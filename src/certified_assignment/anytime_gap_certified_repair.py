from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import heapq
import itertools
import time
import weakref
from typing import Callable, Iterable
import numpy as np

from .instance import AssignmentInstance
from .destroy_repair_analysis import (
    DestroyRepairCache,
    RepairMove,
    build_destroy_repair_cache,
    normalize_destroy_nodes,
    partial_assignment_upper_bound,
    repair_gain,
    repair_is_feasible,
)
from .safe_numerics import SafeEnvelope, build_safe_envelope, exact_repair_feasible
from .coupled_assignment_bound import bound_for_mode


@dataclass(frozen=True)
class AnytimePartialBranch:
    assigned_hosts: tuple[int, ...]
    residual_capacity: np.ndarray
    upper_bound: float
    depth: int


@dataclass(frozen=True)
class GuidancePolicy:
    name: str
    initial_incumbent: Callable[[AssignmentInstance, DestroyRepairCache, float], tuple[int, ...] | None]
    node_order: Callable[[AssignmentInstance, DestroyRepairCache, np.ndarray], int]
    child_order: Callable[[list[AnytimePartialBranch]], list[AnytimePartialBranch]]


@dataclass
class AnytimeRepairCheckpoint:
    """Mutable resumable state for one fixed destroy-and-repair neighborhood.

    The state is deliberately independent of any learned model. Every branch in
    ``queue`` carries an admissible upper bound on all of its feasible
    completions. Consequently, the maximum queued upper bound is a valid global
    bound on every repair not yet fully evaluated.
    """

    cache: DestroyRepairCache
    queue: list[tuple[float, int, AnytimePartialBranch]]
    next_counter: int
    best: RepairMove
    root_upper_bound: float
    leaves_evaluated: int = 0
    partial_branches_expanded: int = 0
    partial_branches_pruned: int = 0
    child_branches_generated: int = 1
    slices_completed: int = 0
    cumulative_elapsed_ms: float = 0.0
    setup_elapsed_ms: float = 0.0
    primal_dive_done: bool = False
    primal_dives: int = 0
    max_pruned_upper_bound: float = float("-inf")
    # Largest numerical pruning guard ever used on this checkpoint.  A later
    # continuation may keep or relax this guard, but it must not request a
    # smaller guard because permanently pruned branches are not reconstructible.
    pruning_tol_used: float = 0.0
    guidance_policy: GuidancePolicy | None = None
    # SHA-256 digests of the frozen repair context.  ``instance_fingerprint``
    # covers the objective and capacity data; ``context_fingerprint`` also
    # covers the incumbent placement, the destroy set and the numeric mode.
    # Empty strings mark legacy checkpoints created before fingerprinting.
    instance_fingerprint: str = ""
    context_fingerprint: str = ""
    # `binary64` is the legacy guarded mode; `safe` adds rigorous rounding
    # envelopes (see safe_numerics) so every certificate bounds the exact gap.
    numeric_mode: str = "binary64"
    safe_envelope: SafeEnvelope | None = None
    # `independent` is Equation 14; `coupled`/`min` add the one-to-one
    # assignment-coupled bound (coupled_assignment_bound, binary64 mode only).
    bound_mode: str = "independent"


NUMERIC_MODE = "binary64"
NUMERIC_MODES = ("binary64", "safe")
LEGACY_CAPACITY_ALLOWANCE = 1e-9
_INSTANCE_DIGESTS: dict[int, tuple[weakref.ref, str]] = {}


def instance_fingerprint(instance: AssignmentInstance) -> str:
    """Digest of the arrays that define the objective and capacities.

    Memoized per live instance object so that per-slice compatibility checks
    do not rehash an O(n^2) interaction matrix on every call.
    """
    key = id(instance)
    cached = _INSTANCE_DIGESTS.get(key)
    if cached is not None and cached[0]() is instance:
        return cached[1]
    h = hashlib.sha256()
    for array in (instance.interaction, instance.demands, instance.capacities, instance.host_cost):
        h.update(str(array.shape).encode())
        h.update(np.ascontiguousarray(array, dtype=np.float64).tobytes())
    digest = h.hexdigest()
    _INSTANCE_DIGESTS[key] = (weakref.ref(instance, lambda _, k=key: _INSTANCE_DIGESTS.pop(k, None)), digest)
    return digest


