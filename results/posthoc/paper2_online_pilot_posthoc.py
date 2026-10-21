"""Paper-2 P7 online pilot.

This module executes a controlled *online* persistence loop over an exogenous
repair-context trace.  Retention affects the repair state, accepted moves,
objective trajectory, invalidations, and future resumptions, while every policy
receives the same repair contexts and acceptance random variates.

The pilot deliberately uses deterministic branch-pop slices.  It compares:
- restart (no persistence),
- exact empirical-compatible expected-value retention,
- the frozen P6-v1 calibrated learned probability + exact selection,
- keep-all persistence as a causal upper-resource opportunity reference.

A clairvoyant future-aware "oracle" is intentionally not implemented: once a
retention decision changes accepted repairs it also changes the future state,
so a static hindsight oracle would be circular.  Keep-all is the honest online
opportunity reference for this pilot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence
import math
import pickle
import time

import joblib
import numpy as np
import pandas as pd

from .alns_baseline import _repair_greedy
from .anytime_gap_certified_repair import initialize_anytime_repair
from .destroy_repair_analysis import build_destroy_repair_cache
from .trace_dynamic_policy import cache_equal_for_resume
from .domain_instances import make_domain_case
from .feasibility import is_feasible
from .matched_lns_controller import IterationRecord, matched_adaptive_lns
from .matched_lns_policies import (
    PersistentCheckpointEntry,
    _residual_capacity_fresh,
    make_heuristic_repair_arms,
)
from .objective import assignment_cost
from .paper2_exact_selection import ValueItem, select_exact_expected_value
from .step_resumption import advance_anytime_repair_steps


P7PilotPolicyName = Literal["restart", "empirical_compatible", "learned", "keep_all", "work_only", "history_only"]


@dataclass(frozen=True)
class ReplayTraceEntry:
    nodes: tuple[int, ...]
    destroy_op_index: int


@dataclass
class StoredCheckpoint:
    key: tuple[int, ...]
    blob: bytes
    size_bytes: int
    cumulative_pops: int
    probability: float
    expected_value: float
    created_iteration: int
    last_scored_iteration: int
    times_resumed: int = 0


@dataclass
class P7OnlineMemory:
    budget_bytes: int | None
    records: dict[tuple[int, ...], StoredCheckpoint] = field(default_factory=dict)
    invalidated_contexts: set[tuple[int, ...]] = field(default_factory=set)
    capacity_evictions: int = 0
    invalidation_evictions: int = 0
    not_retained: int = 0
    serialization_ms: float = 0.0
    restoration_ms: float = 0.0
    selection_ms: float = 0.0
    peak_bytes: int = 0
    byte_time: int = 0
    peak_active_checkpoints: int = 0
    active_checkpoint_time: int = 0

    @property
    def bytes_used(self) -> int:
        return int(sum(r.size_bytes for r in self.records.values()))

    def update_accounting(self) -> None:
        self.peak_bytes = max(self.peak_bytes, self.bytes_used)
        self.byte_time += self.bytes_used
        self.peak_active_checkpoints = max(self.peak_active_checkpoints, len(self.records))
        self.active_checkpoint_time += len(self.records)


@dataclass(frozen=True)
class OnlineHistoryRow:
    iteration: int
    nodes: tuple[int, ...]
    accepted: bool
    objective_before: float
    objective_after: float


@dataclass
class P7PilotResult:
    domain: str
    instance_seed: int
    policy: str
    budget_fraction: float | None
    budget_bytes: int | None
    iterations: int
    accepted_moves: int
    initial_objective: float
    final_objective: float
    best_objective: float
    mean_objective_ratio: float
    branch_pops_executed: int
    useful_resumes: int
    reused_prior_branch_pops: int
    checkpoint_creations: int
    exact_retirements: int
    capacity_evictions: int
    invalidation_evictions: int
    not_retained: int
    peak_bytes: int
    byte_time: int
    peak_active_checkpoints: int
    mean_active_checkpoints: float
    serialization_ms: float
    restoration_ms: float
    selection_ms: float
    model_scoring_ms: float
    max_checkpoint_size_bytes: int
    trace_unique_contexts: int
    trace_recurrence_events: int

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


class FrozenP6Predictor:
    """Load and apply the permanently frozen P6-v1 model/calibrator."""

    def __init__(self, base_dir: str | Path):
        base = Path(base_dir)
        model_obj = joblib.load(base / "03_P6_Predictor_Development" / "p6_final_model.joblib")
        calibration = joblib.load(base / "03_P6_Predictor_Development" / "p6_calibration.joblib")
        self.model = model_obj["model"]
        self.meta = dict(model_obj["meta"])
        self.features = tuple(self.meta["features"])
        self.calibration = calibration
        if self.meta.get("model_family") != "logistic" or self.meta.get("feature_family") != "H+D":
            raise ValueError("P7 pilot requires the frozen P6-v1 logistic H+D model")
        if calibration.get("choice") != "platt":
            raise ValueError("P7 pilot requires the frozen P6-v1 Platt calibrator")

    def predict(self, features: dict[str, float | int]) -> float:
        frame = pd.DataFrame([{name: features[name] for name in self.features}])
        raw = float(self.model.predict_proba(frame)[0, 1])
        raw = float(np.clip(raw, 1e-6, 1 - 1e-6))
        logit = np.array([[math.log(raw / (1.0 - raw))]], dtype=float)
        p = float(self.calibration["platt"].predict_proba(logit)[0, 1])
        return float(np.clip(p, 1e-6, 1 - 1e-6))


def generate_replay_trace(domain: str, seed: int, *, iterations: int = 200, destroy_size: int = 8) -> tuple[ReplayTraceEntry, ...]:
    """Generate one exogenous natural repair-context trace with the baseline controller."""
    case = make_domain_case(domain, 24, 6, seed=int(seed))
    rows: list[IterationRecord] = []
    matched_adaptive_lns(
        case.instance,
        case.placement,
        make_heuristic_repair_arms(),
        destroy_size=int(destroy_size),
        max_iterations=int(iterations),
        seed=7_700_000 + int(seed),
        on_iteration=rows.append,
    )
    return tuple(ReplayTraceEntry(tuple(int(v) for v in r.nodes), int(r.destroy_op_index)) for r in rows)


def _affected_by_move(instance, moved_nodes: Sequence[int], target_nodes: Sequence[int]) -> bool:
    moved = np.asarray(tuple(int(x) for x in moved_nodes), dtype=int)
    adjacent = (
        np.any(instance.interaction[moved] != 0, axis=0)
        | np.any(instance.interaction[:, moved] != 0, axis=1)
    )
    affected = set(np.flatnonzero(adjacent).tolist()) | set(moved.tolist())
    return bool(affected.intersection(int(x) for x in target_nodes))


def _history_features(instance, history: Sequence[OnlineHistoryRow], iteration: int, nodes: tuple[int, ...]) -> dict[str, float | int]:
    # iteration is 1-based and history contains iterations < current.
    same_positions = [r.iteration for r in history if r.nodes == nodes]
    last = same_positions[-1] if same_positions else None

    def recent(window: int):
        rows = list(history[-window:])
        accepted = [r for r in rows if r.accepted]
        overlap = sum(len(set(r.nodes).intersection(nodes)) for r in accepted)
        adjacent_count = sum(_affected_by_move(instance, r.nodes, nodes) for r in accepted)
        same = sum(r.nodes == nodes for r in rows)
        rate = (sum(r.accepted for r in rows) / len(rows)) if rows else 0.0
        if rows:
            improvement = float(rows[0].objective_before - rows[-1].objective_after)
        else:
            improvement = 0.0
        return rate, same, overlap, adjacent_count, improvement

    r10 = recent(10)
    r20 = recent(20)
    return {
        "history_count_same_context": int(len(same_positions)),
        "iterations_since_last_context": int(iteration - last) if last is not None else int(iteration),
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


def _p6_features(
    instance,
    history: Sequence[OnlineHistoryRow],
    iteration: int,
    nodes: tuple[int, ...],
    destroy_op_index: int,
    objective_before: float,
    best_objective: float,
    temperature: float,
) -> dict[str, float | int]:
    out = _history_features(instance, history, iteration, nodes)
    out.update({
        "current_destroy_op_index": int(destroy_op_index),
        # The deployed persistent PCR policy is the sole repair arm in the P7
        # replay controller, so it occupies the known arm-0 category.
        "current_repair_arm_index": 0,
        "current_objective_before": float(objective_before),
        "current_best_objective": float(best_objective),
        "current_temperature": float(temperature),
    })
    return out


def _history_recurrence_probability(history: Sequence[OnlineHistoryRow], iteration: int, nodes: tuple[int, ...], horizon: int = 40) -> float:
    c = float(sum(r.nodes == nodes for r in history))
    # Frozen P6 history baseline: Jeffreys-smoothed Poisson rate.
    lam = (c + 0.5) / (float(iteration) + 1.0)
    return float(np.clip(1.0 - math.exp(-float(horizon) * lam), 1e-6, 1 - 1e-6))


@dataclass
class CompatibilityStats:
    compatible: int = 0
    incompatible: int = 0

    def probability(self, global_stats: "CompatibilityStats") -> float:
        n = self.compatible + self.incompatible
        if n > 0:
            return float((self.compatible + 0.5) / (n + 1.0))
        gn = global_stats.compatible + global_stats.incompatible
        if gn > 0:
            return float((global_stats.compatible + 0.5) / (gn + 1.0))
        return 0.5


class OnlineStepPolicy:
    def __init__(
        self,
        name: P7PilotPolicyName,
        *,
        slice_pops: int,
        budget_bytes: int | None,
        predictor: FrozenP6Predictor | None = None,
        future_horizon: int = 40,
    ):
        self.name = name
        self.slice_pops = int(slice_pops)
        self.budget_bytes = None if budget_bytes is None else int(budget_bytes)
        self.predictor = predictor
        self.future_horizon = int(future_horizon)
        self.memory = P7OnlineMemory(self.budget_bytes)
        self.history: list[OnlineHistoryRow] = []
        self.compat_stats: dict[tuple[int, ...], CompatibilityStats] = {}
        self.global_compat = CompatibilityStats()
        self.invalidated_since_observation: set[tuple[int, ...]] = set()
        self.branch_pops_executed = 0
        self.useful_resumes = 0
        self.reused_prior_branch_pops = 0
        self.checkpoint_creations = 0
        self.exact_retirements = 0
        self.model_scoring_ms = 0.0
        self.max_checkpoint_size_bytes = 0
        self._last_key: tuple[int, ...] | None = None
        self._last_entry: PersistentCheckpointEntry | None = None
        self._last_retained = False

    def _deserialize(self, record: StoredCheckpoint) -> PersistentCheckpointEntry:
        t0 = time.perf_counter()
        entry = pickle.loads(record.blob)
        self.memory.restoration_ms += (time.perf_counter() - t0) * 1000.0
        return entry

    def _serialize(self, entry: PersistentCheckpointEntry) -> bytes:
        t0 = time.perf_counter()
        blob = pickle.dumps(entry, protocol=pickle.HIGHEST_PROTOCOL)
        self.memory.serialization_ms += (time.perf_counter() - t0) * 1000.0
        return blob

    def _score_probability(self, *, instance, iteration: int, nodes: tuple[int, ...], destroy_op_index: int,
                           objective_before: float, best_objective: float, temperature: float) -> float:
        if self.name == "keep_all":
            return 1.0
        if self.name == "work_only":
            return 1.0
        if self.name == "history_only":
            p_rec = _history_recurrence_probability(self.history, iteration, nodes, self.future_horizon)
            return float(np.clip(p_rec, 1e-6, 1 - 1e-6))
        if self.name == "empirical_compatible":
            p_rec = _history_recurrence_probability(self.history, iteration, nodes, self.future_horizon)
            stats = self.compat_stats.setdefault(nodes, CompatibilityStats())
            return float(np.clip(p_rec * stats.probability(self.global_compat), 1e-6, 1 - 1e-6))
        if self.name == "learned":
            assert self.predictor is not None
            feats = _p6_features(instance, self.history, iteration, nodes, destroy_op_index,
                                 objective_before, best_objective, temperature)
            t0 = time.perf_counter()
            p = self.predictor.predict(feats)
            self.model_scoring_ms += (time.perf_counter() - t0) * 1000.0
            return p
        raise AssertionError("restart has no persistence probability")

    def _select_exact(self, incoming: StoredCheckpoint | None, iteration: int) -> bool:
        if self.name == "keep_all":
            if incoming is not None:
                self.memory.records[incoming.key] = incoming
            self.memory.update_accounting()
            return True
        assert self.budget_bytes is not None
        candidates = dict(self.memory.records)
        if incoming is not None:
            candidates[incoming.key] = incoming
        items = [ValueItem(k, r.size_bytes, r.expected_value) for k, r in candidates.items()]
        t0 = time.perf_counter()
        keep = set(select_exact_expected_value(items, budget_bytes=self.budget_bytes))
        self.memory.selection_ms += (time.perf_counter() - t0) * 1000.0
        old_keys = set(self.memory.records)
        for key in old_keys - keep:
            self.memory.records.pop(key, None)
            self.memory.capacity_evictions += 1
        admitted = incoming is None or incoming.key in keep
        if incoming is not None:
            if admitted:
                self.memory.records[incoming.key] = incoming
            else:
                self.memory.records.pop(incoming.key, None)
                self.memory.not_retained += 1
        self.memory.update_accounting()
        return bool(admitted)

    def repair(
        self,
        *,
        instance,
        placement: np.ndarray,
        nodes: tuple[int, ...],
        iteration: int,
        destroy_op_index: int,
        objective_before: float,
        best_objective: float,
        temperature: float,
        local_rng: np.random.Generator,
    ) -> tuple[tuple[int, ...], float, object, dict[str, float | int]]:
        key = tuple(nodes)
        self._last_key = key
        self._last_entry = None
        self._last_retained = False

        # Restart always creates a fresh exact-search state.
        if self.name == "restart":
            cache = build_destroy_repair_cache(instance, placement, nodes)
            target, _ = _repair_greedy(instance, placement, nodes, local_rng)
            cp = initialize_anytime_repair(instance, placement, nodes, initial_target_hosts=target, prebuilt_cache=cache)
            move, cert, pops = advance_anytime_repair_steps(instance, cp, self.slice_pops, epsilon_target=0.0)
            self.branch_pops_executed += int(pops)
            self.checkpoint_creations += 1
            if cert.exact:
                self.exact_retirements += 1
            return move.target_hosts, float(move.gain), cache, {
                "resumed": 0, "reused_prior_branch_pops": 0, "branch_pops": int(pops),
                "checkpoint_size_bytes": 0, "retained": 0, "certificate_exact": int(cert.exact),
            }

        # Observe whether a previous checkpoint for this context survived and
        # remains valid.  This is also the deployable compatibility-history
        # signal used by the empirical comparator.
        record = self.memory.records.get(key)
        entry = None
        resumed = False
        reused = 0
        counted_incompat_this_call = False
        if record is not None:
            candidate = self._deserialize(record)
            if _residual_capacity_fresh(instance, placement, candidate.checkpoint.cache):
                entry = candidate
                resumed = True
                reused = int(record.cumulative_pops)
                self.useful_resumes += 1
                self.reused_prior_branch_pops += reused
                stats = self.compat_stats.setdefault(key, CompatibilityStats())
                stats.compatible += 1
                self.global_compat.compatible += 1
            else:
                self.memory.records.pop(key, None)
                self.memory.invalidation_evictions += 1
                self.invalidated_since_observation.add(key)
                stats = self.compat_stats.setdefault(key, CompatibilityStats())
                stats.incompatible += 1
                self.global_compat.incompatible += 1
                counted_incompat_this_call = True

        if entry is None:
            if key in self.invalidated_since_observation:
                # A previous state for this context was known to be invalidated
                # before this recurrence.  Count it once as an incompatibility
                # observation and clear the marker.
                if not counted_incompat_this_call:
                    stats = self.compat_stats.setdefault(key, CompatibilityStats())
                    stats.incompatible += 1
                    self.global_compat.incompatible += 1
                self.invalidated_since_observation.discard(key)
            cache = build_destroy_repair_cache(instance, placement, nodes)
            target, _ = _repair_greedy(instance, placement, nodes, local_rng)
            cp = initialize_anytime_repair(instance, placement, nodes, initial_target_hosts=target, prebuilt_cache=cache)
            entry = PersistentCheckpointEntry(checkpoint=cp, next_slice_ms=0.0, created_iteration=iteration)
            cumulative_before = 0
            self.checkpoint_creations += 1
        else:
            cache = entry.checkpoint.cache
            entry.times_resumed += 1
            cumulative_before = int(record.cumulative_pops) if record is not None else 0

        move, cert, pops = advance_anytime_repair_steps(instance, entry.checkpoint, self.slice_pops, epsilon_target=0.0)
        self.branch_pops_executed += int(pops)
        entry.last_returned_gain = float(move.gain)
        cumulative = cumulative_before + int(pops)

        if cert.exact:
            self.memory.records.pop(key, None)
            self.exact_retirements += 1
            self.memory.update_accounting()
            self._last_entry = entry
            return move.target_hosts, float(entry.rebased(move.gain)), cache, {
                "resumed": int(resumed), "reused_prior_branch_pops": int(reused), "branch_pops": int(pops),
                "checkpoint_size_bytes": 0, "retained": 0, "certificate_exact": 1,
            }

        p = self._score_probability(
            instance=instance, iteration=iteration, nodes=key, destroy_op_index=destroy_op_index,
            objective_before=objective_before, best_objective=best_objective, temperature=temperature,
        )
        blob = self._serialize(entry)
        size = len(blob)
        self.max_checkpoint_size_bytes = max(self.max_checkpoint_size_bytes, size)
        incoming = StoredCheckpoint(
            key=key,
            blob=blob,
            size_bytes=size,
            cumulative_pops=cumulative,
            probability=float(p),
            expected_value=float(p * cumulative),
            created_iteration=(record.created_iteration if record is not None else iteration),
            last_scored_iteration=iteration,
            times_resumed=entry.times_resumed,
        )
        admitted = self._select_exact(incoming, iteration)
        self._last_entry = entry
        self._last_retained = admitted
        return move.target_hosts, float(entry.rebased(move.gain)), cache, {
            "resumed": int(resumed), "reused_prior_branch_pops": int(reused), "branch_pops": int(pops),
            "checkpoint_size_bytes": int(size), "retained": int(admitted), "certificate_exact": 0,
        }

    def notify_after_decision(self, *, instance, nodes: tuple[int, ...], accepted: bool, iteration: int,
                              objective_before: float, objective_after: float,
                              placement: np.ndarray | None = None,
                              changed_nodes: Sequence[int] = ()) -> None:
        """Update persistence after the controller decision.

        Paper-2 P7B amendment: an accepted *proposal* is not automatically an
        accepted placement change.  Exact checkpoint validity depends on the
        placement that actually changed.  No-op/equal-placement acceptances
        therefore leave all checkpoints untouched.  When hosts really change,
        the producing checkpoint is rebased and every other checkpoint is
        retained only if its exact local cache remains identical under the new
        placement.  Checkpoints whose own free-node assignment was changed by
        another repair are conservatively invalidated because we do not have a
        certified gain-offset rebase for that cross-context case.
        """
        key = tuple(nodes)
        changed = tuple(int(v) for v in changed_nodes)
        if self.name != "restart" and accepted and changed:
            if placement is None:
                raise ValueError("placement is required when accepted decision changes hosts")
            changed_set = set(changed)

            # The checkpoint produced by this same repair remains valid under
            # same-scope rebase: all changed nodes lie in its free set.
            own = self.memory.records.get(key)
            if own is not None:
                entry = self._deserialize(own)
                entry.gain_offset = entry.last_returned_gain
                blob = self._serialize(entry)
                own.blob = blob
                own.size_bytes = len(blob)

            # For every other dormant state, apply the exact PCR compatibility
            # rule instead of invalidating from the entire destroy set.
            for other in list(self.memory.records):
                if other == key:
                    continue
                invalidate = False
                if changed_set.intersection(other):
                    # Another context moved one of this checkpoint's free nodes;
                    # current code has no certified cross-context gain rebase.
                    invalidate = True
                else:
                    record = self.memory.records[other]
                    try:
                        prior = self._deserialize(record)
                        fresh = build_destroy_repair_cache(instance, placement, other)
                        invalidate = not cache_equal_for_resume(fresh, prior.checkpoint.cache)
                    except Exception:
                        invalidate = True
                if invalidate:
                    self.memory.records.pop(other, None)
                    self.memory.invalidation_evictions += 1
                    self.invalidated_since_observation.add(other)

            if self.name != "keep_all" and self.budget_bytes is not None and self.memory.bytes_used > self.budget_bytes:
                self._select_exact(None, iteration)

        self.history.append(OnlineHistoryRow(
            iteration=int(iteration), nodes=key, accepted=bool(accepted),
            objective_before=float(objective_before), objective_after=float(objective_after),
        ))
        self.memory.update_accounting()


def run_online_replay(
    domain: str,
    seed: int,
    trace: Sequence[ReplayTraceEntry],
    *,
    policy_name: P7PilotPolicyName,
    slice_pops: int = 8,
    budget_bytes: int | None = None,
    budget_fraction: float | None = None,
    predictor: FrozenP6Predictor | None = None,
    cooling: float = 0.995,
) -> P7PilotResult:
    case = make_domain_case(domain, 24, 6, seed=int(seed))
    instance = case.instance
    p = case.placement.copy()
    if not is_feasible(instance, p):
        raise ValueError("initial placement must be feasible")
    initial = float(assignment_cost(instance, p))
    current = initial
    best = current
    temperature = max(1e-9, 0.01 * initial)
    accepted_moves = 0
    objective_ratios: list[float] = []
    policy = OnlineStepPolicy(
        policy_name, slice_pops=slice_pops, budget_bytes=budget_bytes,
        predictor=predictor, future_horizon=40,
    )
    accept_rng = np.random.default_rng(8_800_000 + int(seed))
    uniforms = accept_rng.random(len(trace))

    for iteration, entry in enumerate(trace, start=1):
        local_rng = np.random.default_rng(9_900_000 + 1000 * int(seed) + iteration)
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
            raise AssertionError("P7 online repair produced infeasible placement")
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
        temperature *= cooling
        objective_ratios.append(current / initial if initial > 0 else 1.0)

    unique = len({e.nodes for e in trace})
    return P7PilotResult(
        domain=domain,
        instance_seed=int(seed),
        policy=policy_name,
        budget_fraction=budget_fraction,
        budget_bytes=budget_bytes,
        iterations=len(trace),
        accepted_moves=accepted_moves,
        initial_objective=initial,
        final_objective=current,
        best_objective=best,
        mean_objective_ratio=float(np.mean(objective_ratios)),
        branch_pops_executed=int(policy.branch_pops_executed),
        useful_resumes=int(policy.useful_resumes),
        reused_prior_branch_pops=int(policy.reused_prior_branch_pops),
        checkpoint_creations=int(policy.checkpoint_creations),
        exact_retirements=int(policy.exact_retirements),
        capacity_evictions=int(policy.memory.capacity_evictions),
        invalidation_evictions=int(policy.memory.invalidation_evictions),
        not_retained=int(policy.memory.not_retained),
        peak_bytes=int(policy.memory.peak_bytes),
        byte_time=int(policy.memory.byte_time),
        peak_active_checkpoints=int(policy.memory.peak_active_checkpoints),
        mean_active_checkpoints=float(policy.memory.active_checkpoint_time / max(1, 2 * len(trace))),
        serialization_ms=float(policy.memory.serialization_ms),
        restoration_ms=float(policy.memory.restoration_ms),
        selection_ms=float(policy.memory.selection_ms),
        model_scoring_ms=float(policy.model_scoring_ms),
        max_checkpoint_size_bytes=int(policy.max_checkpoint_size_bytes),
        trace_unique_contexts=int(unique),
        trace_recurrence_events=int(len(trace) - unique),
    )
