from __future__ import annotations
import numpy as np
from numba import njit

@njit(cache=True)
def _bound_jit(external_gain, pair_gain, nodes, demands, assigned_hosts, residual, tol):
    k = assigned_hosts.shape[0]
    m = residual.shape[0]
    rdim = residual.shape[1]
    exact = 0.0
    # exact external terms
    for a in range(k):
        ha = assigned_hosts[a]
        if ha >= 0:
            exact += external_gain[a, ha]
    # exact assigned-assigned pairs
    for a in range(k):
        ha = assigned_hosts[a]
        if ha < 0:
            continue
        for b in range(a + 1, k):
            hb = assigned_hosts[b]
            if hb >= 0:
                exact += pair_gain[a, b, ha, hb]

    feasible = np.zeros((k, m), dtype=np.uint8)
    node_upper = 0.0
    for u in range(k):
        if assigned_hosts[u] >= 0:
            continue
        node = nodes[u]
        any_feasible = False
        best = -np.inf
        for h in range(m):
            ok = True
            for rr in range(rdim):
                if residual[h, rr] + tol < demands[node, rr]:
                    ok = False
                    break
            if not ok:
                continue
            feasible[u, h] = 1
            any_feasible = True
            val = external_gain[u, h]
            for a in range(k):
                ha = assigned_hosts[a]
                if ha < 0:
                    continue
                if a < u:
                    val += pair_gain[a, u, ha, h]
                else:
                    val += pair_gain[u, a, h, ha]
            if val > best:
                best = val
        if not any_feasible:
            return -np.inf
        node_upper += best

    pair_upper = 0.0
    for a in range(k):
        if assigned_hosts[a] >= 0:
            continue
        for b in range(a + 1, k):
            if assigned_hosts[b] >= 0:
                continue
            best = -np.inf
            for ha in range(m):
                if feasible[a, ha] == 0:
                    continue
                for hb in range(m):
                    if feasible[b, hb] == 0:
                        continue
                    v = pair_gain[a, b, ha, hb]
                    if v > best:
                        best = v
            pair_upper += best
    return exact + node_upper + pair_upper

def fast_partial_assignment_upper_bound(instance, cache, assigned_hosts, residual_capacity, tol=1e-9):
    assigned_hosts = np.asarray(assigned_hosts, dtype=np.int64)
    residual = np.asarray(residual_capacity, dtype=np.float64)
    nodes = np.asarray(cache.nodes, dtype=np.int64)
    return float(_bound_jit(cache.external_gain, cache.pair_gain, nodes, instance.demands, assigned_hosts, residual, float(tol)))

def install():
    import certified_assignment.anytime_gap_certified_repair as ag
    ag.partial_assignment_upper_bound = fast_partial_assignment_upper_bound
