from __future__ import annotations

from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .instance import AssignmentInstance
from .destroy_repair_analysis import (
    DestroyRepairCache,
    RepairMove,
    build_destroy_repair_cache,
    repair_gain,
    repair_is_feasible,
)


@dataclass(frozen=True)
class RepairMILPResult:
    move: RepairMove
    status: str
    success: bool
    optimal: bool
    elapsed_ms: float
    lower_bound_gain: float | None
    dual_bound_gain: float | None
    mip_gap: float | None
    message: str
    n_binary_variables: int
    n_product_variables: int
    n_constraints: int
    radius: int | None


def _solve_cache_milp(
    instance: AssignmentInstance,
    cache: DestroyRepairCache,
    time_limit_s: float,
    mip_rel_gap: float,
    radius: int | None,
) -> RepairMILPResult:
    if time_limit_s <= 0:
        raise ValueError("time_limit_s must be positive")
    if mip_rel_gap < 0:
        raise ValueError("mip_rel_gap must be non-negative")
    k, m = cache.size, instance.n_hosts
    if radius is not None and (radius < 0 or radius > k):
        raise ValueError("radius must lie in [0, destroy_size]")

    pairs = [(a, b) for a in range(k) for b in range(a + 1, k)]
    x_count = k * m
    y_count = len(pairs) * m * m
    total = x_count + y_count

    def x_idx(a: int, h: int) -> int:
        return a * m + h

    def y_idx(p: int, h: int, g: int) -> int:
        return x_count + p * m * m + h * m + g

    # scipy.milp minimizes. Negate exact repair gain to maximize it.
    c = np.zeros(total, dtype=float)
    for a in range(k):
        for h in range(m):
            c[x_idx(a, h)] = -float(cache.external_gain[a, h])
    for p, (a, b) in enumerate(pairs):
        for h in range(m):
            for g in range(m):
                c[y_idx(p, h, g)] = -float(cache.pair_gain[a, b, h, g])

    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    row = 0

    # Exactly one host per destroyed node.
    for a in range(k):
        for h in range(m):
            rows.append(row); cols.append(x_idx(a, h)); data.append(1.0)
        lower.append(1.0); upper.append(1.0); row += 1

    # Residual multi-resource capacities after removing destroyed nodes.
    for h in range(m):
        for r in range(instance.n_resources):
            for a, node in enumerate(cache.nodes):
                val = float(instance.demands[node, r])
                if val != 0:
                    rows.append(row); cols.append(x_idx(a, h)); data.append(val)
            lower.append(-np.inf)
            upper.append(float(cache.residual_capacity[h, r]))
            row += 1

    # Optional local-branching constraint: at most radius nodes change host.
    if radius is not None:
        for a, old_h in enumerate(cache.original_hosts):
            rows.append(row); cols.append(x_idx(a, int(old_h))); data.append(1.0)
        lower.append(float(k - radius)); upper.append(np.inf); row += 1

    # Exact McCormick linearization for pair products.
    for p, (a, b) in enumerate(pairs):
        for h in range(m):
            xa = x_idx(a, h)
            for g in range(m):
                xb = x_idx(b, g)
                y = y_idx(p, h, g)
                # y <= xa
                rows.extend((row, row)); cols.extend((y, xa)); data.extend((1.0, -1.0))
                lower.append(-np.inf); upper.append(0.0); row += 1
                # y <= xb
                rows.extend((row, row)); cols.extend((y, xb)); data.extend((1.0, -1.0))
                lower.append(-np.inf); upper.append(0.0); row += 1
                # y >= xa + xb - 1
                rows.extend((row, row, row)); cols.extend((xa, xb, y)); data.extend((1.0, 1.0, -1.0))
                lower.append(-np.inf); upper.append(1.0); row += 1

    A = coo_matrix((data, (rows, cols)), shape=(row, total)).tocsr()
    constraint = LinearConstraint(A, np.asarray(lower), np.asarray(upper))
    integrality = np.zeros(total, dtype=int)
    integrality[:x_count] = 1

    start = time.perf_counter()
    result = milp(
        c,
        integrality=integrality,
        bounds=Bounds(np.zeros(total), np.ones(total)),
        constraints=constraint,
        options={"time_limit": float(time_limit_s), "mip_rel_gap": float(mip_rel_gap)},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    status_map = {0: "optimal", 1: "limit_reached", 2: "infeasible", 3: "unbounded", 4: "solver_error"}
    status = status_map.get(int(result.status), f"status_{result.status}")
    target = tuple(int(h) for h in cache.original_hosts)
    gain = 0.0
    if result.x is not None:
        x = np.asarray(result.x[:x_count]).reshape(k, m)
        candidate = tuple(int(v) for v in np.argmax(x, axis=1))
        if repair_is_feasible(instance, cache, candidate):
            target = candidate
            gain = float(repair_gain(cache, candidate))
        else:
            raise AssertionError("repair MILP produced an infeasible assignment")

    # We expose a conservative gain lower bound derived from the primal-dual data.
    # For minimization of -gain, mip_dual_bound <= optimum(-gain), hence
    # -mip_dual_bound >= optimum gain: this is an upper bound on gain, not a lower
    # bound. To avoid misleading semantics, only exact optimal runs report gain.
    exact_gain = gain if int(result.status) == 0 else None
    gap = getattr(result, "mip_gap", None)
    # scipy's HiGHS backend reports a dual bound on its minimization objective
    # even when the time limit is hit before proving optimality (branch-and-bound
    # node bound). Since we minimize -gain, -mip_dual_bound is a valid *upper*
    # bound on the achievable gain -- exactly the certificate quantity this paper
    # reports as "HiGHS exposed a valid residual bound", available independent of
    # whether HiGHS proved optimality.
    raw_dual_bound = getattr(result, "mip_dual_bound", None)
    dual_bound_gain = (
        -float(raw_dual_bound)
        if raw_dual_bound is not None and np.isfinite(raw_dual_bound)
        else None
    )
    move = RepairMove(cache.nodes, target, max(0.0, gain))
    return RepairMILPResult(
        move=move,
        status=status,
        success=bool(result.success),
        optimal=bool(int(result.status) == 0),
        elapsed_ms=float(elapsed_ms),
        lower_bound_gain=None if exact_gain is None else float(exact_gain),
        dual_bound_gain=dual_bound_gain,
        mip_gap=None if gap is None else float(gap),
        message=str(result.message),
        n_binary_variables=x_count,
        n_product_variables=y_count,
        n_constraints=row,
        radius=radius,
    )


def solve_repair_milp(
    instance: AssignmentInstance,
    placement: np.ndarray,
    nodes: tuple[int, ...] | list[int],
    time_limit_s: float = 30.0,
    mip_rel_gap: float = 0.0,
    radius: int | None = None,
    prebuilt_cache: DestroyRepairCache | None = None,
) -> RepairMILPResult:
    cache = prebuilt_cache or build_destroy_repair_cache(instance, placement, nodes)
    return _solve_cache_milp(instance, cache, time_limit_s, mip_rel_gap, radius)
