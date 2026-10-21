"""Rigorous binary64 rounding envelopes for the PCR repair search.

Safe mode keeps binary64 arithmetic in the search but makes every emitted
certificate a proven upper bound on the exact residual gap of the stored
binary64 inputs.  It relies on the standard floating-point model
``fl(a op b) = (a op b)(1 + d), |d| <= u`` with ``u = 2**-53`` and on the
classical bound for a sum or dot product of N terms computed in any order
(including blocked BLAS kernels and fused multiply-add):

    |fl(sum x_i) - sum x_i| <= gamma(N) * sum |x_i|,   gamma(N) = N u / (1 - N u).

Because every interaction weight and host cost is non-negative, the magnitude
of every intermediate quantity in the repair cache is bounded by incident
interaction volume times the largest host cost.  This gives one constant per
destroy set, ``delta``, that bounds the rounding error of any partial-repair
bound (Equation 14) or complete-repair gain evaluated from that cache.  The
envelope is conservative; its size relative to the gains is reported by the
experiments.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

import numpy as np

from .destroy_repair_analysis import DestroyRepairCache
from .instance import AssignmentInstance

UNIT_ROUNDOFF = 2.0 ** -53
# Relative inflation applied to every envelope computed in floating point, so
# that rounding in the envelope arithmetic itself cannot shrink it.
_ENVELOPE_INFLATION = 1.0 + 1e-10


def gamma(n: int) -> float:
    """Higham's gamma_n; valid while n * u < 1."""
    nu = n * UNIT_ROUNDOFF
    if nu >= 0.5:
        raise ValueError(f"gamma({n}) exceeds the range of the rounding model")
    return nu / (1.0 - nu)


@dataclass(frozen=True)
class SafeEnvelope:
    """Per-destroy-set rounding envelope and exact capacity data.

    ``delta`` bounds |computed - exact| for any partial-repair upper bound or
    complete-repair gain evaluated from the cache.  ``residual_slack`` bounds
    the rounding error of any residual capacity entry carried by the search,
    so ``demand <= residual + residual_slack`` admits a superset of the hosts
    that are feasible in exact arithmetic.  ``exact_residual`` holds the exact
    rational residual capacity left by the fixed nodes.
    """

    delta: float
    residual_slack: float
    exact_residual: tuple[tuple[Fraction, ...], ...]
    exact_demands: tuple[tuple[Fraction, ...], ...]


def build_safe_envelope(
    instance: AssignmentInstance,
    placement: np.ndarray,
    cache: DestroyRepairCache,
) -> SafeEnvelope:
    n, m, k = instance.n_nodes, instance.n_hosts, cache.size
    nodes = np.asarray(cache.nodes, dtype=int)
    w = instance.interaction
    c_max = float(np.max(instance.host_cost)) if instance.host_cost.size else 0.0

    # Incident interaction volume of each destroyed node (both directions).
    incident = w[nodes].sum(axis=1) + w[:, nodes].sum(axis=0)
    incident_max = float(np.max(incident)) * (1.0 + gamma(2 * n))

    # External gains: every intermediate is a signed combination of dot
    # products of length <= n (fixed-node scan) or n then m (placement-cost
    # path), plus <= 2k corrections, each of magnitude <= 2 * incident * c_max.
    e_err = gamma(2 * (n + m) + 4 * k + 8) * 4.0 * incident_max * c_max
    pair_weight = 0.0
    if k >= 2:
        sub = w[np.ix_(nodes, nodes)]
        pair_weight = float(np.max(sub + sub.T))
    p_err = gamma(8) * 2.0 * pair_weight * c_max

    n_pairs = k * (k - 1) // 2
    terms = k + n_pairs
    e_mag = float(np.max(np.abs(cache.external_gain))) + e_err
    p_mag = 0.0
    if k >= 2:
        upper = np.triu_indices(k, 1)
        p_mag = float(np.max(np.abs(cache.pair_gain[upper]))) + p_err
    # Entry errors plus the error of adding up to ~2*terms computed values,
    # each bounded by its magnitude.
    delta = k * e_err + n_pairs * p_err + gamma(2 * terms + 4) * (k * e_mag + n_pairs * p_mag)

    demand_total = float(np.max(instance.demands.sum(axis=0))) if instance.demands.size else 0.0
    cap_max = float(np.max(instance.capacities)) if instance.capacities.size else 0.0
    residual_slack = gamma(n + 2 * k + 4) * (cap_max + demand_total)

    p = np.asarray(placement, dtype=int)
    destroyed = set(int(v) for v in cache.nodes)
    exact_residual = [[Fraction(float(v)) for v in row] for row in instance.capacities]
    for i in range(n):
        if i in destroyed:
            continue
        row = exact_residual[int(p[i])]
        for r, d in enumerate(instance.demands[i]):
            row[r] -= Fraction(float(d))
    exact_demands = tuple(
        tuple(Fraction(float(d)) for d in instance.demands[node]) for node in cache.nodes
    )

    return SafeEnvelope(
        delta=float(delta) * _ENVELOPE_INFLATION,
        residual_slack=float(residual_slack) * _ENVELOPE_INFLATION,
        exact_residual=tuple(tuple(row) for row in exact_residual),
        exact_demands=exact_demands,
    )


def exact_repair_feasible(envelope: SafeEnvelope, target_hosts: Iterable[int]) -> bool:
    """Capacity feasibility of a complete repair in exact rational arithmetic."""
    residual = [list(row) for row in envelope.exact_residual]
    for local, host in enumerate(target_hosts):
        row = residual[int(host)]
        for r, d in enumerate(envelope.exact_demands[local]):
            row[r] -= d
            if row[r] < 0:
                return False
    return True
