"""The four matched repair policies for the adaptive-LNS controller study.

All four run under the identical ``matched_lns_controller.matched_adaptive_lns``
loop; only the repair step differs:

* **baseline**  -- the original heuristic repair operators (``_repair_greedy``,
  ``_repair_regret2``), unchanged from ``alns_baseline.py``.
* **restart_pcr**  -- PCR's checkpointed engine, but a fresh checkpoint is
  built on every call; nothing persists across outer-loop iterations.
* **persistent_pcr**  -- PCR's checkpointed engine, with the checkpoint kept
  across outer-loop iterations for as long as it remains valid.
* **cert_guided_persistent_pcr**  -- persistent, plus the controller uses the
  checkpoint's residual certificate to decide whether to resume, retire, or
  open a fresh checkpoint, and how large a time slice to spend, following the
  fixed (not tuned on held-out data) gap-trigger policy already used by
  ``gap_certified_intensification_alns`` (AGCI).

Checkpoint validity (``persistent_pcr`` / ``cert_guided_persistent_pcr``) has
*two* independent triggers, both derived directly from how
``destroy_repair_analysis.build_destroy_repair_cache`` builds a cache, and
both are actually exercised by this experiment (neither is dormant):

1. **Interaction-adjacency eviction** (event-driven, at accept time): a
   checkpoint for destroy-set ``S`` is evicted the moment an accepted move
   changes the host of some node with nonzero interaction (in either
   direction) with some node in ``S``, since ``S``'s external/pair gain terms
   are computed from the *current* hosts of every fixed node.
2. **Residual-capacity freshness check** (verified at resume time, not just
   event-driven): ``cache.residual_capacity`` is computed from
   ``instance.capacities - resource_usage(instance, placement)`` over the
   *entire* placement, so it silently goes stale after *any* accepted move
   that changes host occupancy -- including moves on destroy sets that share
   no interaction with ``S`` at all. (An early version of this module only
   implemented trigger 1 and assumed capacity effects were dormant absent an
   explicit "shock"; a differential test against a freshly rebuilt cache
   after an accepted move on a *non-interacting* destroy set showed the
   residual capacities diverge substantially -- resuming on that basis could
   have driven the search to select a host that looks feasible under the
   stale cache but is not, in the real current placement.) Because trigger 1
   is comparatively rare to hit exactly and trigger 2 fires on almost any
   accepted move, resumption is verified, not assumed: at every resume
   attempt the checkpoint's stored ``residual_capacity`` is compared
   (``np.allclose``) against a freshly recomputed one; a mismatch evicts and
   rebuilds instead of resuming, logged with cause ``"capacity_stale"``. This
   recomputation is O(n), far cheaper than the O(k*m*n) external-gain rebuild
   it lets most calls skip, so most of the persistence benefit (frontier/proof
   reuse, and avoiding the expensive external-gain rebuild) survives.

Demand/capacity/interaction/host_cost changes to the ``AssignmentInstance``
object itself (as opposed to just the placement) are global and would
invalidate every checkpoint; this experiment never mutates the instance
mid-run (no shocks), so that path is implemented but not exercised.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time

import numpy as np

from .anytime_gap_certified_repair import (
    AnytimeRepairCheckpoint,
    advance_anytime_repair,
    initialize_anytime_repair,
)
from .alns_baseline import _repair_greedy, _repair_regret2
from .destroy_repair_analysis import build_destroy_repair_cache
from .feasibility import resource_usage
from .instance import AssignmentInstance
from .matched_lns_controller import RepairPolicyContext, RepairPolicyOutcome


def _residual_capacity_fresh(
    instance: AssignmentInstance,
    placement: np.ndarray,
    cache,
    tol: float = 1e-9,
) -> bool:
    """Cheap (O(n)) freshness check for a checkpoint's cached residual capacity.

    Mirrors exactly how build_destroy_repair_cache computes residual_capacity,
    without paying for the much more expensive external_gain/pair_gain rebuild.
    """
    usage = resource_usage(instance, placement)
    residual = instance.capacities - usage
    for node in cache.nodes:
        residual[placement[node]] += instance.demands[node]
    return bool(np.allclose(residual, cache.residual_capacity, atol=tol))


def _material_gap(gap: float, gain: float, absolute: float, ratio: float) -> bool:
    return gap > absolute and gap / max(abs(gain), 1.0) >= ratio


# ---------------------------------------------------------------------------
# Variant A: heuristic baseline
# ---------------------------------------------------------------------------

class HeuristicRepairPolicy:
    """Wraps one of alns_baseline's heuristic repair functions unchanged."""

    def __init__(self, repair_fn):
        self._repair_fn = repair_fn

    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome:
        target, gain = self._repair_fn(ctx.instance, ctx.placement, ctx.nodes, ctx.rng)
        t0 = time.perf_counter()
        cache = build_destroy_repair_cache(ctx.instance, ctx.placement, ctx.nodes)
        rebuild_ms = (time.perf_counter() - t0) * 1000.0
        return RepairPolicyOutcome(
            target_hosts=target,
            gain=float(gain),
            cache=cache,
            diagnostics={
                "rebuild_ms": rebuild_ms, "setup_ms": 0.0, "solve_ms": 0.0,
                "scheduling_ms": 0.0, "resumed": 0, "slices_completed": 0,
            },
        )

    def notify_move(self, instance, accepted, nodes, iteration) -> None:
        pass


