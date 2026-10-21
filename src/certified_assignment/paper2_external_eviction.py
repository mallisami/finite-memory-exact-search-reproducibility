"""External bounded-cache eviction baselines for Paper-2 RQ1.

Checkpoint-level adaptations of the bounded-cache policies evaluated by
Medema, Breeman & Lazovik (Constraints, 2024): FIFO, LRU, and Random
Replacement.  The checkpoint representation, exact repair, controller,
compatibility revalidation, invalidation, acceptance random variates, and byte
budgets remain those of the frozen P7 online-retention experiment.

The source paper uses an entry-count capacity.  Paper 2 has heterogeneous
serialized checkpoint sizes, so the adaptation repeatedly evicts resident
entries until the *same exact byte budget* used by P7 can admit the incoming
checkpoint.  As in the source policy semantics, the incoming item is admitted
after eviction and is not itself an eviction victim.
"""
from __future__ import annotations

from typing import Literal, Sequence
import math
import time

import numpy as np

from .domain_instances import make_domain_case
from .feasibility import is_feasible
from .objective import assignment_cost
from .paper2_online_pilot import (
    OnlineStepPolicy,
    P7PilotResult,
    ReplayTraceEntry,
    StoredCheckpoint,
)

ExternalPolicyName = Literal["fifo", "lru", "random"]


class ExternalEvictionOnlineStepPolicy(OnlineStepPolicy):
    """P7 persistence mechanism with only the resident-set rule replaced."""

    def __init__(
        self,
        name: ExternalPolicyName,
        *,
        slice_pops: int,
        budget_bytes: int,
        eviction_seed: int | None = None,
        future_horizon: int = 40,
    ):
        if name not in {"fifo", "lru", "random"}:
            raise ValueError(f"unsupported external policy: {name}")
        if int(budget_bytes) <= 0:
            raise ValueError("budget_bytes must be positive")
        if name == "random" and eviction_seed is None:
            raise ValueError("random replacement requires an explicit eviction_seed")
        # OnlineStepPolicy does not runtime-check the Literal annotation.
        super().__init__(
            name,  # type: ignore[arg-type]
            slice_pops=int(slice_pops),
            budget_bytes=int(budget_bytes),
            predictor=None,
            future_horizon=int(future_horizon),
        )
        self.eviction_seed = None if eviction_seed is None else int(eviction_seed)
        self._eviction_rng = None if name != "random" else np.random.default_rng(self.eviction_seed)

    def _score_probability(self, **kwargs) -> float:  # noqa: ARG002
        # External policies do not score recurrence or compatibility probability.
        # P7's StoredCheckpoint field is retained only to avoid changing the
        # checkpoint/lifecycle representation; its value is unused by eviction.
        return 0.0

    @staticmethod
    def _ordered_keys(records: dict[tuple[int, ...], StoredCheckpoint]) -> list[tuple[int, ...]]:
        return sorted(records)

    def _choose_victim(self, records: dict[tuple[int, ...], StoredCheckpoint]) -> tuple[int, ...]:
        if not records:
            raise RuntimeError("eviction requested with no resident checkpoints")
        if self.name == "fifo":
            # Admission/creation order. Hits do not update FIFO position.
            return min(records, key=lambda k: (records[k].created_iteration, k))
        if self.name == "lru":
            # In the P7 controller, last_scored_iteration is exactly the most
            # recent occurrence/access of that resident repair context because
            # only the currently accessed context is reserialized each step.
            return min(
                records,
                key=lambda k: (
                    records[k].last_scored_iteration,
                    records[k].created_iteration,
                    k,
                ),
            )
        if self.name == "random":
            assert self._eviction_rng is not None
            keys = self._ordered_keys(records)
            return keys[int(self._eviction_rng.integers(0, len(keys)))]
        raise AssertionError(self.name)

    def _evict_until(self, *, bytes_required: int, iteration: int) -> None:  # noqa: ARG002
        assert self.budget_bytes is not None
        if bytes_required > self.budget_bytes:
            raise ValueError(
                f"incoming checkpoint ({bytes_required} B) exceeds budget ({self.budget_bytes} B)"
            )
        while self.memory.bytes_used + int(bytes_required) > self.budget_bytes:
            victim = self._choose_victim(self.memory.records)
            self.memory.records.pop(victim)
            self.memory.capacity_evictions += 1

    def _select_exact(self, incoming: StoredCheckpoint | None, iteration: int) -> bool:
        """Apply the frozen external eviction rule under the exact P7 byte cap.

        The method name is inherited from P7.  No exact knapsack selection is
        performed for these external policies.
        """
        assert self.budget_bytes is not None
        t0 = time.perf_counter()

        if incoming is None:
            # Re-serialization after a placement change can alter byte size.
            # Restore feasibility using the same policy order over the current
            # resident set.  Here every current entry is a legitimate victim.
            while self.memory.bytes_used > self.budget_bytes:
                victim = self._choose_victim(self.memory.records)
                self.memory.records.pop(victim)
                self.memory.capacity_evictions += 1
            self.memory.selection_ms += (time.perf_counter() - t0) * 1000.0
            self.memory.update_accounting()
            return True

        # A recurring resident checkpoint is an access/hit.  Remove its old
        # serialized version before computing admission pressure, then reinsert
        # the updated state.  FIFO keeps the original creation/admission time;
        # LRU's last_scored_iteration has already been set to this iteration.
        self.memory.records.pop(incoming.key, None)
        self._evict_until(bytes_required=incoming.size_bytes, iteration=iteration)
        self.memory.records[incoming.key] = incoming

        self.memory.selection_ms += (time.perf_counter() - t0) * 1000.0
        self.memory.update_accounting()
        return True