def context_fingerprint(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: tuple[int, ...],
    numeric_mode: str = NUMERIC_MODE,
) -> str:
    h = hashlib.sha256()
    h.update(instance_fingerprint(instance).encode())
    h.update(np.ascontiguousarray(placement, dtype=np.int64).tobytes())
    h.update(repr(tuple(int(v) for v in nodes)).encode())
    h.update(numeric_mode.encode())
    return h.hexdigest()


def check_checkpoint_compatible(
    state: AnytimeRepairCheckpoint,
    instance: AssignmentInstance,
    placement: np.ndarray | None = None,
) -> None:
    """Reject resumption against a different repair context.

    The instance is always checked.  The placement is checked when supplied
    and must equal the placement the checkpoint was built from; a caller that
    has since applied this checkpoint's own repair omits it.
    """
    if not state.instance_fingerprint:
        return
    if instance_fingerprint(instance) != state.instance_fingerprint:
        raise ValueError("checkpoint was created for a different instance")
    if placement is not None and context_fingerprint(
        instance, placement, state.cache.nodes, state.numeric_mode
    ) != state.context_fingerprint:
        raise ValueError("checkpoint was created for a different placement or destroy set")


@dataclass(frozen=True)
class AnytimeGapCertificate:
    incumbent_gain: float
    frontier_upper_bound: float
    additive_gap: float
    relative_gap: float
    exact: bool
    epsilon_certified: bool
    epsilon_target: float


@dataclass(frozen=True)
class AnytimeRepairStats:
    destroy_set: tuple[int, ...]
    theoretical_assignments: int
    leaves_evaluated: int
    partial_branches_expanded: int
    partial_branches_pruned: int
    child_branches_generated: int
    root_upper_bound: float
    setup_elapsed_ms: float
    slice_elapsed_ms: float
    cumulative_elapsed_ms: float
    total_elapsed_ms: float
    requested_budget_ms: float
    deadline_overrun_ms: float
    slices_completed: int
    queue_size: int
    primal_dives: int


@dataclass(frozen=True)
class AnytimeRepairResult:
    move: RepairMove
    certificate: AnytimeGapCertificate
    stats: AnytimeRepairStats
    checkpoint: AnytimeRepairCheckpoint


def _next_unassigned(
    instance: AssignmentInstance,
    cache: DestroyRepairCache,
    assigned_hosts: np.ndarray,
) -> int:
    candidates = np.flatnonzero(assigned_hosts < 0)
    if candidates.size == 0:
        return -1
    max_cap = np.maximum(instance.capacities.max(axis=0), 1e-12)
    scores: list[float] = []
    for local in candidates:
        node = cache.nodes[int(local)]
        demand_score = float(np.max(instance.demands[node] / max_cap))
        interaction_score = float(np.ptp(cache.external_gain[int(local)]))
        scores.append(demand_score + 1e-6 * interaction_score)
    return int(candidates[int(np.argmax(scores))])