def make_heuristic_repair_arms() -> tuple[HeuristicRepairPolicy, HeuristicRepairPolicy]:
    return HeuristicRepairPolicy(_repair_greedy), HeuristicRepairPolicy(_repair_regret2)


# ---------------------------------------------------------------------------
# Variant B: restart PCR (no persistence)
# ---------------------------------------------------------------------------

class RestartPCRPolicy:
    def __init__(self, slice_ms: float, epsilon_target: float = 0.0):
        self.slice_ms = slice_ms
        self.epsilon_target = epsilon_target

    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome:
        t0 = time.perf_counter()
        cache = build_destroy_repair_cache(ctx.instance, ctx.placement, ctx.nodes)
        rebuild_ms = (time.perf_counter() - t0) * 1000.0

        checkpoint = initialize_anytime_repair(ctx.instance, ctx.placement, ctx.nodes, prebuilt_cache=cache)
        slice_budget = min(self.slice_ms, max(0.0, ctx.remaining_budget_ms - ctx.deadline_guard_ms))
        result = advance_anytime_repair(
            ctx.instance, checkpoint, budget_ms=max(0.0, slice_budget), epsilon_target=self.epsilon_target,
        )
        return RepairPolicyOutcome(
            target_hosts=result.move.target_hosts,
            gain=float(result.move.gain),
            cache=cache,
            diagnostics={
                "rebuild_ms": rebuild_ms,
                "setup_ms": result.stats.setup_elapsed_ms,
                "solve_ms": result.stats.slice_elapsed_ms,
                "scheduling_ms": 0.0,
                "resumed": 0,
                "slices_completed": result.stats.slices_completed,
                "certificate_additive_gap": result.certificate.additive_gap,
                "certificate_relative_gap": result.certificate.relative_gap,
                "certificate_exact": int(result.certificate.exact),
                "certificate_epsilon_certified": int(result.certificate.epsilon_certified),
            },
        )

    def notify_move(self, instance, accepted, nodes, iteration) -> None:
        pass  # nothing persists, so there is nothing to invalidate


# ---------------------------------------------------------------------------
# Shared persistence machinery for Variants C and D
# ---------------------------------------------------------------------------

@dataclass
class PersistentCheckpointEntry:
    checkpoint: AnytimeRepairCheckpoint
    next_slice_ms: float
    times_resumed: int = 0
    created_iteration: int = 0
    # The checkpoint's cache measures gains relative to the placement at build
    # time.  After this destroy set's own repair is accepted, the new placement
    # sits at gain ``gain_offset`` in that frame, so gains reported to the
    # controller are rebased by subtracting it.  The additive certificate is a
    # difference of two values in the same frame and needs no rebasing.
    gain_offset: float = 0.0
    last_returned_gain: float = 0.0

    def rebased(self, frame_gain: float) -> float:
        return float(frame_gain) - self.gain_offset


