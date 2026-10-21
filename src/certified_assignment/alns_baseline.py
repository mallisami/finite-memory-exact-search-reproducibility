from __future__ import annotations

from dataclasses import dataclass
import time
import numpy as np

from .instance import AssignmentInstance
from .objective import assignment_cost
from .feasibility import is_feasible
from .destroy_repair_analysis import apply_repair, build_destroy_repair_cache, repair_gain


@dataclass(frozen=True)
class ALNSResult:
    placement: np.ndarray
    initial_objective: float
    final_objective: float
    iterations: int
    accepted_moves: int
    elapsed_ms: float
    destroy_weights: tuple[float, ...]
    repair_weights: tuple[float, ...]

    @property
    def reduction_pct(self) -> float:
        if self.initial_objective <= 0:
            return 0.0
        return 100.0 * (self.initial_objective - self.final_objective) / self.initial_objective


def _incident_cost(instance: AssignmentInstance, placement: np.ndarray) -> np.ndarray:
    n = instance.n_nodes
    out = np.zeros(n, dtype=float)
    for i in range(n):
        hi = int(placement[i])
        out[i] = float(
            np.sum(instance.interaction[i] * instance.host_cost[hi, placement])
            + np.sum(instance.interaction[:, i] * instance.host_cost[placement, hi])
        )
    return out


def _destroy_random(instance: AssignmentInstance, placement: np.ndarray, k: int, rng: np.random.Generator) -> tuple[int, ...]:
    return tuple(sorted(int(i) for i in rng.choice(instance.n_nodes, size=k, replace=False)))


def _destroy_costly(instance: AssignmentInstance, placement: np.ndarray, k: int, rng: np.random.Generator) -> tuple[int, ...]:
    scores = _incident_cost(instance, placement)
    noise = rng.uniform(0.9, 1.1, size=scores.size)
    return tuple(sorted(int(i) for i in np.argsort(-(scores * noise))[:k]))


def _destroy_affinity(instance: AssignmentInstance, placement: np.ndarray, k: int, rng: np.random.Generator) -> tuple[int, ...]:
    anchor = int(rng.integers(instance.n_nodes))
    affinity = instance.interaction[anchor] + instance.interaction[:, anchor]
    order = np.argsort(-affinity)
    chosen = [anchor]
    for node in order:
        if int(node) != anchor:
            chosen.append(int(node))
        if len(chosen) == k:
            break
    return tuple(sorted(chosen))


def _repair_greedy(instance: AssignmentInstance, placement: np.ndarray, nodes: tuple[int, ...], rng: np.random.Generator) -> tuple[tuple[int, ...], float]:
    cache = build_destroy_repair_cache(instance, placement, nodes)
    k = cache.size
    residual = cache.residual_capacity.copy()
    assigned = np.full(k, -1, dtype=int)
    order = list(range(k))
    rng.shuffle(order)
    order.sort(key=lambda a: -float(np.max(instance.demands[cache.nodes[a]] / np.maximum(instance.capacities.max(axis=0), 1e-9))))
    for local in order:
        node = cache.nodes[local]
        feasible = np.flatnonzero(np.all(residual + 1e-9 >= instance.demands[node][None, :], axis=1))
        if feasible.size == 0:
            return tuple(int(h) for h in cache.original_hosts), 0.0
        values = cache.external_gain[local, feasible].astype(float).copy()
        for other in np.flatnonzero(assigned >= 0):
            h_other = int(assigned[other])
            if other < local:
                values += cache.pair_gain[other, local, h_other, feasible]
            else:
                values += cache.pair_gain[local, other, feasible, h_other]
        host = int(feasible[int(np.argmax(values))])
        assigned[local] = host
        residual[host] -= instance.demands[node]
    return tuple(int(h) for h in assigned), float(repair_gain(cache, assigned))


