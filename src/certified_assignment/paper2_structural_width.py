"""P7B structural portfolio-width characterization.

Mechanistic-only characterization of natural live checkpoint portfolios across
problem scales and destroy sizes.  No objective-comparison result is returned
or used for regime selection.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from .domain_instances import make_domain_case
from .feasibility import is_feasible
from .objective import assignment_cost
from .matched_lns_controller import IterationRecord, matched_adaptive_lns
from .matched_lns_policies import make_heuristic_repair_arms
from .paper2_online_pilot import OnlineStepPolicy, ReplayTraceEntry


@dataclass
class StructuralWidthResult:
    domain: str
    instance_seed: int
    n_nodes: int
    n_hosts: int
    destroy_size: int
    iterations: int
    slice_pops: int
    trace_unique_contexts: int
    trace_recurrence_events: int
    accepted_moves: int
    useful_resumes: int
    reused_prior_branch_pops: int
    checkpoint_creations: int
    exact_retirements: int
    unfinished_return_fraction: float
    invalidation_evictions: int
    peak_active_checkpoints: int
    mean_active_checkpoints_end_iteration: float
    fraction_iterations_k_ge_2: float
    fraction_iterations_k_ge_3: float
    fraction_iterations_k_ge_4: float
    peak_bytes: int
    max_checkpoint_size_bytes: int
    max_checkpoint_fraction_of_peak: float
    median_active_checkpoint_bytes: float

    def to_dict(self):
        return dict(self.__dict__)


def generate_structural_trace(domain: str, n_nodes: int, n_hosts: int, seed: int, *,
                              iterations: int = 200, destroy_size: int = 8) -> tuple[ReplayTraceEntry, ...]:
    case = make_domain_case(domain, int(n_nodes), int(n_hosts), seed=int(seed))
    rows: list[IterationRecord] = []
    matched_adaptive_lns(
        case.instance,
        case.placement,
        make_heuristic_repair_arms(),
        destroy_size=int(destroy_size),
        max_iterations=int(iterations),
        seed=7_700_000 + 101 * int(n_nodes) + 17 * int(n_hosts) + int(seed) + 1009 * int(destroy_size),
        on_iteration=rows.append,
    )
    return tuple(ReplayTraceEntry(tuple(int(v) for v in r.nodes), int(r.destroy_op_index)) for r in rows)


def characterize_keep_all(domain: str, n_nodes: int, n_hosts: int, seed: int,
                          trace: Sequence[ReplayTraceEntry], *, slice_pops: int = 8,
                          cooling: float = 0.995) -> StructuralWidthResult:
    case = make_domain_case(domain, int(n_nodes), int(n_hosts), seed=int(seed))
    instance = case.instance
    p = case.placement.copy()
    if not is_feasible(instance, p):
        raise ValueError("initial placement must be feasible")
    initial = float(assignment_cost(instance, p))
    current = initial
    best = current
    temperature = max(1e-9, 0.01 * initial)
    accepted_moves = 0
    policy = OnlineStepPolicy("keep_all", slice_pops=int(slice_pops), budget_bytes=None, predictor=None, future_horizon=40)
    accept_rng = np.random.default_rng(8_800_000 + 101 * int(n_nodes) + 17 * int(n_hosts) + int(seed) + 1009 * int(len(trace[0].nodes) if trace else 0))
    uniforms = accept_rng.random(len(trace))
    active_end: list[int] = []
    bytes_end: list[int] = []

    for iteration, entry in enumerate(trace, start=1):
        local_rng = np.random.default_rng(9_900_000 + 10_000 * int(n_nodes) + 100 * int(seed) + iteration)
        before = current
        targets, _, cache, _diag = policy.repair(
            instance=instance, placement=p, nodes=entry.nodes, iteration=iteration,
            destroy_op_index=entry.destroy_op_index, objective_before=current,
            best_objective=best, temperature=temperature, local_rng=local_rng,
        )
        q = p.copy()
        for node, host in zip(cache.nodes, targets):
            q[int(node)] = int(host)
        if not is_feasible(instance, q):
            raise AssertionError("P7B keep-all repair produced infeasible placement")
        q_cost = float(assignment_cost(instance, q))
        delta = q_cost - current
        accept_prob = 1.0 if delta < 0 else math.exp(-max(0.0, delta) / max(temperature, 1e-12))
        accept = bool(delta < 0 or uniforms[iteration - 1] < accept_prob)
        changed_nodes = tuple(int(v) for v in np.flatnonzero(q != p)) if accept else ()
        if accept:
            p = q
            current = q_cost
            accepted_moves += 1
            best = min(best, current)
        policy.notify_after_decision(
            instance=instance, nodes=entry.nodes, accepted=accept, iteration=iteration,
            objective_before=before, objective_after=current, placement=p, changed_nodes=changed_nodes,
        )
        active_end.append(len(policy.memory.records))
        bytes_end.append(policy.memory.bytes_used)
        temperature *= cooling

    a = np.asarray(active_end, dtype=float)
    b = np.asarray(bytes_end, dtype=float)
    unique = len({e.nodes for e in trace})
    unfinished = max(0, len(trace) - int(policy.exact_retirements)) / max(1, len(trace))
    peak_bytes = int(max(bytes_end) if bytes_end else 0)
    max_cp = int(policy.max_checkpoint_size_bytes)
    return StructuralWidthResult(
        domain=str(domain), instance_seed=int(seed), n_nodes=int(n_nodes), n_hosts=int(n_hosts),
        destroy_size=int(len(trace[0].nodes) if trace else 0), iterations=int(len(trace)), slice_pops=int(slice_pops),
        trace_unique_contexts=int(unique), trace_recurrence_events=int(len(trace)-unique),
        accepted_moves=int(accepted_moves), useful_resumes=int(policy.useful_resumes),
        reused_prior_branch_pops=int(policy.reused_prior_branch_pops), checkpoint_creations=int(policy.checkpoint_creations),
        exact_retirements=int(policy.exact_retirements), unfinished_return_fraction=float(unfinished),
        invalidation_evictions=int(policy.memory.invalidation_evictions), peak_active_checkpoints=int(max(active_end) if active_end else 0),
        mean_active_checkpoints_end_iteration=float(a.mean() if a.size else 0.0),
        fraction_iterations_k_ge_2=float((a >= 2).mean() if a.size else 0.0),
        fraction_iterations_k_ge_3=float((a >= 3).mean() if a.size else 0.0),
        fraction_iterations_k_ge_4=float((a >= 4).mean() if a.size else 0.0),
        peak_bytes=peak_bytes, max_checkpoint_size_bytes=max_cp,
        max_checkpoint_fraction_of_peak=float(max_cp / peak_bytes) if peak_bytes > 0 else 0.0,
        median_active_checkpoint_bytes=float(np.median(b[b > 0])) if np.any(b > 0) else 0.0,
    )