@dataclass
class PersistentPCRMemory:
    checkpoints: dict[tuple[int, ...], PersistentCheckpointEntry] = field(default_factory=dict)
    log: list[dict[str, object]] = field(default_factory=list)

    def _record(self, iteration: int, event: str, cause: str, destroy_set_nodes: tuple[int, ...],
                moved_nodes: tuple[int, ...], overlap_size: int, times_resumed_cumulative: int) -> None:
        self.log.append(dict(
            iteration=iteration, event=event, cause=cause,
            destroy_set_nodes=destroy_set_nodes, moved_nodes=moved_nodes,
            overlap_size=overlap_size, times_resumed_cumulative=times_resumed_cumulative,
        ))

    def on_accepted_move(self, instance: AssignmentInstance, moved_nodes: tuple[int, ...], iteration: int,
                         produced_here: bool = True) -> None:
        """Invalidate every OTHER checkpoint whose cache depends on a node
        whose host just changed. The checkpoint for ``moved_nodes`` itself is
        kept: accepting one of a destroy-set's own proposed repairs only
        changes that destroy-set's own (already-"free") nodes, never a fixed
        node's host, so its frontier and certificate remain valid.  Its gains,
        however, are measured from the build-time hosts, so the accepted
        repair's frame gain becomes the offset for later reported gains.
        """
        own = self.checkpoints.get(tuple(moved_nodes))
        if own is not None and produced_here:
            own.gain_offset = own.last_returned_gain
        elif own is not None:
            # Another repair arm moved this destroy set; the checkpoint's
            # incumbent is not the new placement, so it cannot be rebased.
            self.checkpoints.pop(tuple(moved_nodes))
            self._record(iteration, "evicted", "moved_by_other_arm", tuple(moved_nodes),
                         tuple(int(v) for v in moved_nodes), len(moved_nodes), own.times_resumed)
        moved = np.asarray(moved_nodes, dtype=int)
        adjacent_mask = (
            np.any(instance.interaction[moved] != 0, axis=0)
            | np.any(instance.interaction[:, moved] != 0, axis=1)
        )
        affected = set(np.flatnonzero(adjacent_mask).tolist()) | set(moved.tolist())
        for key in list(self.checkpoints):
            if key == tuple(moved_nodes):
                continue  # handled above
            overlap = affected.intersection(key)
            if overlap:
                entry = self.checkpoints.pop(key)
                self._record(iteration, "evicted", "interaction_adjacent_move", key,
                              tuple(int(v) for v in moved_nodes), len(overlap), entry.times_resumed)


# ---------------------------------------------------------------------------
# Variant C: persistent PCR, fixed slice budget, no certificate scheduling
# ---------------------------------------------------------------------------

class PersistentPCRPolicy:
    def __init__(self, slice_ms: float, epsilon_target: float = 0.0):
        self.slice_ms = slice_ms
        self.epsilon_target = epsilon_target
        self.memory = PersistentPCRMemory()

    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome:
        self._last_call_iteration = ctx.iteration
        entry = self.memory.checkpoints.get(ctx.nodes)
        if entry is not None and not _residual_capacity_fresh(ctx.instance, ctx.placement, entry.checkpoint.cache):
            self.memory._record(ctx.iteration, "evicted", "capacity_stale", ctx.nodes, (), 0, entry.times_resumed)
            entry = None
        resumed = entry is not None
        rebuild_ms = 0.0

        if entry is None:
            t0 = time.perf_counter()
            cache = build_destroy_repair_cache(ctx.instance, ctx.placement, ctx.nodes)
            rebuild_ms = (time.perf_counter() - t0) * 1000.0
            checkpoint = initialize_anytime_repair(ctx.instance, ctx.placement, ctx.nodes, prebuilt_cache=cache)
            entry = PersistentCheckpointEntry(checkpoint=checkpoint, next_slice_ms=self.slice_ms,
                                               created_iteration=ctx.iteration)
            self.memory._record(ctx.iteration, "created", "", ctx.nodes, (), 0, 0)
        else:
            entry.times_resumed += 1
            self.memory._record(ctx.iteration, "resumed", "", ctx.nodes, (), 0, entry.times_resumed)

        cache = entry.checkpoint.cache
        slice_budget = min(self.slice_ms, max(0.0, ctx.remaining_budget_ms - ctx.deadline_guard_ms))
        result = advance_anytime_repair(
            ctx.instance, entry.checkpoint, budget_ms=max(0.0, slice_budget), epsilon_target=self.epsilon_target,
        )
        entry.checkpoint = result.checkpoint
        entry.last_returned_gain = float(result.move.gain)
        self.memory.checkpoints[ctx.nodes] = entry

        return RepairPolicyOutcome(
            target_hosts=result.move.target_hosts,
            gain=entry.rebased(result.move.gain),
            cache=cache,
            diagnostics={
                "rebuild_ms": rebuild_ms,
                "setup_ms": result.stats.setup_elapsed_ms if not resumed else 0.0,
                "solve_ms": result.stats.slice_elapsed_ms,
                "scheduling_ms": 0.0,
                "resumed": int(resumed),
                "slices_completed": result.stats.slices_completed,
                "certificate_additive_gap": result.certificate.additive_gap,
                "certificate_relative_gap": result.certificate.relative_gap,
                "certificate_exact": int(result.certificate.exact),
                "certificate_epsilon_certified": int(result.certificate.epsilon_certified),
            },
        )

    def notify_move(self, instance, accepted, nodes, iteration) -> None:
        if accepted:
            self.memory.on_accepted_move(instance, nodes, iteration,
                                         produced_here=getattr(self, "_last_call_iteration", None) == iteration)