def initialize_anytime_repair(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: Iterable[int],
    initial_target_hosts: Iterable[int] | None = None,
    prebuilt_cache: DestroyRepairCache | None = None,
    tol: float = 1e-12,
    guidance_policy: GuidancePolicy | None = None,
    numeric_mode: str = NUMERIC_MODE,
    bound_mode: str = "independent",
) -> AnytimeRepairCheckpoint:
    """Initialize a resumable best-first repair search.

    ``initial_target_hosts`` may contain any feasible heuristic repair. It is
    used only as the incumbent lower bound; it does not affect validity of the
    upper-bound certificate.
    """

    if numeric_mode not in NUMERIC_MODES:
        raise ValueError(f"numeric_mode must be one of {NUMERIC_MODES}")
    if bound_mode not in ("independent", "coupled", "min"):
        raise ValueError("bound_mode must be independent, coupled or min")
    if numeric_mode == "safe" and bound_mode != "independent":
        raise ValueError("safe mode's rounding envelope covers only the independent bound")
    setup_start = time.perf_counter()
    normalized = normalize_destroy_nodes(instance, nodes)
    cache = prebuilt_cache or build_destroy_repair_cache(instance, placement, normalized)
    if cache.nodes != normalized:
        raise ValueError("prebuilt_cache does not match nodes")
    envelope = build_safe_envelope(instance, placement, cache) if numeric_mode == "safe" else None

    def feasible(target: tuple[int, ...]) -> bool:
        if envelope is not None:
            return exact_repair_feasible(envelope, target)
        return repair_is_feasible(instance, cache, target)

    best = RepairMove(cache.nodes, tuple(cache.original_hosts.tolist()), 0.0)
    if guidance_policy is not None:
        target = guidance_policy.initial_incumbent(instance, cache, tol)
        if target is not None:
            target = tuple(int(h) for h in target)
            if not feasible(target):
                raise ValueError("guidance_policy initial incumbent must define a feasible repair")
            gain = float(repair_gain(cache, target))
            if gain > best.gain + tol:
                best = RepairMove(cache.nodes, target, gain)
    elif initial_target_hosts is not None:
        target = tuple(int(h) for h in initial_target_hosts)
        if not feasible(target):
            raise ValueError("initial_target_hosts must define a feasible repair")
        gain = float(repair_gain(cache, target))
        if gain > best.gain + tol:
            best = RepairMove(cache.nodes, target, gain)

    root_assignment = np.full(cache.size, -1, dtype=int)
    root_residual = cache.residual_capacity.copy()
    root_upper = float(bound_for_mode(
        bound_mode, instance, cache, root_assignment, root_residual,
        envelope.residual_slack if envelope is not None else LEGACY_CAPACITY_ALLOWANCE,
    ))
    # Numerical guard: a valid upper bound cannot be below a feasible incumbent.
    root_upper = max(root_upper, float(best.gain))
    root = AnytimePartialBranch(
        tuple(root_assignment.tolist()), root_residual, root_upper, 0
    )
    queue: list[tuple[float, int, AnytimePartialBranch]] = [(-root_upper, 0, root)]
    heapq.heapify(queue)
    return AnytimeRepairCheckpoint(
        cache=cache,
        queue=queue,
        next_counter=1,
        best=best,
        root_upper_bound=root_upper,
        setup_elapsed_ms=(time.perf_counter() - setup_start) * 1000.0,
        pruning_tol_used=float(tol),
        guidance_policy=guidance_policy,
        instance_fingerprint=instance_fingerprint(instance),
        context_fingerprint=context_fingerprint(
            instance, instance.validate_placement(placement), cache.nodes, numeric_mode
        ),
        numeric_mode=numeric_mode,
        safe_envelope=envelope,
        bound_mode=bound_mode,
    )


def _frontier_upper(state: AnytimeRepairCheckpoint) -> float:
    values = [float(state.best.gain), float(state.max_pruned_upper_bound)]
    if state.queue:
        values.append(float(-state.queue[0][0]))
    return max(values)


def _record_exact_prune(
    state: AnytimeRepairCheckpoint,
    upper_bound: float,
) -> None:
    """Record the largest permanently pruned bound for an honest certificate."""
    state.max_pruned_upper_bound = max(
        float(state.max_pruned_upper_bound), float(upper_bound)
    )


def _domain_slack(state: AnytimeRepairCheckpoint) -> float:
    """Capacity slack for host domains.

    In safe mode the slack is the rigorous residual rounding bound, so the
    domain is a superset of the exactly feasible hosts and the bound stays
    admissible at every coefficient scale.
    """
    if state.safe_envelope is not None:
        return state.safe_envelope.residual_slack
    return LEGACY_CAPACITY_ALLOWANCE


def _bound(state: AnytimeRepairCheckpoint, instance: AssignmentInstance,
           assigned: np.ndarray, residual: np.ndarray) -> float:
    if state.bound_mode == "independent":
        return float(partial_assignment_upper_bound(
            instance, state.cache, assigned, residual, tol=_domain_slack(state)))
    return bound_for_mode(state.bound_mode, instance, state.cache, assigned, residual, _domain_slack(state))


