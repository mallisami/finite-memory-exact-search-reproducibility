from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence
import hashlib, math
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

@dataclass(frozen=True)
class MDKPInstance:
    profits: np.ndarray          # (n,)
    weights: np.ndarray          # (d,n)
    capacities: np.ndarray       # (d,)
    seed: int

    @property
    def n_items(self) -> int:
        return int(self.profits.size)

    @property
    def n_dims(self) -> int:
        return int(self.capacities.size)

    @property
    def fingerprint(self) -> str:
        h=hashlib.sha256()
        for a in (self.profits,self.weights,self.capacities):
            h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()

@dataclass
class SearchNode:
    pos: int
    remaining: tuple[int, ...]
    profit: int
    bits: int

@dataclass
class MDKPCheckpoint:
    context: tuple[int, ...]
    order: tuple[int, ...]
    frontier: list[SearchNode]
    best_profit: int
    best_bits: int
    residual: tuple[int, ...]
    invested_nodes: int
    instance_fingerprint: str
    exact: bool = False


def make_instance(n_items: int, seed: int, n_dims: int = 3) -> MDKPInstance:
    """Generate a deterministic MDKP instance with correlated integer weights."""
    rng=np.random.default_rng(int(seed))
    base=rng.integers(4,25,size=int(n_items),endpoint=False)
    weights=[]
    for j in range(int(n_dims)):
        jitter=rng.integers(-3,8,size=int(n_items))
        scale=0.75+0.25*j
        weights.append(np.maximum(1,np.rint(scale*base+jitter)).astype(np.int64))
    w=np.vstack(weights).astype(np.int64)
    scarcity=(w / np.maximum(w.mean(axis=1,keepdims=True),1)).sum(axis=0)
    profits=np.rint(15 + 6*scarcity + rng.gamma(shape=2.2,scale=9.0,size=int(n_items))).astype(np.int64)
    # Tight enough to make packing nontrivial, but with many feasible combinations.
    cap=np.floor(0.34*w.sum(axis=1)).astype(np.int64)
    return MDKPInstance(profits=profits,weights=w,capacities=cap,seed=int(seed))


def objective_cost(instance: MDKPInstance, x: np.ndarray) -> float:
    """Minimization convention used by the outer controller: negative packed profit."""
    return -float(np.dot(instance.profits, np.asarray(x,dtype=np.int8)))


def feasible(instance: MDKPInstance, x: np.ndarray) -> bool:
    return bool(np.all(instance.weights @ np.asarray(x,dtype=np.int64) <= instance.capacities))


def initial_solution(instance: MDKPInstance) -> np.ndarray:
    """Deterministic greedy feasible start."""
    norm=(instance.weights/np.maximum(instance.capacities[:,None],1)).sum(axis=0)
    score=instance.profits/np.maximum(norm,1e-12)
    order=np.argsort(-score,kind='stable')
    x=np.zeros(instance.n_items,dtype=np.int8); used=np.zeros(instance.n_dims,dtype=np.int64)
    for i in order:
        wi=instance.weights[:,i]
        if np.all(used+wi<=instance.capacities):
            x[i]=1; used+=wi
    assert feasible(instance,x)
    return x


def make_context_library(n_items: int, destroy_size: int, seed: int, count: int = 18) -> tuple[tuple[int,...], ...]:
    rng=np.random.default_rng(int(seed)+101_003)
    contexts=[]; seen=set()
    # A shared core creates controlled overlap; fresh items preserve context diversity.
    core_n=max(2,int(round(0.25*destroy_size)))
    shared=np.sort(rng.choice(int(n_items),size=min(int(n_items),max(core_n*2,destroy_size)),replace=False))
    attempts=0
    while len(contexts)<int(count) and attempts<10000:
        attempts+=1
        take_core=np.sort(rng.choice(shared,size=min(core_n,len(shared)),replace=False))
        remaining=np.setdiff1d(np.arange(int(n_items)),take_core,assume_unique=False)
        extra=np.sort(rng.choice(remaining,size=int(destroy_size)-len(take_core),replace=False))
        ctx=tuple(sorted(np.concatenate([take_core,extra]).astype(int).tolist()))
        if ctx not in seen:
            seen.add(ctx); contexts.append(ctx)
    if len(contexts)<int(count):
        raise RuntimeError('could not build distinct context library')
    return tuple(contexts)


