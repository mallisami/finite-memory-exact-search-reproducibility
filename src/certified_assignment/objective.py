from __future__ import annotations

from collections.abc import Mapping
import numpy as np

from .instance import AssignmentInstance


def assignment_cost(instance: AssignmentInstance, placement: np.ndarray) -> float:
    """Return the exact directed communication cost of a placement."""
    p = instance.validate_placement(placement)
    pair_cost = instance.host_cost[p[:, None], p[None, :]]
    return float(np.sum(instance.interaction * pair_cost))


def reassignment_delta(
    instance: AssignmentInstance,
    placement: np.ndarray,
    changes: Mapping[int, int],
) -> float:
    """Exact incremental objective change for a small reassignment.

    Returns ``new_cost - old_cost``. Negative values are improvements.

    Only directed edges whose source or destination is in ``changes`` can alter
    their cost. Each affected directed edge is counted exactly once.
    """
    p = instance.validate_placement(placement)
    if not changes:
        return 0.0

    changed_nodes = np.fromiter(changes.keys(), dtype=int)
    if np.any(changed_nodes < 0) or np.any(changed_nodes >= instance.n_nodes):
        raise ValueError("changes contains an invalid node index")
    new_hosts = np.fromiter(changes.values(), dtype=int)
    if np.any(new_hosts < 0) or np.any(new_hosts >= instance.n_hosts):
        raise ValueError("changes contains an invalid host index")

    q = p.copy()
    for node, host in changes.items():
        q[int(node)] = int(host)

    changed_mask = np.zeros(instance.n_nodes, dtype=bool)
    changed_mask[changed_nodes] = True
    affected = changed_mask[:, None] | changed_mask[None, :]

    old_pair_cost = instance.host_cost[p[:, None], p[None, :]]
    new_pair_cost = instance.host_cost[q[:, None], q[None, :]]
    return float(np.sum(instance.interaction[affected] * (new_pair_cost[affected] - old_pair_cost[affected])))