def _leaf_feasible(state: AnytimeRepairCheckpoint, assigned: np.ndarray) -> bool:
    """Safe mode admits an incumbent only if it is feasible in exact arithmetic."""
    if state.safe_envelope is None:
        return True
    return exact_repair_feasible(state.safe_envelope, assigned.tolist())


def _certificate(
    state: AnytimeRepairCheckpoint,
    epsilon_target: float,
    tol: float,
) -> AnytimeGapCertificate:
    frontier = _frontier_upper(state)
    raw_gap = max(0.0, frontier - float(state.best.gain))
    # ``exact`` and ``epsilon_certified`` describe the search state (the same
    # tests that stop the search); the reported gap is the certificate.
    exact = raw_gap <= tol
    epsilon_certified = raw_gap <= epsilon_target + tol
    gap = raw_gap
    if state.safe_envelope is not None:
        # Every stored bound and the incumbent gain are within delta of their
        # exact values, so exact(U) - exact(g) <= raw gap + 2 delta.  Two upward
        # ulps absorb the rounding of the subtraction above and of this addition.
        gap = float(np.nextafter(np.nextafter(raw_gap + 2.0 * state.safe_envelope.delta, np.inf), np.inf))
        frontier = float(state.best.gain) + gap
    relative = gap / max(abs(float(state.best.gain)), 1e-12)
    return AnytimeGapCertificate(
        incumbent_gain=float(state.best.gain),
        frontier_upper_bound=float(frontier),
        additive_gap=float(gap),
        relative_gap=float(relative),
        exact=bool(exact),
        epsilon_certified=bool(epsilon_certified),
        epsilon_target=float(epsilon_target),
    )


def _run_primal_dive(
    instance: AssignmentInstance,
    state: AnytimeRepairCheckpoint,
    deadline: float,
    counter: itertools.count,
    epsilon_target: float,
    tol: float,
) -> None:
    """Follow the strongest-bound child to obtain a feasible leaf quickly.

    Sibling branches are retained in the global frontier, so the gap certificate
    remains valid. If the deadline is reached, the unfinished branch is pushed
    back unchanged and the dive resumes in a later time slice.
    """
    if state.primal_dive_done or not state.queue:
        return
    _, _, branch = heapq.heappop(state.queue)
    while True:
        if time.perf_counter() >= deadline:
            heapq.heappush(state.queue, (-branch.upper_bound, next(counter), branch))
            return
        if branch.upper_bound <= state.best.gain + tol:
            state.partial_branches_pruned += 1
            _record_exact_prune(state, branch.upper_bound)
            state.primal_dive_done = True
            state.primal_dives += 1
            return
        assigned = np.asarray(branch.assigned_hosts, dtype=int)
        if state.guidance_policy is not None:
            local = state.guidance_policy.node_order(instance, state.cache, assigned)
        else:
            local = _next_unassigned(instance, state.cache, assigned)
        if local < 0:
            state.leaves_evaluated += 1
            gain = float(repair_gain(state.cache, assigned))
            if gain > state.best.gain + tol and _leaf_feasible(state, assigned):
                state.best = RepairMove(
                    state.cache.nodes, tuple(int(h) for h in assigned), gain
                )
            state.primal_dive_done = True
            state.primal_dives += 1
            return
        state.partial_branches_expanded += 1
        node = state.cache.nodes[local]
        feasible_hosts = np.flatnonzero(np.all(
            branch.residual_capacity + _domain_slack(state) >= instance.demands[node][None, :],
            axis=1,
        ))
        children: list[AnytimePartialBranch] = []
        for host in feasible_hosts:
            child_assignment = assigned.copy(); child_assignment[local] = int(host)
            child_residual = branch.residual_capacity.copy()
            child_residual[int(host)] -= instance.demands[node]
            upper = float(_bound(state, instance, child_assignment, child_residual))
            state.child_branches_generated += 1
            if upper <= state.best.gain + tol:
                state.partial_branches_pruned += 1
                _record_exact_prune(state, upper)
                continue
            children.append(AnytimePartialBranch(
                tuple(child_assignment.tolist()), child_residual, upper, branch.depth + 1
            ))
        if not children:
            state.primal_dive_done = True
            state.primal_dives += 1
            return
        if state.guidance_policy is not None:
            children = state.guidance_policy.child_order(children)
        else:
            children.sort(key=lambda b: -b.upper_bound)
        branch = children[0]
        for sibling in children[1:]:
            heapq.heappush(state.queue, (-sibling.upper_bound, next(counter), sibling))