def make_context_trace(contexts: Sequence[tuple[int,...]], iterations: int, seed: int) -> tuple[tuple[tuple[int,...],int,float], ...]:
    """Exogenous recurrent context trace: (context, class, acceptance_uniform)."""
    rng=np.random.default_rng(int(seed)+909_091)
    k=len(contexts); hot=max(2,k//3); warm=max(hot+1,2*k//3)
    trace=[]; prev=None
    for _ in range(int(iterations)):
        if prev is not None and rng.random()<0.32:
            idx=prev
        else:
            u=rng.random()
            if u<0.58: idx=int(rng.integers(0,hot))
            elif u<0.88: idx=int(rng.integers(hot,warm))
            else: idx=int(rng.integers(warm,k))
        cls=0 if idx<hot else (1 if idx<warm else 2)
        trace.append((tuple(contexts[idx]),cls,float(rng.random())))
        prev=idx
    return tuple(trace)


def residual_capacity(instance: MDKPInstance, x: np.ndarray, context: Sequence[int]) -> np.ndarray:
    mask=np.ones(instance.n_items,dtype=bool); mask[np.asarray(context,dtype=int)]=False
    used=instance.weights[:,mask] @ np.asarray(x,dtype=np.int64)[mask]
    return (instance.capacities-used).astype(np.int64)


def _context_order(instance: MDKPInstance, context: Sequence[int], residual: np.ndarray) -> tuple[int,...]:
    ids=np.asarray(context,dtype=int)
    norm=(instance.weights[:,ids]/np.maximum(residual[:,None],1)).sum(axis=0)
    density=instance.profits[ids]/np.maximum(norm,1e-12)
    # Deterministic tie breaker on item id.
    idx=np.lexsort((ids,-density))
    return tuple(ids[idx].astype(int).tolist())


def _bits_profit(instance: MDKPInstance, order: Sequence[int], bits: int) -> int:
    p=0
    for pos,i in enumerate(order):
        if (bits>>pos)&1: p+=int(instance.profits[i])
    return p


def _incumbent_bits(instance: MDKPInstance, x: np.ndarray, order: Sequence[int], residual: np.ndarray) -> tuple[int,int]:
    rem=np.asarray(residual,dtype=np.int64).copy(); bits=0; p=0
    # First preserve currently selected context items when feasible, then greedily add.
    for pos,i in enumerate(order):
        if int(x[i]) and np.all(instance.weights[:,i]<=rem):
            rem-=instance.weights[:,i]; bits|=1<<pos; p+=int(instance.profits[i])
    for pos,i in enumerate(order):
        if (bits>>pos)&1: continue
        if np.all(instance.weights[:,i]<=rem):
            rem-=instance.weights[:,i]; bits|=1<<pos; p+=int(instance.profits[i])
    return bits,p


def initialize_checkpoint(instance: MDKPInstance, x: np.ndarray, context: Sequence[int]) -> MDKPCheckpoint:
    ctx=tuple(sorted(int(i) for i in context))
    residual=residual_capacity(instance,x,ctx)
    if np.any(residual<0): raise ValueError('outside assignment is infeasible')
    order=_context_order(instance,ctx,residual)
    bits,p=_incumbent_bits(instance,x,order,residual)
    root=SearchNode(pos=0,remaining=tuple(int(v) for v in residual),profit=0,bits=0)
    return MDKPCheckpoint(context=ctx,order=order,frontier=[root],best_profit=int(p),best_bits=int(bits),
                          residual=tuple(int(v) for v in residual),invested_nodes=0,
                          instance_fingerprint=instance.fingerprint,exact=False)


def checkpoint_compatible(instance: MDKPInstance, x: np.ndarray, cp: MDKPCheckpoint) -> bool:
    if cp.instance_fingerprint!=instance.fingerprint: return False
    now=tuple(int(v) for v in residual_capacity(instance,x,cp.context))
    return now==tuple(cp.residual)


def _upper_bound_1d(instance: MDKPInstance, order: Sequence[int], pos: int, remaining: tuple[int,...], dim: int) -> float:
    cap=float(remaining[dim]); ub=0.0
    items=[]
    for q in range(pos,len(order)):
        i=order[q]; w=float(instance.weights[dim,i]); p=float(instance.profits[i])
        if w<=0: ub+=p
        else: items.append((p/w,w,p))
    items.sort(reverse=True,key=lambda z:z[0])
    for _,w,p in items:
        if cap<=0: break
        if w<=cap: ub+=p; cap-=w
        else: ub+=p*(cap/w); cap=0.0
    return ub


def _upper_bound(instance: MDKPInstance, cp: MDKPCheckpoint, node: SearchNode) -> float:
    if node.pos>=len(cp.order): return float(node.profit)
    tails=[_upper_bound_1d(instance,cp.order,node.pos,node.remaining,d) for d in range(instance.n_dims)]
    return float(node.profit + min(tails))


def advance_checkpoint(instance: MDKPInstance, cp: MDKPCheckpoint, budget_nodes: int) -> tuple[int,int,int,bool]:
    """Advance a serializable DFS B&B checkpoint by at most budget_nodes node expansions.

    Returns (best_bits, best_profit, nodes_expanded_this_call, exact).
    """
    if cp.instance_fingerprint!=instance.fingerprint: raise ValueError('instance mismatch')
    expanded=0
    while cp.frontier and expanded<int(budget_nodes):
        node=cp.frontier.pop(); expanded+=1; cp.invested_nodes+=1
        if _upper_bound(instance,cp,node) <= cp.best_profit + 1e-12:
            continue
        if node.pos>=len(cp.order):
            if node.profit>cp.best_profit:
                cp.best_profit=int(node.profit); cp.best_bits=int(node.bits)
            continue
        pos=node.pos; item=cp.order[pos]; rem=np.asarray(node.remaining,dtype=np.int64)
        # Exclude branch first on stack so include branch is explored first (LIFO).
        cp.frontier.append(SearchNode(pos+1,tuple(int(v) for v in rem),int(node.profit),int(node.bits)))
        wi=instance.weights[:,item]
        if np.all(wi<=rem):
            rem2=rem-wi
            cp.frontier.append(SearchNode(pos+1,tuple(int(v) for v in rem2),
                                          int(node.profit+instance.profits[item]),
                                          int(node.bits | (1<<pos))))
    cp.exact=not cp.frontier
    return int(cp.best_bits),int(cp.best_profit),int(expanded),bool(cp.exact)


def checkpoint_solution(instance: MDKPInstance, base_x: np.ndarray, cp: MDKPCheckpoint) -> np.ndarray:
    x=np.asarray(base_x,dtype=np.int8).copy()
    x[np.asarray(cp.context,dtype=int)]=0
    for pos,i in enumerate(cp.order):
        if (cp.best_bits>>pos)&1: x[i]=1
    if not feasible(instance,x): raise AssertionError('checkpoint incumbent is infeasible')
    return x


def solve_with_highs(instance: MDKPInstance, x: np.ndarray, context: Sequence[int]) -> tuple[int,np.ndarray]:
    """Independent exact certificate for engineering tests using SciPy/HiGHS MILP."""
    ctx=np.asarray(tuple(sorted(int(i) for i in context)),dtype=int)
    resid=residual_capacity(instance,x,ctx)
    c=-instance.profits[ctx].astype(float)
    A=instance.weights[:,ctx].astype(float)
    con=LinearConstraint(A,lb=-np.inf*np.ones(instance.n_dims),ub=resid.astype(float))
    res=milp(c=c,integrality=np.ones(len(ctx),dtype=int),bounds=Bounds(np.zeros(len(ctx)),np.ones(len(ctx))),constraints=con,
             options={'time_limit':30.0,'mip_rel_gap':0.0})
    if not res.success: raise RuntimeError(f'HiGHS failed: {res.message}')
    z=np.rint(res.x).astype(np.int8)
    return int(np.dot(instance.profits[ctx],z)),z
