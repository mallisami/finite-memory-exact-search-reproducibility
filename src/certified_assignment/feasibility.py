from __future__ import annotations

import numpy as np

from .instance import AssignmentInstance


def resource_usage(instance: AssignmentInstance, placement: np.ndarray) -> np.ndarray:
    """Return host-by-resource usage matrix."""
    p = instance.validate_placement(placement)
    usage = np.zeros_like(instance.capacities, dtype=float)
    np.add.at(usage, p, instance.demands)
    return usage


def is_feasible(instance: AssignmentInstance, placement: np.ndarray, tol: float = 1e-9) -> bool:
    usage = resource_usage(instance, placement)
    return bool(np.all(usage <= instance.capacities + tol))


def relocation_is_feasible(
    instance: AssignmentInstance,
    placement: np.ndarray,
    node: int,
    target_host: int,
    usage: np.ndarray | None = None,
    tol: float = 1e-9,
) -> bool:
    p = instance.validate_placement(placement)
    if not 0 <= node < instance.n_nodes:
        raise ValueError("invalid node")
    if not 0 <= target_host < instance.n_hosts:
        raise ValueError("invalid target_host")
    source = int(p[node])
    if source == target_host:
        return True
    u = resource_usage(instance, p) if usage is None else np.asarray(usage, dtype=float)
    return bool(np.all(u[target_host] + instance.demands[node] <= instance.capacities[target_host] + tol))


def swap_is_feasible(
    instance: AssignmentInstance,
    placement: np.ndarray,
    i: int,
    j: int,
    usage: np.ndarray | None = None,
    tol: float = 1e-9,
) -> bool:
    p = instance.validate_placement(placement)
    if not (0 <= i < instance.n_nodes and 0 <= j < instance.n_nodes):
        raise ValueError("invalid node index")
    hi, hj = int(p[i]), int(p[j])
    if hi == hj:
        return True
    u = resource_usage(instance, p) if usage is None else np.asarray(usage, dtype=float)
    new_hi = u[hi] - instance.demands[i] + instance.demands[j]
    new_hj = u[hj] - instance.demands[j] + instance.demands[i]
    return bool(
        np.all(new_hi <= instance.capacities[hi] + tol)
        and np.all(new_hj <= instance.capacities[hj] + tol)
    )