def advance_anytime_repair(
    instance: AssignmentInstance,
    state: AnytimeRepairCheckpoint,
    budget_ms: float,
    epsilon_target: float = 0.0,
    tol: float = 1e-12,
    placement: np.ndarray | None = None,
) -> AnytimeRepairResult:
    """Advance a repair search for at most one requested time slice.

    At every return, including deadline interruption, the result includes a
    valid additive optimality certificate

        g* - g_inc <= max(0, U_frontier - g_inc).

    Search can be resumed by passing the returned checkpoint to another call.
    ``epsilon_target`` is a stopping condition, not a permanent pruning
    tolerance: only branches dominated by the incumbent up to ``tol`` are
    discarded.  Therefore a checkpoint returned at a positive target can later
    resume with a smaller target, including exact continuation.  The
    implementation checks the deadline only at branch-safe points. The measured
    overrun is reported explicitly and is normally bounded by one branch
    expansion.
    """

    if budget_ms < 0:
        raise ValueError("budget_ms must be non-negative")
    if epsilon_target < 0:
        raise ValueError("epsilon_target must be non-negative")
    if tol < 0:
        raise ValueError("tol must be non-negative")

    check_checkpoint_compatible(state, instance, placement)

    # Checkpoint compatibility includes the pruning guard.  Increasing the
    # guard is conservative for compatibility (future pruning may be looser),
    # but decreasing it would ask a checkpoint to reconstruct branches that
    # may have been permanently pruned under a larger guard.  Those branches
    # remain covered by max_pruned_upper_bound for certification, but their
    # internal states are not recoverable.
    if float(tol) + 1e-30 < float(state.pruning_tol_used):
        raise ValueError(
            "checkpoint was pruned with a larger tolerance; "
            f"requested tol={tol:g} < stored pruning_tol_used="
            f"{state.pruning_tol_used:g}"
        )
    state.pruning_tol_used = max(float(state.pruning_tol_used), float(tol))

    start = time.perf_counter()
    deadline = start + budget_ms / 1000.0
    counter = itertools.count(state.next_counter)

    # A positive target is a stopping condition.  Keep the frontier intact so
    # the same checkpoint can later resume with a smaller target.
    if _frontier_upper(state) > state.best.gain + epsilon_target + tol:
        _run_primal_dive(
            instance, state, deadline, counter, epsilon_target, tol
        )

    while state.queue:
        # The largest frontier bound already certifies the requested tolerance.
        if -state.queue[0][0] <= state.best.gain + epsilon_target + tol:
            break
        if time.perf_counter() >= deadline:
            break

        _, _, branch = heapq.heappop(state.queue)
        if branch.upper_bound <= state.best.gain + tol:
            state.partial_branches_pruned += 1
            _record_exact_prune(state, branch.upper_bound)
            continue

        assigned = np.asarray(branch.assigned_hosts, dtype=int)
        if state.guidance_policy is not None:
            local = state.guidance_policy.node_order(instance, state.cache, assigned)
        else:
            local = _next_unassigned(instance, state.cache, assigned)
        if local < 0:
            state.leaves_evaluated += 1
            gain = float(repair_gain(state.cache, assigned))
            if gain > state.best.gain + tol and _leaf_feasible(state, assigned):
                state.best = RepairMove(
                    state.cache.nodes,
                    tuple(int(h) for h in assigned),
                    gain,
                )
            continue

        state.partial_branches_expanded += 1
        node = state.cache.nodes[local]
        feasible_hosts = np.flatnonzero(np.all(
            branch.residual_capacity + _domain_slack(state) >= instance.demands[node][None, :],
            axis=1,
        ))

        # Generate the children of one branch atomically. This preserves a clean
        # resumable frontier and bounds deadline overrun by one such expansion.
        children: list[AnytimePartialBranch] = []
        for host in feasible_hosts:
            child_assignment = assigned.copy()
            child_assignment[local] = int(host)
            child_residual = branch.residual_capacity.copy()
            child_residual[int(host)] -= instance.demands[node]
            upper = float(_bound(state, instance, child_assignment, child_residual))
            state.child_branches_generated += 1
            if upper <= state.best.gain + tol:
                state.partial_branches_pruned += 1
                _record_exact_prune(state, upper)
                continue
            children.append(AnytimePartialBranch(
                tuple(child_assignment.tolist()),
                child_residual,
                upper,
                branch.depth + 1,
            ))

        # Better upper bounds are inserted first only for deterministic tie
        # behavior; correctness is independent of insertion order.
        if state.guidance_policy is not None:
            children = state.guidance_policy.child_order(children)
        else:
            children.sort(key=lambda b: -b.upper_bound)
        for child in children:
            heapq.heappush(
                state.queue,
                (-child.upper_bound, next(counter), child),
            )

    state.next_counter = next(counter)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    state.slices_completed += 1
    state.cumulative_elapsed_ms += elapsed_ms
    cert = _certificate(state, epsilon_target, tol)
    overrun = max(0.0, elapsed_ms - budget_ms)
    stats = AnytimeRepairStats(
        destroy_set=state.cache.nodes,
        theoretical_assignments=instance.n_hosts ** state.cache.size,
        leaves_evaluated=state.leaves_evaluated,
        partial_branches_expanded=state.partial_branches_expanded,
        partial_branches_pruned=state.partial_branches_pruned,
        child_branches_generated=state.child_branches_generated,
        root_upper_bound=float(state.root_upper_bound),
        setup_elapsed_ms=float(state.setup_elapsed_ms),
        slice_elapsed_ms=float(elapsed_ms),
        cumulative_elapsed_ms=float(state.cumulative_elapsed_ms),
        total_elapsed_ms=float(state.setup_elapsed_ms + state.cumulative_elapsed_ms),
        requested_budget_ms=float(budget_ms),
        deadline_overrun_ms=float(overrun),
        slices_completed=state.slices_completed,
        queue_size=len(state.queue),
        primal_dives=state.primal_dives,
    )
    return AnytimeRepairResult(state.best, cert, stats, state)


