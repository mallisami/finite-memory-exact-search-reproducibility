from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable
import numpy as np

from .instance import AssignmentInstance
from .feasibility import resource_usage


@dataclass(frozen=True)
class DestroyRepairCache:
    """Exact decomposition for a fixed destroy set.

    For destroyed nodes S, every repair gain can be written as the sum of:
      * one external term per destroyed node, covering edges to fixed nodes;
      * one internal pair term per unordered pair of destroyed nodes.

    Positive values are improvements (old objective minus new objective).
    """

    nodes: tuple[int, ...]
    original_hosts: np.ndarray
    residual_capacity: np.ndarray
    external_gain: np.ndarray       # (k, m)
    pair_gain: np.ndarray           # (k, k, m, m), only entries a < b are used

    @property
    def size(self) -> int:
        return len(self.nodes)


def canonical_pair_gain(
    cache: DestroyRepairCache,
    a: int,
    b: int,
    host_a: int | np.ndarray,
    host_b: int | np.ndarray,
):
    """Return the unordered-pair gain with a canonical index convention.

    The cache stores values only for ``a < b``.  This helper makes the
    mathematical convention explicit: reversing the local node order also
    reverses the host arguments, so the returned value is always the true
    contribution for the ordered tuple ``(a, host_a), (b, host_b)``.
    """
    if a == b:
        raise ValueError("pair endpoints must be distinct")
    if a < b:
        return cache.pair_gain[a, b, host_a, host_b]
    return cache.pair_gain[b, a, host_b, host_a]


@dataclass(frozen=True)
class PlacementCostCache:
    """Reusable per-placement node-to-host incident communication costs.

    ``node_host_cost[i,h]`` is the total directed objective contribution of all
    edges incident to node ``i`` if only that node were assigned to host ``h``
    while every other node stayed at its current host. The cache lets many
    overlapping destroy sets avoid repeated O(k*m*n) fixed-node scans.
    """

    placement: np.ndarray
    node_host_cost: np.ndarray


def build_placement_cost_cache(
    instance: AssignmentInstance,
    placement: np.ndarray,
) -> PlacementCostCache:
    p = instance.validate_placement(placement)
    onehot = np.zeros((instance.n_nodes, instance.n_hosts), dtype=float)
    onehot[np.arange(instance.n_nodes), p] = 1.0
    outgoing_by_host = instance.interaction @ onehot
    incoming_by_host = instance.interaction.T @ onehot
    node_host_cost = outgoing_by_host @ instance.host_cost.T
    node_host_cost += incoming_by_host @ instance.host_cost
    return PlacementCostCache(p.copy(), node_host_cost)


@dataclass(frozen=True)
class RepairMove:
    nodes: tuple[int, ...]
    target_hosts: tuple[int, ...]
    gain: float

    @property
    def delta_cost(self) -> float:
        return -float(self.gain)

    @property
    def improvement(self) -> float:
        return max(0.0, float(self.gain))


def normalize_destroy_nodes(instance: AssignmentInstance, nodes: Iterable[int]) -> tuple[int, ...]:
    out = tuple(sorted({int(i) for i in nodes}))
    if not out:
        raise ValueError("destroy set must contain at least one node")
    if any(i < 0 or i >= instance.n_nodes for i in out):
        raise ValueError("destroy set contains an invalid node")
    return out


