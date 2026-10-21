"""Paper-2 P5.5 dataset/protocol hardening.

This module builds a *natural* recurrence/compatibility corpus from the existing
matched outer-LNS controller.  It does not use the P4/P5 synthetic recurrence
sampler and it does not select perturbations to force a desired compatibility
rate.

At fixed, pre-declared decision iterations, a real unfinished exact-repair
checkpoint is created from the controller's current repair context and current
placement.  The subsequent unmodified controller trace determines whether the
same destroy set recurs within a fixed horizon and, if so, whether the old
checkpoint remains legally resumable under PCR's exact cache-equality rule.

All future-derived fields are explicitly separated from decision-time features
so P6 can enforce a no-leak feature firewall.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import pickle
from typing import Iterable, Sequence

import numpy as np

from .destroy_repair_analysis import build_destroy_repair_cache
from .domain_instances import make_domain_case
from .matched_lns_controller import IterationRecord, matched_adaptive_lns
from .matched_lns_policies import make_heuristic_repair_arms
from .paper2_counterfactual import make_counterfactual_reuse_pair
from .step_resumption import advance_anytime_repair_steps
from .trace_dynamic_policy import cache_equal_for_resume


P55_SEEDS: tuple[int, ...] = (
    101, 202, 303, 404, 505, 606, 707, 808, 909,
    1010, 1111, 1212, 1313, 1414, 1515,
)
P55_DOMAINS: tuple[str, ...] = ("generic", "workflow", "microservice")
P55_DECISION_ITERATIONS: tuple[int, ...] = tuple(range(20, 161, 10))
P55_FUTURE_HORIZON = 40
P55_TOTAL_ITERATIONS = 200
P55_DESTROY_SIZE = 8
P55_INVESTED_SCHEDULE: tuple[int, ...] = (2, 4, 6, 8, 10, 12, 14, 16)

# Model-input fields frozen before P6.  Identifiers/split columns are kept
# outside this list and must not be silently included by a generic dataframe
# loader.
P55_ALLOWED_FEATURES: tuple[str, ...] = (
    "invested_branch_pops",
    "checkpoint_bytes",
    "additive_gap_at_checkpoint",
    "residual_opportunity",
    "queue_size",
    "partial_branches_expanded",
    "partial_branches_pruned",
    "child_branches_generated",
    "leaves_evaluated",
    "best_gain_at_checkpoint",
    "root_upper_bound",
    "history_count_same_context",
    "iterations_since_last_context",
    "current_recurrent",
    "current_destroy_op_index",
    "current_repair_arm_index",
    "current_objective_before",
    "current_best_objective",
    "current_temperature",
    "recent_accept_rate_10",
    "recent_accept_rate_20",
    "recent_same_context_count_20",
    "recent_moved_node_overlap_10",
    "recent_adjacent_move_count_10",
    "recent_moved_node_overlap_20",
    "recent_adjacent_move_count_20",
    "objective_improvement_last_10",
    "objective_improvement_last_20",
)

P55_FORBIDDEN_FEATURES: tuple[str, ...] = (
    "future_count",
    "future_compatible_count",
    "future_incompatible_count",
    "first_future_position",
    "first_future_compatible_position",
    "future_recurred",
    "future_compatible_recurrence",
    "future_incompatible_only",
    "realized_future_saved_branch_pops",
    "future_placement",
    "future_state",
    "future_edge",
    "oracle_selected",
    "oracle_value",
)


# P5.6 amendment: remove fields that are constant or exact duplicates in the
# frozen P5.5 natural corpus.  P5.5 remains unchanged for provenance; P6 uses
# this cleaned feature matrix.
P56_DROPPED_FEATURES: tuple[str, ...] = (
    "current_recurrent",
    "leaves_evaluated",
    "best_gain_at_checkpoint",
    "partial_branches_expanded",  # exact duplicate of invested_branch_pops
    "residual_opportunity",       # exact duplicate of additive_gap_at_checkpoint
)
P56_ALLOWED_FEATURES: tuple[str, ...] = tuple(
    f for f in P55_ALLOWED_FEATURES if f not in set(P56_DROPPED_FEATURES)
)
P56_BLIND_SEEDS: tuple[int, ...] = (1616, 1717, 1818, 1919, 2020)


@dataclass(frozen=True)
class P55NaturalEvent:
    case_id: str
    domain: str
    instance_seed: int
    decision_iteration: int
    candidate_id: str
    destroy_set: tuple[int, ...]
    future_horizon: int
    requested_invested_branch_pops: int
    invested_branch_pops: int
    checkpoint_bytes: int
    additive_gap_at_checkpoint: float
    residual_opportunity: float
    queue_size: int
    partial_branches_expanded: int
    partial_branches_pruned: int
    child_branches_generated: int
    leaves_evaluated: int
    best_gain_at_checkpoint: float
    root_upper_bound: float
    history_count_same_context: int
    iterations_since_last_context: int
    current_recurrent: int
    current_destroy_op_index: int
    current_repair_arm_index: int
    current_objective_before: float
    current_best_objective: float
    current_temperature: float
    recent_accept_rate_10: float
    recent_accept_rate_20: float
    recent_same_context_count_20: int
    recent_moved_node_overlap_10: int
    recent_adjacent_move_count_10: int
    recent_moved_node_overlap_20: int
    recent_adjacent_move_count_20: int
    objective_improvement_last_10: float
    objective_improvement_last_20: float
    future_count: int
    future_compatible_count: int
    future_incompatible_count: int
    first_future_position: int
    first_future_compatible_position: int
    future_recurred: int
    future_compatible_recurrence: int
    future_incompatible_only: int
    realized_future_saved_branch_pops: int

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["destroy_set"] = ";".join(str(v) for v in self.destroy_set)
        return row


def _placements_before(case, records: Sequence[IterationRecord]) -> list[np.ndarray]:
    """Reconstruct the exact placement seen at the start of every iteration."""
    p = case.placement.copy()
    placements: list[np.ndarray] = []
    for record in records:
        placements.append(p.copy())
        if record.accepted:
            for node, host in zip(record.nodes, record.outcome.target_hosts):
                p[int(node)] = int(host)
    placements.append(p.copy())
    return placements


def _is_exact(instance, checkpoint) -> bool:
    _, cert, _ = advance_anytime_repair_steps(instance, checkpoint, 0, epsilon_target=0.0)
    return bool(cert.exact)


def _checkpoint_at_decision(case, placement, nodes, requested_invested: int):
    invested = max(1, int(requested_invested))
    pair = make_counterfactual_reuse_pair(
        case.instance,
        placement,
        nodes,
        invested_branch_pops=invested,
    )
    while _is_exact(case.instance, pair.resume_checkpoint) and invested > 1:
        invested = max(1, invested // 2)
        pair = make_counterfactual_reuse_pair(
            case.instance,
            placement,
            nodes,
            invested_branch_pops=invested,
        )
    if _is_exact(case.instance, pair.resume_checkpoint):
        return None
    return pair


def _affected_by_move(instance, moved_nodes: Sequence[int], target_nodes: Sequence[int]) -> bool:
    moved = np.asarray(tuple(int(x) for x in moved_nodes), dtype=int)
    adjacent = (
        np.any(instance.interaction[moved] != 0, axis=0)
        | np.any(instance.interaction[:, moved] != 0, axis=1)
    )
    affected = set(np.flatnonzero(adjacent).tolist()) | set(moved.tolist())
    return bool(affected.intersection(int(x) for x in target_nodes))


def _history_features(instance, records: Sequence[IterationRecord], idx: int, nodes: tuple[int, ...]) -> dict[str, float | int]:
    history = records[:idx]
    same_positions = [j for j, r in enumerate(history) if r.nodes == nodes]
    last = same_positions[-1] if same_positions else -1

    def recent(window: int):
        rows = records[max(0, idx - window):idx]
        accepted = [r for r in rows if r.accepted]
        overlap = sum(len(set(r.nodes).intersection(nodes)) for r in accepted)
        adjacent_count = sum(_affected_by_move(instance, r.nodes, nodes) for r in accepted)
        same = sum(r.nodes == nodes for r in rows)
        rate = (sum(r.accepted for r in rows) / len(rows)) if rows else 0.0
        if rows:
            start_obj = float(rows[0].objective_before)
            end_obj = float(records[idx].objective_before)
            improvement = start_obj - end_obj
        else:
            improvement = 0.0
        return rate, same, overlap, adjacent_count, improvement

    r10 = recent(10)
    r20 = recent(20)
    return {
        "history_count_same_context": int(len(same_positions)),
        "iterations_since_last_context": int(idx - last) if last >= 0 else int(idx + 1),
        "recent_accept_rate_10": float(r10[0]),
        "recent_accept_rate_20": float(r20[0]),
        "recent_same_context_count_20": int(r20[1]),
        "recent_moved_node_overlap_10": int(r10[2]),
        "recent_adjacent_move_count_10": int(r10[3]),
        "recent_moved_node_overlap_20": int(r20[2]),
        "recent_adjacent_move_count_20": int(r20[3]),
        "objective_improvement_last_10": float(r10[4]),
        "objective_improvement_last_20": float(r20[4]),
    }


def _future_labels(case, records, placements, idx: int, nodes: tuple[int, ...], checkpoint, horizon: int) -> dict[str, int]:
    stop = min(len(records), idx + 1 + int(horizon))
    future_count = compatible = incompatible = 0
    first = first_compatible = -1
    for j in range(idx + 1, stop):
        record = records[j]
        if record.nodes != nodes:
            continue
        future_count += 1
        rel = j - idx
        if first < 0:
            first = int(rel)
        fresh = build_destroy_repair_cache(case.instance, placements[j], nodes)
        if cache_equal_for_resume(fresh, checkpoint.cache):
            compatible += 1
            if first_compatible < 0:
                first_compatible = int(rel)
        else:
            incompatible += 1
    return {
        "future_count": int(future_count),
        "future_compatible_count": int(compatible),
        "future_incompatible_count": int(incompatible),
        "first_future_position": int(first),
        "first_future_compatible_position": int(first_compatible),
        "future_recurred": int(future_count > 0),
        "future_compatible_recurrence": int(compatible > 0),
        "future_incompatible_only": int(future_count > 0 and compatible == 0),
    }


def generate_natural_case_events(
    domain: str,
    instance_seed: int,
    *,
    n: int = 24,
    m: int = 6,
    destroy_size: int = P55_DESTROY_SIZE,
    total_iterations: int = P55_TOTAL_ITERATIONS,
    decision_iterations: Sequence[int] = P55_DECISION_ITERATIONS,
    future_horizon: int = P55_FUTURE_HORIZON,
    controller_seed_offset: int = 700_000,
    invested_schedule: Sequence[int] = P55_INVESTED_SCHEDULE,
) -> tuple[list[P55NaturalEvent], dict[str, object]]:
    """Generate no-lookahead natural recurrence/compatibility events for one case."""
    case = make_domain_case(domain, n, m, seed=int(instance_seed))
    records: list[IterationRecord] = []
    result = matched_adaptive_lns(
        case.instance,
        case.placement,
        make_heuristic_repair_arms(),
        destroy_size=int(destroy_size),
        max_iterations=int(total_iterations),
        seed=int(controller_seed_offset + instance_seed),
        on_iteration=records.append,
    )
    placements = _placements_before(case, records)
    events: list[P55NaturalEvent] = []
    skipped_exact = 0

    # Randomize invested-work levels within the case using a seed fixed before
    # any future labels are inspected.  This prevents invested work from acting
    # as a deterministic proxy for decision iteration.
    domain_code = {"generic": 1, "workflow": 2, "microservice": 3}[domain]
    schedule_values = list(int(v) for v in invested_schedule)
    requested_sequence = [schedule_values[i % len(schedule_values)] for i in range(len(tuple(decision_iterations)))]
    np.random.default_rng(5_500_000 + 10_000 * domain_code + int(instance_seed)).shuffle(requested_sequence)

    for event_index, iteration in enumerate(decision_iterations):
        if iteration < 1 or iteration > len(records):
            continue
        idx = int(iteration) - 1
        record = records[idx]
        nodes = tuple(int(v) for v in record.nodes)
        requested = int(requested_sequence[event_index])
        pair = _checkpoint_at_decision(case, placements[idx], nodes, requested)
        if pair is None:
            skipped_exact += 1
            continue
        cp = pair.resume_checkpoint
        frontier = -cp.queue[0][0] if cp.queue else cp.best.gain
        residual = float(max(0.0, frontier - cp.best.gain))
        hist = _history_features(case.instance, records, idx, nodes)
        future = _future_labels(case, records, placements, idx, nodes, cp, future_horizon)
        size_bytes = len(pickle.dumps(cp, protocol=pickle.HIGHEST_PROTOCOL))
        events.append(P55NaturalEvent(
            case_id=f"{domain}-s{instance_seed}",
            domain=domain,
            instance_seed=int(instance_seed),
            decision_iteration=int(iteration),
            candidate_id=f"{domain}-s{instance_seed}-i{iteration:03d}",
            destroy_set=nodes,
            future_horizon=int(future_horizon),
            requested_invested_branch_pops=requested,
            invested_branch_pops=int(pair.invested_branch_pops),
            checkpoint_bytes=int(size_bytes),
            additive_gap_at_checkpoint=residual,
            residual_opportunity=residual,
            queue_size=int(len(cp.queue)),
            partial_branches_expanded=int(cp.partial_branches_expanded),
            partial_branches_pruned=int(cp.partial_branches_pruned),
            child_branches_generated=int(cp.child_branches_generated),
            leaves_evaluated=int(cp.leaves_evaluated),
            best_gain_at_checkpoint=float(cp.best.gain),
            root_upper_bound=float(cp.root_upper_bound),
            history_count_same_context=int(hist["history_count_same_context"]),
            iterations_since_last_context=int(hist["iterations_since_last_context"]),
            current_recurrent=int(bool(record.recurrent)),
            current_destroy_op_index=int(record.destroy_op_index),
            current_repair_arm_index=int(record.repair_arm_index),
            current_objective_before=float(record.objective_before),
            current_best_objective=float(record.best_objective_so_far),
            current_temperature=float(record.temperature),
            recent_accept_rate_10=float(hist["recent_accept_rate_10"]),
            recent_accept_rate_20=float(hist["recent_accept_rate_20"]),
            recent_same_context_count_20=int(hist["recent_same_context_count_20"]),
            recent_moved_node_overlap_10=int(hist["recent_moved_node_overlap_10"]),
            recent_adjacent_move_count_10=int(hist["recent_adjacent_move_count_10"]),
            recent_moved_node_overlap_20=int(hist["recent_moved_node_overlap_20"]),
            recent_adjacent_move_count_20=int(hist["recent_adjacent_move_count_20"]),
            objective_improvement_last_10=float(hist["objective_improvement_last_10"]),
            objective_improvement_last_20=float(hist["objective_improvement_last_20"]),
            future_count=int(future["future_count"]),
            future_compatible_count=int(future["future_compatible_count"]),
            future_incompatible_count=int(future["future_incompatible_count"]),
            first_future_position=int(future["first_future_position"]),
            first_future_compatible_position=int(future["first_future_compatible_position"]),
            future_recurred=int(future["future_recurred"]),
            future_compatible_recurrence=int(future["future_compatible_recurrence"]),
            future_incompatible_only=int(future["future_incompatible_only"]),
            realized_future_saved_branch_pops=(
                int(pair.invested_branch_pops) if int(future["future_compatible_recurrence"]) else 0
            ),
        ))

    summary = {
        "case_id": f"{domain}-s{instance_seed}",
        "domain": domain,
        "instance_seed": int(instance_seed),
        "controller_iterations": len(records),
        "accepted_moves": int(result.accepted_moves),
        "unique_destroy_sets": int(len({r.nodes for r in records})),
        "natural_recurrence_events": int(len(records) - len({r.nodes for r in records})),
        "decision_events_requested": int(len(tuple(decision_iterations))),
        "decision_events_emitted": int(len(events)),
        "decision_events_skipped_exact": int(skipped_exact),
    }
    return events, summary


def split_for_seed(seed: int) -> str:
    """Frozen 9/3/3 per-domain grouped split for the 15 P5.5 seeds."""
    if seed not in P55_SEEDS:
        raise ValueError(f"seed {seed} is not in the frozen P5.5 seed set")
    pos = P55_SEEDS.index(int(seed))
    if pos < 9:
        return "train"
    if pos < 12:
        return "validation"
    return "test"


def feature_firewall() -> dict[str, object]:
    return {
        "target": "future_compatible_recurrence",
        "secondary_targets": ["future_recurred", "future_incompatible_only"],
        "allowed_model_features": list(P55_ALLOWED_FEATURES),
        "forbidden_future_or_oracle_fields": list(P55_FORBIDDEN_FEATURES),
        "identifier_only_fields": [
            "case_id", "domain", "instance_seed", "decision_iteration",
            "candidate_id", "destroy_set", "future_horizon",
            "requested_invested_branch_pops",
        ],
        "split_group": ["domain", "instance_seed"],
        "rule": (
            "A field not explicitly listed in allowed_model_features is not a model input by default. "
            "Future/outcome/oracle fields are prohibited. Domain may be evaluated as an explicit "
            "ablation/categorical context but is not silently included in the default model matrix."
        ),
    }


def feature_firewall_p56() -> dict[str, object]:
    """Cleaned P6 feature firewall; P5.5's original firewall remains intact."""
    return {
        "target": "future_compatible_recurrence",
        "secondary_targets": ["future_recurred", "future_incompatible_only"],
        "allowed_model_features": list(P56_ALLOWED_FEATURES),
        "dropped_from_p55": list(P56_DROPPED_FEATURES),
        "forbidden_future_or_oracle_fields": list(P55_FORBIDDEN_FEATURES),
        "identifier_only_fields": [
            "case_id", "domain", "instance_seed", "decision_iteration",
            "candidate_id", "destroy_set", "future_horizon",
            "requested_invested_branch_pops",
        ],
        "split_group": ["domain", "instance_seed"],
        "rule": (
            "P6 uses only explicitly listed cleaned decision-time features. "
            "The five P5.5 dead/duplicate fields are excluded. Future/outcome/oracle "
            "fields remain prohibited. The final blind holdout is not used for model selection."
        ),
    }
