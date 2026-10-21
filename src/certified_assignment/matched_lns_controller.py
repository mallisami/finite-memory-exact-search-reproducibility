"""Shared adaptive-LNS controller with an injectable repair policy.

This is the same destroy-operator pool, roulette-wheel operator selection,
exponential weight update, and simulated-annealing acceptance rule as
``alns_baseline.adaptive_lns`` (kept unmodified — see that module), except the
repair step is delegated to a caller-supplied ``RepairPolicy`` instead of a
fixed pair of heuristic repair functions. This lets the exact same controller
be run once per repair-engine variant (heuristic / restart-PCR /
persistent-PCR / certificate-guided persistent-PCR) for a fair, matched
comparison, instead of forking the loop once per variant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Protocol, Sequence

import numpy as np

from .instance import AssignmentInstance
from .objective import assignment_cost
from .feasibility import is_feasible
from .destroy_repair_analysis import DestroyRepairCache, apply_repair
from .alns_baseline import _destroy_random, _destroy_costly, _destroy_affinity

DESTROY_OPS = (_destroy_random, _destroy_costly, _destroy_affinity)


@dataclass(frozen=True)
class RepairPolicyContext:
    instance: AssignmentInstance
    placement: np.ndarray
    nodes: tuple[int, ...]
    rng: np.random.Generator
    iteration: int
    elapsed_ms: float
    remaining_budget_ms: float
    deadline_guard_ms: float


@dataclass(frozen=True)
class RepairPolicyOutcome:
    target_hosts: tuple[int, ...]
    gain: float
    cache: DestroyRepairCache
    diagnostics: dict[str, float | int | str] = field(default_factory=dict)


class RepairPolicy(Protocol):
    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome: ...

    def notify_move(
        self,
        instance: AssignmentInstance,
        accepted: bool,
        nodes: tuple[int, ...],
        iteration: int,
    ) -> None:
        """Called once per iteration after the accept/reject decision.

        Stateless policies (heuristic, restart-PCR) implement this as a no-op.
        Persistent policies use it to invalidate checkpoints made stale by an
        accepted move.
        """
        ...


@dataclass(frozen=True)
class IterationRecord:
    iteration: int
    elapsed_ms: float
    destroy_op_index: int
    repair_arm_index: int
    nodes: tuple[int, ...]
    objective_before: float
    objective_after: float
    accepted: bool
    score: float
    destroy_weight_after: float
    repair_weight_after: float
    temperature: float
    best_objective_so_far: float
    outcome: RepairPolicyOutcome
    recurrent: bool = False
    filtered_redraws: int = 0


class RecurrenceSampler:
    """Re-select a previously used, still-compatible destroy set (X5).

    Compatibility is decided at the controller level with the same adjacency
    rule persistent PCR uses to evict checkpoints, so every repair arm faces
    the same recurrence mechanism.  A set stays compatible after its own
    repair is accepted and becomes incompatible when an accepted move changes
    the host of a node in it or interacting with it.
    """

    def __init__(self, probability: float):
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        self.probability = probability
        self.compatible: list[tuple[int, ...]] = []

    def pick(self, rng: np.random.Generator) -> tuple[int, ...] | None:
        if not self.compatible:
            return None
        return self.compatible[int(rng.integers(len(self.compatible)))]

    def observe(self, instance: AssignmentInstance, nodes: tuple[int, ...], accepted: bool) -> None:
        if accepted:
            moved = np.asarray(nodes, dtype=int)
            adjacent = (np.any(instance.interaction[moved] != 0, axis=0)
                        | np.any(instance.interaction[:, moved] != 0, axis=1))
            affected = set(np.flatnonzero(adjacent).tolist()) | set(moved.tolist())
            self.compatible = [s for s in self.compatible if s == nodes or not affected.intersection(s)]
        if nodes not in self.compatible:
            self.compatible.append(nodes)


@dataclass(frozen=True)
class MatchedALNSResult:
    placement: np.ndarray
    initial_objective: float
    final_objective: float
    iterations: int
    accepted_moves: int
    elapsed_ms: float
    destroy_weights: tuple[float, ...]
    repair_weights: tuple[float, ...]

    @property
    def reduction_pct(self) -> float:
        if self.initial_objective <= 0:
            return 0.0
        return 100.0 * (self.initial_objective - self.final_objective) / self.initial_objective


def matched_adaptive_lns(
    instance: AssignmentInstance,
    initial_placement: np.ndarray,
    repair_arms: Sequence[RepairPolicy],
    destroy_size: int = 5,
    time_limit_s: float | None = None,
    max_iterations: int | None = None,
    seed: int = 0,
    reaction: float = 0.2,
    cooling: float = 0.995,
    deadline_guard_ms: float = 1.0,
    on_iteration: Callable[[IterationRecord], None] | None = None,
    recurrence: RecurrenceSampler | None = None,
    destroy_filter: Callable[[tuple[int, ...]], bool] | None = None,
    max_filter_redraws: int = 10,
    repair_trace: Sequence[tuple[int, ...]] | None = None,
) -> MatchedALNSResult:
    """Run adaptive LNS with an injectable repair engine.

    Exactly one of ``time_limit_s`` (real, non-reproducible wall-clock
    stopping — used for the actual matched-budget experiment) or
    ``max_iterations`` (deterministic stopping — used only by tests) must be
    given, mirroring why this repo never bit-identity-tests
    ``advance_anytime_repair``'s wall-clock path, only its step-counted twin.
    """
    if not repair_arms:
        raise ValueError("repair_arms must be non-empty")
    if destroy_size < 2 or destroy_size > instance.n_nodes:
        raise ValueError("invalid destroy_size")
    if (time_limit_s is None) == (max_iterations is None):
        raise ValueError("exactly one of time_limit_s or max_iterations must be set")
    if time_limit_s is not None and time_limit_s <= 0:
        raise ValueError("time_limit_s must be positive")
    if max_iterations is not None and max_iterations < 1:
        raise ValueError("max_iterations must be positive")

    trace_nodes: tuple[tuple[int, ...], ...] | None = None
    if repair_trace is not None:
        if recurrence is not None:
            raise ValueError("repair_trace and recurrence cannot be used together")
        trace_nodes = tuple(tuple(int(v) for v in nodes) for nodes in repair_trace)
        if not trace_nodes:
            raise ValueError("repair_trace must contain at least one repair context")
        if max_iterations is not None and len(trace_nodes) < max_iterations:
            raise ValueError("repair_trace is shorter than max_iterations")
        for nodes in trace_nodes:
            if len(nodes) != destroy_size:
                raise ValueError("every repair_trace entry must match destroy_size")
            if len(set(nodes)) != len(nodes):
                raise ValueError("repair_trace entries must not contain duplicate nodes")
            if any(v < 0 or v >= instance.n_nodes for v in nodes):
                raise ValueError("repair_trace contains an out-of-range node")
            if destroy_filter is not None and not destroy_filter(nodes):
                raise ValueError("repair_trace contains a set rejected by destroy_filter")

    p = instance.validate_placement(initial_placement).copy()
    if not is_feasible(instance, p):
        raise ValueError("initial placement must be feasible")

    rng = np.random.default_rng(seed)
    dw = np.ones(len(DESTROY_OPS), dtype=float)
    rw = np.ones(len(repair_arms), dtype=float)

    start = time.perf_counter()
    initial = float(assignment_cost(instance, p))
    current = initial
    best_p = p.copy()
    best = current
    accepted_moves = 0
    iterations = 0
    temperature = max(1e-9, 0.01 * initial)

    budget_ms = time_limit_s * 1000.0 if time_limit_s is not None else None

    def _elapsed_ms() -> float:
        return (time.perf_counter() - start) * 1000.0

    def _keep_going() -> bool:
        if trace_nodes is not None and iterations >= len(trace_nodes):
            return False
        if max_iterations is not None:
            return iterations < max_iterations
        return _elapsed_ms() < budget_ms  # type: ignore[operator]

    trace_seen: set[tuple[int, ...]] = set()

    while _keep_going():
        iterations += 1
        di = int(rng.choice(len(dw), p=dw / dw.sum()))
        ri = int(rng.choice(len(rw), p=rw / rw.sum()))
        nodes = None
        recurrent = False
        redraws = 0
        # A supplied trace overrides destroy-set generation but leaves all
        # repair/acceptance logic untouched.  This gives Paper-2 policies the
        # exact same sequence of repair contexts, so retention effects are not
        # confounded by different neighborhood draws.  The default path below
        # is unchanged draw for draw when repair_trace is None.
        if trace_nodes is not None:
            nodes = trace_nodes[iterations - 1]
            recurrent = nodes in trace_seen
            trace_seen.add(nodes)
        else:
            if recurrence is not None and rng.random() < recurrence.probability:
                nodes = recurrence.pick(rng)
                recurrent = nodes is not None
            if nodes is None:
                nodes = DESTROY_OPS[di](instance, p, destroy_size, rng)
                if destroy_filter is not None:
                    while not destroy_filter(nodes) and redraws < max_filter_redraws:
                        nodes = DESTROY_OPS[di](instance, p, destroy_size, rng)
                        redraws += 1

        elapsed_ms = _elapsed_ms()
        remaining_budget_ms = (budget_ms - elapsed_ms) if budget_ms is not None else float("inf")
        ctx = RepairPolicyContext(
            instance=instance,
            placement=p,
            nodes=nodes,
            rng=rng,
            iteration=iterations,
            elapsed_ms=elapsed_ms,
            remaining_budget_ms=remaining_budget_ms,
            deadline_guard_ms=deadline_guard_ms,
        )
        outcome = repair_arms[ri](ctx)
        q = apply_repair(p, outcome.cache, outcome.target_hosts)
        if not is_feasible(instance, q):
            raise AssertionError("matched_adaptive_lns repair produced infeasible placement")
        q_cost = float(assignment_cost(instance, q))
        before_obj = current
        delta = q_cost - current
        accept = delta < 0 or rng.random() < np.exp(-max(0.0, delta) / max(temperature, 1e-12))
        score = 0.0
        if accept:
            p = q
            current = q_cost
            accepted_moves += 1
            score = 1.0
            if current < best - 1e-9:
                best = current
                best_p = p.copy()
                score = 5.0
        if trace_nodes is None and not recurrent:
            dw[di] = (1.0 - reaction) * dw[di] + reaction * max(0.1, score)
        rw[ri] = (1.0 - reaction) * rw[ri] + reaction * max(0.1, score)
        temperature *= cooling

        # Every arm sees every accepted move: a stateful arm must invalidate its
        # checkpoints even when another arm produced the move.
        for arm in repair_arms:
            arm.notify_move(instance, bool(accept), nodes, iterations)
        if recurrence is not None:
            recurrence.observe(instance, nodes, bool(accept))

        if on_iteration is not None:
            on_iteration(IterationRecord(
                iteration=iterations,
                elapsed_ms=elapsed_ms,
                destroy_op_index=di,
                repair_arm_index=ri,
                nodes=nodes,
                objective_before=before_obj,
                objective_after=current,
                accepted=bool(accept),
                score=score,
                destroy_weight_after=float(dw[di]),
                repair_weight_after=float(rw[ri]),
                temperature=float(temperature),
                best_objective_so_far=best,
                outcome=outcome,
                recurrent=recurrent,
                filtered_redraws=redraws,
            ))

    elapsed = _elapsed_ms()
    return MatchedALNSResult(
        best_p,
        initial,
        best,
        iterations,
        accepted_moves,
        float(elapsed),
        tuple(float(x) for x in dw),
        tuple(float(x) for x in rw),
    )