def run_external_online_replay(
    domain: str,
    seed: int,
    trace: Sequence[ReplayTraceEntry],
    *,
    policy_name: ExternalPolicyName,
    slice_pops: int = 8,
    budget_bytes: int,
    budget_fraction: float | None = None,
    eviction_seed: int | None = None,
    cooling: float = 0.995,
) -> P7PilotResult:
    """Run one P7 replay with only the finite-memory eviction rule changed."""
    case = make_domain_case(domain, 24, 6, seed=int(seed))
    instance = case.instance
    p = case.placement.copy()
    if not is_feasible(instance, p):
        raise ValueError("initial placement must be feasible")
    initial = float(assignment_cost(instance, p))
    current = initial
    best = current
    temperature = max(1e-9, 0.01 * initial)
    accepted_moves = 0
    objective_ratios: list[float] = []
    policy = ExternalEvictionOnlineStepPolicy(
        policy_name,
        slice_pops=int(slice_pops),
        budget_bytes=int(budget_bytes),
        eviction_seed=eviction_seed,
        future_horizon=40,
    )

    # Identical controller acceptance stream to the frozen P7 implementation.
    accept_rng = np.random.default_rng(8_800_000 + int(seed))
    uniforms = accept_rng.random(len(trace))

    for iteration, entry in enumerate(trace, start=1):
        local_rng = np.random.default_rng(9_900_000 + 1000 * int(seed) + iteration)
        before = current
        targets, _, cache, _diag = policy.repair(
            instance=instance,
            placement=p,
            nodes=entry.nodes,
            iteration=iteration,
            destroy_op_index=entry.destroy_op_index,
            objective_before=current,
            best_objective=best,
            temperature=temperature,
            local_rng=local_rng,
        )
        q = p.copy()
        for node, host in zip(cache.nodes, targets):
            q[int(node)] = int(host)
        if not is_feasible(instance, q):
            raise AssertionError("P7 external comparator produced infeasible placement")
        q_cost = float(assignment_cost(instance, q))
        delta = q_cost - current
        accept_prob = 1.0 if delta < 0 else math.exp(-max(0.0, delta) / max(temperature, 1e-12))
        accept = bool(delta < 0 or uniforms[iteration - 1] < accept_prob)
        changed_nodes = tuple(int(v) for v in np.flatnonzero(q != p)) if accept else ()
        if accept:
            p = q
            current = q_cost
            accepted_moves += 1
            best = min(best, current)
        policy.notify_after_decision(
            instance=instance,
            nodes=entry.nodes,
            accepted=accept,
            iteration=iteration,
            objective_before=before,
            objective_after=current,
            placement=p,
            changed_nodes=changed_nodes,
        )
        temperature *= cooling
        objective_ratios.append(current / initial if initial > 0 else 1.0)

    unique = len({e.nodes for e in trace})
    return P7PilotResult(
        domain=domain,
        instance_seed=int(seed),
        policy=policy_name,
        budget_fraction=budget_fraction,
        budget_bytes=int(budget_bytes),
        iterations=len(trace),
        accepted_moves=accepted_moves,
        initial_objective=initial,
        final_objective=current,
        best_objective=best,
        mean_objective_ratio=float(np.mean(objective_ratios)),
        branch_pops_executed=int(policy.branch_pops_executed),
        useful_resumes=int(policy.useful_resumes),
        reused_prior_branch_pops=int(policy.reused_prior_branch_pops),
        checkpoint_creations=int(policy.checkpoint_creations),
        exact_retirements=int(policy.exact_retirements),
        capacity_evictions=int(policy.memory.capacity_evictions),
        invalidation_evictions=int(policy.memory.invalidation_evictions),
        not_retained=int(policy.memory.not_retained),
        peak_bytes=int(policy.memory.peak_bytes),
        byte_time=int(policy.memory.byte_time),
        peak_active_checkpoints=int(policy.memory.peak_active_checkpoints),
        mean_active_checkpoints=float(policy.memory.active_checkpoint_time / max(1, 2 * len(trace))),
        serialization_ms=float(policy.memory.serialization_ms),
        restoration_ms=float(policy.memory.restoration_ms),
        selection_ms=float(policy.memory.selection_ms),
        model_scoring_ms=0.0,
        max_checkpoint_size_bytes=int(policy.max_checkpoint_size_bytes),
        trace_unique_contexts=int(unique),
        trace_recurrence_events=int(len(trace) - unique),
    )