def build_destroy_repair_cache(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: Iterable[int],
    placement_cost_cache: PlacementCostCache | None = None,
) -> DestroyRepairCache:
    p = instance.validate_placement(placement)
    destroy = normalize_destroy_nodes(instance, nodes)
    k, m = len(destroy), instance.n_hosts
    destroy_array = np.asarray(destroy, dtype=int)
    destroyed_mask = np.zeros(instance.n_nodes, dtype=bool)
    destroyed_mask[destroy_array] = True
    fixed = np.flatnonzero(~destroyed_mask)

    usage = resource_usage(instance, p)
    residual = instance.capacities - usage
    for node in destroy:
        residual[p[node]] += instance.demands[node]

    external_gain = np.zeros((k, m), dtype=float)
    if placement_cost_cache is not None:
        if not np.array_equal(placement_cost_cache.placement, p):
            raise ValueError("placement_cost_cache does not match placement")
        # Start from the gain obtained by moving each destroyed node while all
        # other nodes remain at their original hosts, then remove the unilateral
        # contributions of edges to other destroyed nodes. This leaves exactly
        # the interaction with fixed nodes, matching the direct construction.
        for a, node in enumerate(destroy):
            old_host = int(p[node])
            full_gain = (
                placement_cost_cache.node_host_cost[node, old_host]
                - placement_cost_cache.node_host_cost[node]
            )
            values = full_gain.astype(float).copy()
            for other in destroy:
                if other == node:
                    continue
                old_other = int(p[other])
                old_pair = (
                    instance.interaction[node, other] * instance.host_cost[old_host, old_other]
                    + instance.interaction[other, node] * instance.host_cost[old_other, old_host]
                )
                new_pair = (
                    instance.interaction[node, other] * instance.host_cost[:, old_other]
                    + instance.interaction[other, node] * instance.host_cost[old_other, :]
                )
                values -= old_pair - new_pair
            external_gain[a] = values
    else:
        for a, node in enumerate(destroy):
            old_host = int(p[node])
            if fixed.size == 0:
                continue
            fixed_hosts = p[fixed]
            out_w = instance.interaction[node, fixed]
            in_w = instance.interaction[fixed, node]
            old_external = float(
                np.sum(out_w * instance.host_cost[old_host, fixed_hosts])
                + np.sum(in_w * instance.host_cost[fixed_hosts, old_host])
            )
            for host in range(m):
                new_external = float(
                    np.sum(out_w * instance.host_cost[host, fixed_hosts])
                    + np.sum(in_w * instance.host_cost[fixed_hosts, host])
                )
                external_gain[a, host] = old_external - new_external

    pair_gain = np.zeros((k, k, m, m), dtype=float)
    for a in range(k):
        i = destroy[a]
        old_i = int(p[i])
        for b in range(a + 1, k):
            j = destroy[b]
            old_j = int(p[j])
            old_pair = (
                instance.interaction[i, j] * instance.host_cost[old_i, old_j]
                + instance.interaction[j, i] * instance.host_cost[old_j, old_i]
            )
            for hi in range(m):
                for hj in range(m):
                    new_pair = (
                        instance.interaction[i, j] * instance.host_cost[hi, hj]
                        + instance.interaction[j, i] * instance.host_cost[hj, hi]
                    )
                    pair_gain[a, b, hi, hj] = old_pair - new_pair

    return DestroyRepairCache(
        nodes=destroy,
        original_hosts=p[destroy_array].copy(),
        residual_capacity=residual,
        external_gain=external_gain,
        pair_gain=pair_gain,
    )


def repair_gain(cache: DestroyRepairCache, target_hosts: Iterable[int]) -> float:
    hosts = np.asarray(tuple(int(h) for h in target_hosts), dtype=int)
    if hosts.shape != (cache.size,):
        raise ValueError(f"target_hosts must have length {cache.size}")
    if np.any(hosts < 0) or np.any(hosts >= cache.residual_capacity.shape[0]):
        raise ValueError("target_hosts contains an invalid host")

    gain = float(np.sum(cache.external_gain[np.arange(cache.size), hosts]))
    for a in range(cache.size):
        for b in range(a + 1, cache.size):
            gain += float(cache.pair_gain[a, b, hosts[a], hosts[b]])
    return gain


def repair_is_feasible(
    instance: AssignmentInstance,
    cache: DestroyRepairCache,
    target_hosts: Iterable[int],
    tol: float = 1e-9,
) -> bool:
    hosts = np.asarray(tuple(int(h) for h in target_hosts), dtype=int)
    if hosts.shape != (cache.size,):
        return False
    residual = cache.residual_capacity.copy()
    for local, host in enumerate(hosts):
        residual[host] -= instance.demands[cache.nodes[local]]
        if np.any(residual[host] < -tol):
            return False
    return True


