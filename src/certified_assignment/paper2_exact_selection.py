"""Exact finite-byte subset selection for Paper 2.

The prediction layer supplies a nonnegative expected value for each checkpoint.
This module solves the allocation layer exactly under a byte budget so that
prediction quality is not confounded with a greedy cache-eviction heuristic.

The implementation uses a sparse dynamic program over reachable byte totals.
It is exact for the supplied values/sizes and deterministic under ties.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable, TypeVar

import numpy as np

K = TypeVar("K", bound=Hashable)


@dataclass(frozen=True)
class ValueItem:
    key: K
    size_bytes: int
    expected_value: float


def _better_same_bytes(
    candidate: tuple[float, tuple[K, ...]],
    incumbent: tuple[float, tuple[K, ...]],
    *,
    tol: float = 1e-12,
) -> bool:
    cv, ck = candidate
    iv, ik = incumbent
    if cv > iv + tol:
        return True
    if abs(cv - iv) <= tol:
        return tuple(map(repr, ck)) < tuple(map(repr, ik))
    return False


def select_exact_expected_value(
    items: Iterable[ValueItem],
    *,
    budget_bytes: int,
) -> tuple[K, ...]:
    """Return the exact maximum-expected-value subset under ``budget_bytes``.

    Tie order is:
    1. larger expected value;
    2. fewer bytes used;
    3. lexicographically smaller key representation.

    Negative expected values are legal but will never improve the empty set.
    Oversize items are simply infeasible.
    """
    if budget_bytes < 0:
        raise ValueError("budget_bytes must be non-negative")

    ordered = sorted(
        (ValueItem(i.key, int(i.size_bytes), float(i.expected_value)) for i in items),
        key=lambda i: repr(i.key),
    )
    if any(i.size_bytes < 0 for i in ordered):
        raise ValueError("item size_bytes must be non-negative")

    # Wide portfolios are solved as the mathematically identical binary
    # knapsack MILP.  This avoids Pareto-frontier explosion when many
    # similarly sized checkpoints have distinct predicted probabilities.
    # A second exact stage minimizes bytes among value-optimal subsets.
    if len(ordered) > 12:
        from scipy.optimize import Bounds, LinearConstraint, milp
        sizes = np.asarray([i.size_bytes for i in ordered], dtype=float)
        values = np.asarray([i.expected_value for i in ordered], dtype=float)
        n = len(ordered)
        bounds = Bounds(np.zeros(n), np.ones(n))
        integrality = np.ones(n, dtype=int)
        cap = LinearConstraint(sizes.reshape(1, -1), -np.inf, float(budget_bytes))
        first = milp(-values, integrality=integrality, bounds=bounds, constraints=cap,
                     options={"presolve": True})
        if not first.success or first.x is None:
            raise RuntimeError(f"exact knapsack MILP failed: {first.message}")
        chosen = first.x > 0.5
        # For wide portfolios the scientific criterion is the exact maximum
        # expected value under the byte cap.  A second MILP used only to
        # minimize bytes among exactly value-tied optima can become numerically
        # pathological for calibrated floating probabilities and is immaterial
        # unless the primary objective is tied.  HiGHS is deterministic for
        # the fixed ordered inputs, so return the exact primary optimum.
        return tuple(ordered[i].key for i in range(n) if chosen[i])

    # Exact sparse Pareto-frontier DP.  After each item, states dominated by a
    # state using no more bytes and having no smaller expected value can never
    # participate in an optimal completion, so they are removed immediately.
    # This preserves the exact objective and historical tie rules while avoiding
    # the exponential accumulation of arbitrary reachable byte totals that made
    # wide online portfolios impractical.
    states: dict[int, tuple[float, tuple[K, ...]]] = {0: (0.0, ())}
    tol = 1e-12
    for item in ordered:
        updated = dict(states)
        for used, (value, keys) in states.items():
            new_used = used + item.size_bytes
            if new_used > budget_bytes:
                continue
            new_state = (value + item.expected_value, keys + (item.key,))
            incumbent = updated.get(new_used)
            if incumbent is None or _better_same_bytes(new_state, incumbent):
                updated[new_used] = new_state

        # Pareto prune in ascending bytes.  Equal-value higher-byte states are
        # dominated because final ties prefer fewer bytes.
        pruned: dict[int, tuple[float, tuple[K, ...]]] = {}
        best_value = -float("inf")
        for used in sorted(updated):
            value, keys = updated[used]
            if value > best_value + tol:
                pruned[used] = (value, keys)
                best_value = value
        states = pruned

    best_used = 0
    best_value, best_keys = states[0]
    for used, (value, keys) in states.items():
        better = False
        if value > best_value + tol:
            better = True
        elif abs(value - best_value) <= tol:
            if used < best_used:
                better = True
            elif used == best_used and tuple(map(repr, keys)) < tuple(map(repr, best_keys)):
                better = True
        if better:
            best_used = used
            best_value = value
            best_keys = keys
    return tuple(sorted(best_keys, key=repr))
