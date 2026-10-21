"""P10-local exact finite-byte checkpoint allocation.

This module is intentionally self-contained so the independent-domain P10 validation
does not import the original Paper-2 allocation implementation.  It solves the same
instantaneous 0/1 expected-value knapsack used by the persistence policy.
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


def _better_same_bytes(candidate, incumbent, tol: float = 1e-12) -> bool:
    cv, ck = candidate; iv, ik = incumbent
    if cv > iv + tol:
        return True
    if abs(cv - iv) <= tol:
        return tuple(map(repr, ck)) < tuple(map(repr, ik))
    return False


def select_exact_expected_value(items: Iterable[ValueItem], *, budget_bytes: int) -> tuple[K, ...]:
    """Return a globally optimal subset for the instantaneous byte-constrained value problem.

    Small pools use an exact sparse dynamic program.  Wider pools use the equivalent
    binary MILP with HiGHS through SciPy and a zero requested MIP relative gap.  Solver
    numerical tolerances still apply to floating-valued calibrated probabilities; the
    scientific comparison uses this identical allocator for learned and empirical policies.
    """
    if budget_bytes < 0:
        raise ValueError("budget_bytes must be non-negative")
    ordered = sorted((ValueItem(i.key, int(i.size_bytes), float(i.expected_value)) for i in items), key=lambda i: repr(i.key))
    if any(i.size_bytes < 0 for i in ordered):
        raise ValueError("item size_bytes must be non-negative")
    if not ordered:
        return ()

    if len(ordered) > 12:
        from scipy.optimize import Bounds, LinearConstraint, milp
        sizes=np.asarray([i.size_bytes for i in ordered],dtype=float)
        values=np.asarray([i.expected_value for i in ordered],dtype=float)
        n=len(ordered)
        res=milp(
            c=-values,
            integrality=np.ones(n,dtype=int),
            bounds=Bounds(np.zeros(n),np.ones(n)),
            constraints=LinearConstraint(sizes.reshape(1,-1),-np.inf,float(budget_bytes)),
            options={"presolve": True, "mip_rel_gap": 0.0},
        )
        if not res.success or res.x is None:
            raise RuntimeError(f"P10 exact allocation MILP failed: {res.message}")
        return tuple(ordered[i].key for i in range(n) if res.x[i] > 0.5)

    states: dict[int, tuple[float, tuple[K, ...]]] = {0:(0.0,())}
    tol=1e-12
    for item in ordered:
        updated=dict(states)
        for used,(value,keys) in states.items():
            nu=used+item.size_bytes
            if nu>budget_bytes:
                continue
            cand=(value+item.expected_value,keys+(item.key,))
            inc=updated.get(nu)
            if inc is None or _better_same_bytes(cand,inc,tol):
                updated[nu]=cand
        pruned={}; best=-float('inf')
        for used in sorted(updated):
            value,keys=updated[used]
            if value>best+tol:
                pruned[used]=(value,keys); best=value
        states=pruned

    best_used=0; best_value,best_keys=states[0]
    for used,(value,keys) in states.items():
        better=value>best_value+tol
        if not better and abs(value-best_value)<=tol:
            better=used<best_used or (used==best_used and tuple(map(repr,keys))<tuple(map(repr,best_keys)))
        if better:
            best_used,best_value,best_keys=used,value,keys
    return tuple(sorted(best_keys,key=repr))
