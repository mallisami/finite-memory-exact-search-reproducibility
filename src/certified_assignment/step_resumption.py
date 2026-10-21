from __future__ import annotations

import heapq
import itertools
import numpy as np

from .instance import AssignmentInstance
from .destroy_repair_analysis import RepairMove, repair_gain, partial_assignment_upper_bound
from .anytime_gap_certified_repair import (
    AnytimePartialBranch,
    AnytimeRepairCheckpoint,
    AnytimeGapCertificate,
    _bound,
    _certificate,
    _domain_slack,
    _leaf_feasible,
    _next_unassigned,
    check_checkpoint_compatible,
    _record_exact_prune,
)


def advance_anytime_repair_steps(
    instance: AssignmentInstance,
    state: AnytimeRepairCheckpoint,
    max_branch_pops: int,
    epsilon_target: float = 0.0,
    tol: float = 1e-12,
) -> tuple[RepairMove, AnytimeGapCertificate, int]:
    """Advance a checkpoint by a deterministic number of branch pops.

    This helper is for hardware-independent resumption validation. It applies
    the same expansion and exact-pruning rules as the time-limited routine, but
    stops after ``max_branch_pops`` queue removals. The primal dive is disabled
    by the experiment before the first call so continuous and sliced schedules
    receive identical units of best-first work.
    """
    if max_branch_pops < 0:
        raise ValueError("max_branch_pops must be non-negative")
    if float(tol) + 1e-30 < float(state.pruning_tol_used):
        raise ValueError("checkpoint was pruned with a larger tolerance")
    check_checkpoint_compatible(state, instance)
    state.pruning_tol_used = max(float(state.pruning_tol_used), float(tol))
    counter = itertools.count(state.next_counter)
    pops = 0
    while state.queue and pops < max_branch_pops:
        if -state.queue[0][0] <= state.best.gain + epsilon_target + tol:
            break
        _, _, branch = heapq.heappop(state.queue)
        pops += 1
        if branch.upper_bound <= state.best.gain + tol:
            state.partial_branches_pruned += 1
            _record_exact_prune(state, branch.upper_bound)
            continue
        assigned = np.asarray(branch.assigned_hosts, dtype=int)
        local = _next_unassigned(instance, state.cache, assigned)
        if local < 0:
            state.leaves_evaluated += 1
            gain = float(repair_gain(state.cache, assigned))
            if gain > state.best.gain + tol and _leaf_feasible(state, assigned):
                state.best = RepairMove(
                    state.cache.nodes, tuple(int(h) for h in assigned), gain
                )
            continue
        state.partial_branches_expanded += 1
        node = state.cache.nodes[local]
        feasible_hosts = np.flatnonzero(
            np.all(
                branch.residual_capacity + _domain_slack(state)
                >= instance.demands[node][None, :],
                axis=1,
            )
        )
        children: list[AnytimePartialBranch] = []
        for host in feasible_hosts:
            child_assignment = assigned.copy()
            child_assignment[local] = int(host)
            child_residual = branch.residual_capacity.copy()
            child_residual[int(host)] -= instance.demands[node]
            upper = float(
                _bound(state, instance, child_assignment, child_residual)
            )
            state.child_branches_generated += 1
            if upper <= state.best.gain + tol:
                state.partial_branches_pruned += 1
                _record_exact_prune(state, upper)
                continue
            children.append(
                AnytimePartialBranch(
                    tuple(child_assignment.tolist()),
                    child_residual,
                    upper,
                    branch.depth + 1,
                )
            )
        children.sort(key=lambda b: -b.upper_bound)
        for child in children:
            heapq.heappush(state.queue, (-child.upper_bound, next(counter), child))
    state.next_counter = next(counter)
    state.slices_completed += 1
    cert = _certificate(state, epsilon_target, tol)
    return state.best, cert, pops