def apply_repair(
    placement: np.ndarray,
    cache: DestroyRepairCache,
    target_hosts: Iterable[int],
) -> np.ndarray:
    hosts = tuple(int(h) for h in target_hosts)
    if len(hosts) != cache.size:
        raise ValueError("target_hosts length mismatch")
    q = np.asarray(placement, dtype=int).copy()
    for node, host in zip(cache.nodes, hosts):
        q[node] = host
    return q


def partial_assignment_upper_bound(
    instance: AssignmentInstance,
    cache: DestroyRepairCache,
    assigned_hosts: np.ndarray,
    residual_capacity: np.ndarray,
    tol: float = 1e-9,
) -> float:
    """Admissible upper bound for any completion of a partial repair.

    ``assigned_hosts[a]`` is -1 for an unassigned destroyed node. The bound is
    formed from exact contributions among assigned nodes, independent maxima
    for every unassigned node (including interactions with assigned nodes), and
    independent maxima for every pair of unassigned nodes. Capacity competition
    among different unassigned nodes is deliberately relaxed, so the expression
    can overestimate but cannot underestimate the best feasible completion.
    """
    assigned_hosts = np.asarray(assigned_hosts, dtype=int)
    if assigned_hosts.shape != (cache.size,):
        raise ValueError("assigned_hosts shape mismatch")
    residual = np.asarray(residual_capacity, dtype=float)
    if residual.shape != cache.residual_capacity.shape:
        raise ValueError("residual_capacity shape mismatch")

    assigned = np.flatnonzero(assigned_hosts >= 0)
    unassigned = np.flatnonzero(assigned_hosts < 0)

    exact = 0.0
    for a in assigned:
        exact += float(cache.external_gain[a, assigned_hosts[a]])
    for pos, a in enumerate(assigned):
        for b in assigned[pos + 1:]:
            exact += float(canonical_pair_gain(
                cache, int(a), int(b),
                int(assigned_hosts[a]), int(assigned_hosts[b])
            ))

    feasible_hosts: dict[int, np.ndarray] = {}
    node_upper = 0.0
    for u in unassigned:
        node = cache.nodes[u]
        hosts = np.flatnonzero(
            np.all(residual + tol >= instance.demands[node][None, :], axis=1)
        )
        if hosts.size == 0:
            return float("-inf")
        feasible_hosts[int(u)] = hosts
        values = cache.external_gain[u, hosts].astype(float).copy()
        for a in assigned:
            h_assigned = int(assigned_hosts[a])
            values += canonical_pair_gain(
                cache, int(a), int(u), h_assigned, hosts
            )
        node_upper += float(np.max(values))

    pair_upper = 0.0
    for pos, a in enumerate(unassigned):
        ha = feasible_hosts[int(a)]
        for b in unassigned[pos + 1:]:
            hb = feasible_hosts[int(b)]
            values = canonical_pair_gain(
                cache, int(a), int(b), ha[:, None], hb[None, :]
            )
            pair_upper += float(np.max(values))

    return float(exact + node_upper + pair_upper)


def exhaustive_best_repair(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: Iterable[int],
    tol: float = 1e-12,
) -> tuple[RepairMove, int, int]:
    """Enumerate all host assignments for one destroy set exactly."""
    cache = build_destroy_repair_cache(instance, placement, nodes)
    best = RepairMove(cache.nodes, tuple(cache.original_hosts.tolist()), 0.0)
    total = 0
    feasible = 0
    for hosts in product(range(instance.n_hosts), repeat=cache.size):
        total += 1
        if not repair_is_feasible(instance, cache, hosts):
            continue
        feasible += 1
        gain = repair_gain(cache, hosts)
        if gain > best.gain + tol:
            best = RepairMove(cache.nodes, tuple(int(h) for h in hosts), float(gain))
    return best, total, feasible