def anytime_certified_repair_destroy_set(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: Iterable[int],
    budget_ms: float,
    epsilon_target: float = 0.0,
    initial_target_hosts: Iterable[int] | None = None,
    prebuilt_cache: DestroyRepairCache | None = None,
    tol: float = 1e-12,
    guidance_policy: GuidancePolicy | None = None,
    numeric_mode: str = NUMERIC_MODE,
) -> AnytimeRepairResult:
    wall_start = time.perf_counter()
    state = initialize_anytime_repair(
        instance,
        placement,
        nodes,
        initial_target_hosts=initial_target_hosts,
        prebuilt_cache=prebuilt_cache,
        tol=tol,
        guidance_policy=guidance_policy,
        numeric_mode=numeric_mode,
    )
    remaining_ms = max(0.0, float(budget_ms) - state.setup_elapsed_ms)
    result = advance_anytime_repair(
        instance,
        state,
        budget_ms=remaining_ms,
        epsilon_target=epsilon_target,
        tol=tol,
    )
    wall_elapsed_ms = (time.perf_counter() - wall_start) * 1000.0
    stats = replace(
        result.stats,
        requested_budget_ms=float(budget_ms),
        deadline_overrun_ms=max(0.0, wall_elapsed_ms - float(budget_ms)),
        total_elapsed_ms=float(wall_elapsed_ms),
    )
    return AnytimeRepairResult(result.move, result.certificate, stats, result.checkpoint)
