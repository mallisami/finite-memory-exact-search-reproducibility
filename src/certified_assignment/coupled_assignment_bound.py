"""Assignment-coupled partial-repair bound for one-to-one neighborhoods (X6).

In a one-to-one neighborhood every available host can take at most one of the
unassigned destroyed nodes, as in QAP-derived instances.  The independent bound
(Equation 14) lets several nodes claim the same host; this Gilmore-Lawler-style
bound forbids that through a linear assignment.

For unassigned node u on host h let

    l[u, h] = E_u(h) + sum_{i in A} P_iu(z_i, h)
              + 1/2 * sum_{v in U, v != u} max_{k in H_v, k != h} P_uv(h, k).

Any feasible one-to-one completion y has gain
    exact(A) + sum_u [ E_u(y_u) + sum_A P_iu(z_i, y_u) + 1/2 sum_{v != u} P_uv(y_u, y_v) ],
and because y_v != y_u each bracket is at most l[u, y_u].  Hence
    gain(y) <= exact(A) + max over injective u -> h of sum_u l[u, h],
which a linear assignment solves exactly.  The bound is admissible but not
necessarily monotone under branching; certificate validity does not need
monotonicity.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from .destroy_repair_analysis import DestroyRepairCache, canonical_pair_gain, partial_assignment_upper_bound
from .instance import AssignmentInstance


def is_one_to_one(instance: AssignmentInstance, cache: DestroyRepairCache, unassigned: np.ndarray,
                  residual: np.ndarray, tol: float) -> bool:
    """True if no available host can hold two of the unassigned nodes."""
    if unassigned.size < 2:
        return False
    demands = instance.demands[[cache.nodes[u] for u in unassigned]]
    smallest_two = np.sort(demands, axis=0)[:2].sum(axis=0)
    return bool(np.all(np.any(residual + tol < smallest_two[None, :], axis=1)))


def assignment_coupled_upper_bound(
    instance: AssignmentInstance,
    cache: DestroyRepairCache,
    assigned_hosts: np.ndarray,
    residual_capacity: np.ndarray,
    tol: float = 1e-9,
) -> float | None:
    """Coupled bound, or None when the neighborhood is not one-to-one."""
    assigned_hosts = np.asarray(assigned_hosts, dtype=int)
    residual = np.asarray(residual_capacity, dtype=float)
    assigned = np.flatnonzero(assigned_hosts >= 0)
    unassigned = np.flatnonzero(assigned_hosts < 0)
    if not is_one_to_one(instance, cache, unassigned, residual, tol):
        return None

    exact = 0.0
    for a in assigned:
        exact += float(cache.external_gain[a, assigned_hosts[a]])
    for pos, a in enumerate(assigned):
        for b in assigned[pos + 1:]:
            exact += float(canonical_pair_gain(cache, int(a), int(b), int(assigned_hosts[a]), int(assigned_hosts[b])))

    m = residual.shape[0]
    feasible = np.zeros((unassigned.size, m), dtype=bool)
    for row, u in enumerate(unassigned):
        feasible[row] = np.all(residual + tol >= instance.demands[cache.nodes[u]][None, :], axis=1)
        if not feasible[row].any():
            return float("-inf")

    hosts = np.arange(m)
    lmat = np.full((unassigned.size, m), -np.inf)
    for row, u in enumerate(unassigned):
        values = cache.external_gain[u].astype(float).copy()
        for a in assigned:
            values += canonical_pair_gain(cache, int(a), int(u), int(assigned_hosts[a]), hosts)
        half_pairs = np.zeros(m)
        for col, v in enumerate(unassigned):
            if v == u:
                continue
            pair = np.asarray(canonical_pair_gain(cache, int(u), int(v), hosts[:, None], hosts[None, :]), dtype=float)
            pair = np.where(feasible[col][None, :], pair, -np.inf)
            np.fill_diagonal(pair, -np.inf)  # y_v != y_u
            best = pair.max(axis=1)
            if not np.all(np.isfinite(best[feasible[row]])):
                # u on h leaves v no distinct feasible host: that pairing is impossible.
                best = np.where(np.isfinite(best), best, -np.inf)
            half_pairs += 0.5 * best
        lmat[row] = np.where(feasible[row], values + half_pairs, -np.inf)

    finite = np.isfinite(lmat)
    if not finite.any(axis=1).all():
        return float("-inf")
    big = 1.0 + float(np.abs(lmat[finite]).max()) * (unassigned.size + 1)
    cost = np.where(finite, -lmat, big)
    rows, cols = linear_sum_assignment(cost)
    if not np.all(finite[rows, cols]):
        return float("-inf")
    return float(exact + lmat[rows, cols].sum())


def bound_for_mode(mode: str, instance, cache, assigned_hosts, residual, tol) -> float:
    independent = float(partial_assignment_upper_bound(instance, cache, assigned_hosts, residual, tol=tol))
    if mode == "independent":
        return independent
    coupled = assignment_coupled_upper_bound(instance, cache, assigned_hosts, residual, tol=tol)
    if coupled is None:
        return independent
    if mode == "coupled":
        return coupled
    if mode == "min":
        return min(independent, coupled)
    raise ValueError(f"unknown bound mode {mode!r}")