# ---------------------------------------------------------------------------
# Variant D: certificate-guided persistent PCR
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CertGuidedConfig:
    """Fixed before held-out evaluation -- these are AGCI's existing defaults,
    not tuned on this experiment's data."""

    root_gap_ratio_trigger: float = 0.04
    root_gap_absolute_trigger: float = 1e-9
    resume_gap_ratio: float = 0.02
    resume_gap_absolute: float = 1e-9
    initial_slice_ms: float = 2.0
    slice_growth: float = 2.0
    maximum_slice_ms: float = 16.0
    max_slices_per_call: int = 3
    epsilon_target: float = 0.0


class CertGuidedPersistentPCRPolicy:
    def __init__(self, config: CertGuidedConfig | None = None):
        self.config = config or CertGuidedConfig()
        self.memory = PersistentPCRMemory()

    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome:
        cfg = self.config
        self._last_call_iteration = ctx.iteration
        sched_t0 = time.perf_counter()
        entry = self.memory.checkpoints.get(ctx.nodes)
        if entry is not None and not _residual_capacity_fresh(ctx.instance, ctx.placement, entry.checkpoint.cache):
            self.memory._record(ctx.iteration, "evicted", "capacity_stale", ctx.nodes, (), 0, entry.times_resumed)
            entry = None
        resumed = entry is not None
        rebuild_ms = 0.0
        setup_ms = 0.0
        event = ""

        if entry is None:
            t0 = time.perf_counter()
            cache = build_destroy_repair_cache(ctx.instance, ctx.placement, ctx.nodes)
            rebuild_ms = (time.perf_counter() - t0) * 1000.0
            heuristic_target, heuristic_gain = _repair_greedy(ctx.instance, ctx.placement, ctx.nodes, ctx.rng)
            checkpoint = initialize_anytime_repair(
                ctx.instance, ctx.placement, ctx.nodes,
                initial_target_hosts=heuristic_target, prebuilt_cache=cache,
            )
            setup_ms = checkpoint.setup_elapsed_ms
            entry = PersistentCheckpointEntry(checkpoint=checkpoint, next_slice_ms=cfg.initial_slice_ms,
                                               created_iteration=ctx.iteration)
            self.memory._record(ctx.iteration, "created", "", ctx.nodes, (), 0, 0)

            root_gap = max(0.0, checkpoint.root_upper_bound - checkpoint.best.gain)
            if not _material_gap(root_gap, checkpoint.best.gain, cfg.root_gap_absolute_trigger, cfg.root_gap_ratio_trigger):
                entry.last_returned_gain = float(heuristic_gain)
                self.memory.checkpoints[ctx.nodes] = entry
                self.memory._record(ctx.iteration, "retired_root_gap", "", ctx.nodes, (), 0, 0)
                scheduling_ms = (time.perf_counter() - sched_t0) * 1000.0
                return RepairPolicyOutcome(
                    target_hosts=tuple(int(h) for h in heuristic_target),
                    gain=float(heuristic_gain),
                    cache=cache,
                    diagnostics={
                        "rebuild_ms": rebuild_ms, "setup_ms": setup_ms, "solve_ms": 0.0,
                        "scheduling_ms": scheduling_ms, "resumed": 0, "slices_completed": 0,
                        "certificate_additive_gap": float("nan"), "certificate_relative_gap": float("nan"),
                        "certificate_exact": 0, "certificate_epsilon_certified": 0,
                        "event": "retired_root_gap",
                    },
                )
        else:
            entry.times_resumed += 1
            # Zero-budget peek: refreshes the certificate without expanding any branch
            # (advance_anytime_repair's deadline is met immediately at budget_ms=0).
            peek = advance_anytime_repair(ctx.instance, entry.checkpoint, budget_ms=0.0, epsilon_target=cfg.epsilon_target)
            entry.checkpoint = peek.checkpoint
            entry.last_returned_gain = float(peek.move.gain)
            if peek.certificate.exact or peek.certificate.epsilon_certified:
                self.memory.checkpoints[ctx.nodes] = entry
                self.memory._record(ctx.iteration, "retired_exact", "", ctx.nodes, (), 0, entry.times_resumed)
                scheduling_ms = (time.perf_counter() - sched_t0) * 1000.0
                return RepairPolicyOutcome(
                    target_hosts=peek.move.target_hosts, gain=entry.rebased(peek.move.gain), cache=entry.checkpoint.cache,
                    diagnostics={
                        "rebuild_ms": 0.0, "setup_ms": 0.0, "solve_ms": 0.0,
                        "scheduling_ms": scheduling_ms, "resumed": 1, "slices_completed": 0,
                        "certificate_additive_gap": peek.certificate.additive_gap,
                        "certificate_relative_gap": peek.certificate.relative_gap,
                        "certificate_exact": int(peek.certificate.exact),
                        "certificate_epsilon_certified": int(peek.certificate.epsilon_certified),
                        "event": "retired_exact",
                    },
                )
            if not _material_gap(peek.certificate.additive_gap, entry.rebased(peek.move.gain), cfg.resume_gap_absolute, cfg.resume_gap_ratio):
                self.memory.checkpoints[ctx.nodes] = entry
                self.memory._record(ctx.iteration, "retired_resume_gap", "", ctx.nodes, (), 0, entry.times_resumed)
                scheduling_ms = (time.perf_counter() - sched_t0) * 1000.0
                return RepairPolicyOutcome(
                    target_hosts=peek.move.target_hosts, gain=entry.rebased(peek.move.gain), cache=entry.checkpoint.cache,
                    diagnostics={
                        "rebuild_ms": 0.0, "setup_ms": 0.0, "solve_ms": 0.0,
                        "scheduling_ms": scheduling_ms, "resumed": 1, "slices_completed": 0,
                        "certificate_additive_gap": peek.certificate.additive_gap,
                        "certificate_relative_gap": peek.certificate.relative_gap,
                        "certificate_exact": int(peek.certificate.exact),
                        "certificate_epsilon_certified": int(peek.certificate.epsilon_certified),
                        "event": "retired_resume_gap",
                    },
                )
            self.memory._record(ctx.iteration, "resumed", "", ctx.nodes, (), 0, entry.times_resumed)
            cache = entry.checkpoint.cache

        cache = entry.checkpoint.cache
        scheduling_ms = (time.perf_counter() - sched_t0) * 1000.0

        last_result = None
        solve_ms = 0.0
        for _ in range(cfg.max_slices_per_call):
            slice_budget = min(
                entry.next_slice_ms,
                max(0.0, ctx.remaining_budget_ms - ctx.deadline_guard_ms),
            )
            if slice_budget <= 0.0:
                break
            result = advance_anytime_repair(
                ctx.instance, entry.checkpoint, budget_ms=slice_budget, epsilon_target=cfg.epsilon_target,
            )
            solve_ms += result.stats.slice_elapsed_ms
            entry.checkpoint = result.checkpoint
            last_result = result
            if result.certificate.exact or result.certificate.epsilon_certified:
                break
            if not _material_gap(result.certificate.additive_gap, entry.rebased(result.move.gain), cfg.resume_gap_absolute, cfg.resume_gap_ratio):
                break
            entry.next_slice_ms = min(cfg.maximum_slice_ms, entry.next_slice_ms * cfg.slice_growth)

        entry.last_returned_gain = float(entry.checkpoint.best.gain)
        self.memory.checkpoints[ctx.nodes] = entry

        if last_result is None:
            # Global budget exhausted before any slice could run this call.
            return RepairPolicyOutcome(
                target_hosts=entry.checkpoint.best.target_hosts,
                gain=entry.rebased(entry.checkpoint.best.gain),
                cache=cache,
                diagnostics={
                    "rebuild_ms": rebuild_ms, "setup_ms": setup_ms, "solve_ms": 0.0,
                    "scheduling_ms": scheduling_ms, "resumed": int(resumed), "slices_completed": 0,
                    "certificate_additive_gap": float("nan"), "certificate_relative_gap": float("nan"),
                    "certificate_exact": 0, "certificate_epsilon_certified": 0, "event": "no_budget",
                },
            )

        return RepairPolicyOutcome(
            target_hosts=last_result.move.target_hosts,
            gain=entry.rebased(last_result.move.gain),
            cache=cache,
            diagnostics={
                "rebuild_ms": rebuild_ms,
                "setup_ms": setup_ms,
                "solve_ms": solve_ms,
                "scheduling_ms": scheduling_ms,
                "resumed": int(resumed),
                "slices_completed": last_result.stats.slices_completed,
                "certificate_additive_gap": last_result.certificate.additive_gap,
                "certificate_relative_gap": last_result.certificate.relative_gap,
                "certificate_exact": int(last_result.certificate.exact),
                "certificate_epsilon_certified": int(last_result.certificate.epsilon_certified),
                "event": "sliced",
            },
        )

    def notify_move(self, instance, accepted, nodes, iteration) -> None:
        if accepted:
            self.memory.on_accepted_move(instance, nodes, iteration,
                                         produced_here=getattr(self, "_last_call_iteration", None) == iteration)