def _repair_regret2(instance: AssignmentInstance, placement: np.ndarray, nodes: tuple[int, ...], rng: np.random.Generator) -> tuple[tuple[int, ...], float]:
    cache = build_destroy_repair_cache(instance, placement, nodes)
    residual = cache.residual_capacity.copy()
    assigned = np.full(cache.size, -1, dtype=int)
    remaining = set(range(cache.size))
    while remaining:
        best_local = None
        best_host = None
        best_regret = -np.inf
        best_value = -np.inf
        for local in remaining:
            node = cache.nodes[local]
            feasible = np.flatnonzero(np.all(residual + 1e-9 >= instance.demands[node][None, :], axis=1))
            if feasible.size == 0:
                return tuple(int(h) for h in cache.original_hosts), 0.0
            values = cache.external_gain[local, feasible].astype(float).copy()
            for other in np.flatnonzero(assigned >= 0):
                h_other = int(assigned[other])
                if other < local:
                    values += cache.pair_gain[other, local, h_other, feasible]
                else:
                    values += cache.pair_gain[local, other, feasible, h_other]
            order = np.argsort(-values)
            top = float(values[order[0]])
            second = float(values[order[1]]) if order.size > 1 else top - 1e6
            regret = top - second
            # Small stochastic tie breaking is conventional in ALNS-style repair.
            key = regret + 1e-9 * rng.random()
            if key > best_regret or (abs(key - best_regret) < 1e-12 and top > best_value):
                best_regret = key
                best_value = top
                best_local = int(local)
                best_host = int(feasible[order[0]])
        assert best_local is not None and best_host is not None
        assigned[best_local] = best_host
        residual[best_host] -= instance.demands[cache.nodes[best_local]]
        remaining.remove(best_local)
    return tuple(int(h) for h in assigned), float(repair_gain(cache, assigned))


def adaptive_lns(
    instance: AssignmentInstance,
    initial_placement: np.ndarray,
    destroy_size: int = 5,
    time_limit_s: float = 1.0,
    seed: int = 0,
    reaction: float = 0.2,
    cooling: float = 0.995,
) -> ALNSResult:
    if destroy_size < 2 or destroy_size > instance.n_nodes:
        raise ValueError("invalid destroy_size")
    if time_limit_s <= 0:
        raise ValueError("time_limit_s must be positive")
    p = instance.validate_placement(initial_placement).copy()
    if not is_feasible(instance, p):
        raise ValueError("initial placement must be feasible")
    rng = np.random.default_rng(seed)
    destroy_ops = (_destroy_random, _destroy_costly, _destroy_affinity)
    repair_ops = (_repair_greedy, _repair_regret2)
    dw = np.ones(len(destroy_ops), dtype=float)
    rw = np.ones(len(repair_ops), dtype=float)
    start = time.perf_counter()
    initial = float(assignment_cost(instance, p))
    current = initial
    best_p = p.copy()
    best = current
    accepted = 0
    iterations = 0
    temperature = max(1e-9, 0.01 * initial)

    while time.perf_counter() - start < time_limit_s:
        iterations += 1
        di = int(rng.choice(len(dw), p=dw / dw.sum()))
        ri = int(rng.choice(len(rw), p=rw / rw.sum()))
        nodes = destroy_ops[di](instance, p, destroy_size, rng)
        target, gain = repair_ops[ri](instance, p, nodes, rng)
        cache = build_destroy_repair_cache(instance, p, nodes)
        q = apply_repair(p, cache, target)
        if not is_feasible(instance, q):
            raise AssertionError("ALNS repair produced infeasible placement")
        q_cost = float(assignment_cost(instance, q))
        delta = q_cost - current
        accept = delta < 0 or rng.random() < np.exp(-max(0.0, delta) / max(temperature, 1e-12))
        score = 0.0
        if accept:
            p = q
            current = q_cost
            accepted += 1
            score = 1.0
            if current < best - 1e-9:
                best = current
                best_p = p.copy()
                score = 5.0
        dw[di] = (1.0 - reaction) * dw[di] + reaction * max(0.1, score)
        rw[ri] = (1.0 - reaction) * rw[ri] + reaction * max(0.1, score)
        temperature *= cooling

    elapsed = (time.perf_counter() - start) * 1000.0
    return ALNSResult(
        best_p,
        initial,
        best,
        iterations,
        accepted,
        float(elapsed),
        tuple(float(x) for x in dw),
        tuple(float(x) for x in rw),
    )
