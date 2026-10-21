"""Trace-dynamic PCR policy with cache-equality continuation across instance changes.

This module extends the package's persistent PCR repair policy only for the
pre-registered E-DYN trace-driven confirmation study.  Cross-state resumption
uses the same rule frozen for P1: a checkpoint may survive an external traffic
change only if a freshly rebuilt cache under the current instance and placement
has exactly equal external gains, pair gains, and residual capacity.

When that rule passes, search continues against the checkpoint's snapshot
instance.  This mirrors P1: the local repair problem represented by the cache is
identical even if unrelated parts of the global interaction matrix changed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from .anytime_gap_certified_repair import advance_anytime_repair, initialize_anytime_repair
from .destroy_repair_analysis import build_destroy_repair_cache
from .matched_lns_controller import RepairPolicyContext, RepairPolicyOutcome
from .matched_lns_policies import (
    PersistentCheckpointEntry,
    PersistentPCRMemory,
    _residual_capacity_fresh,
)


def cache_equal_for_resume(a, b) -> bool:
    """P1-compatible exact cache equality; original_hosts are intentionally omitted."""
    return (
        np.array_equal(a.external_gain, b.external_gain)
        and np.array_equal(a.pair_gain, b.pair_gain)
        and np.array_equal(a.residual_capacity, b.residual_capacity)
    )


@dataclass(frozen=True)
class TransitionAudit:
    examined: int
    compatible: int
    incompatible: int
    discarded_expansions: int
    elapsed_ms: float


class TracePersistentPCRPolicy:
    """Persistent PCR with explicit cross-state compatibility reconciliation.

    Within a temporal state this behaves like ``PersistentPCRPolicy``.  At an
    external state transition, call ``reconcile_state`` before using the policy
    on the new instance.  Compatible checkpoints are retained, incompatible
    checkpoints are discarded, and the compatibility-check wall time can be
    counted against the next state's fixed controller budget.
    """

    def __init__(
        self,
        slice_ms: float,
        epsilon_target: float = 0.0,
        numeric_mode: str = "safe",
        tol: float = 0.0,
    ) -> None:
        self.slice_ms = float(slice_ms)
        self.epsilon_target = float(epsilon_target)
        self.numeric_mode = numeric_mode
        self.tol = float(tol)
        self.memory = PersistentPCRMemory()
        self._snapshots: dict[tuple[int, ...], object] = {}
        self._carried_unconsumed: set[tuple[int, ...]] = set()
        self.cross_state_resume_calls = 0
        self.cross_state_transition_log: list[dict[str, object]] = []

    def clear_cross_state(self, state_index: int, reason: str = "forced_reset") -> TransitionAudit:
        t0 = time.perf_counter()
        examined = len(self.memory.checkpoints)
        discarded = sum(int(e.checkpoint.partial_branches_expanded) for e in self.memory.checkpoints.values())
        self.memory.checkpoints.clear()
        self._snapshots.clear()
        self._carried_unconsumed.clear()
        elapsed = (time.perf_counter() - t0) * 1000.0
        self.cross_state_transition_log.append({
            "state_index": int(state_index), "action": reason,
            "examined": examined, "compatible": 0, "incompatible": examined,
            "discarded_expansions": discarded, "elapsed_ms": elapsed,
        })
        return TransitionAudit(examined, 0, examined, discarded, elapsed)

    def reconcile_state(self, instance, placement: np.ndarray, state_index: int) -> TransitionAudit:
        """Retain only checkpoints whose complete local cache remains identical."""
        t0 = time.perf_counter()
        examined = compatible = incompatible = discarded = 0
        carried: set[tuple[int, ...]] = set()
        for key in list(self.memory.checkpoints):
            entry = self.memory.checkpoints[key]
            examined += 1
            try:
                fresh = build_destroy_repair_cache(instance, placement, key)
                ok = cache_equal_for_resume(fresh, entry.checkpoint.cache)
            except Exception:
                ok = False
            if ok:
                compatible += 1
                carried.add(key)
            else:
                incompatible += 1
                discarded += int(entry.checkpoint.partial_branches_expanded)
                self.memory.checkpoints.pop(key, None)
                self._snapshots.pop(key, None)
        self._carried_unconsumed = carried
        elapsed = (time.perf_counter() - t0) * 1000.0
        self.cross_state_transition_log.append({
            "state_index": int(state_index), "action": "reconcile",
            "examined": examined, "compatible": compatible,
            "incompatible": incompatible, "discarded_expansions": discarded,
            "elapsed_ms": elapsed,
        })
        return TransitionAudit(examined, compatible, incompatible, discarded, elapsed)

    def __call__(self, ctx: RepairPolicyContext) -> RepairPolicyOutcome:
        self._last_call_iteration = ctx.iteration
        key = ctx.nodes
        entry = self.memory.checkpoints.get(key)
        if entry is not None and not _residual_capacity_fresh(ctx.instance, ctx.placement, entry.checkpoint.cache):
            self.memory._record(ctx.iteration, "evicted", "capacity_stale", key, (), 0, entry.times_resumed)
            self.memory.checkpoints.pop(key, None)
            self._snapshots.pop(key, None)
            self._carried_unconsumed.discard(key)
            entry = None

        resumed = entry is not None
        cross_state_resumed = 0
        rebuild_ms = 0.0
        if entry is None:
            t0 = time.perf_counter()
            cache = build_destroy_repair_cache(ctx.instance, ctx.placement, key)
            rebuild_ms = (time.perf_counter() - t0) * 1000.0
            checkpoint = initialize_anytime_repair(
                ctx.instance,
                ctx.placement,
                key,
                prebuilt_cache=cache,
                tol=self.tol,
                numeric_mode=self.numeric_mode,
            )
            entry = PersistentCheckpointEntry(
                checkpoint=checkpoint,
                next_slice_ms=self.slice_ms,
                created_iteration=ctx.iteration,
            )
            self._snapshots[key] = ctx.instance
            self.memory._record(ctx.iteration, "created", "", key, (), 0, 0)
        else:
            entry.times_resumed += 1
            self.memory._record(ctx.iteration, "resumed", "", key, (), 0, entry.times_resumed)
            if key in self._carried_unconsumed:
                cross_state_resumed = 1
                self.cross_state_resume_calls += 1
                self._carried_unconsumed.discard(key)

        cache = entry.checkpoint.cache
        search_instance = self._snapshots.get(key, ctx.instance)
        slice_budget = min(self.slice_ms, max(0.0, ctx.remaining_budget_ms - ctx.deadline_guard_ms))
        result = advance_anytime_repair(
            search_instance,
            entry.checkpoint,
            budget_ms=max(0.0, slice_budget),
            epsilon_target=self.epsilon_target,
            tol=self.tol,
        )
        entry.checkpoint = result.checkpoint
        entry.last_returned_gain = float(result.move.gain)
        self.memory.checkpoints[key] = entry

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
                "cross_state_resumed": cross_state_resumed,
                "slices_completed": result.stats.slices_completed,
                "certificate_additive_gap": result.certificate.additive_gap,
                "certificate_relative_gap": result.certificate.relative_gap,
                "certificate_exact": int(result.certificate.exact),
                "certificate_epsilon_certified": int(result.certificate.epsilon_certified),
            },
        )

    def notify_move(self, instance, accepted, nodes, iteration) -> None:
        if not accepted:
            return
        before = set(self.memory.checkpoints)
        self.memory.on_accepted_move(
            instance,
            nodes,
            iteration,
            produced_here=getattr(self, "_last_call_iteration", None) == iteration,
        )
        after = set(self.memory.checkpoints)
        for key in before - after:
            self._snapshots.pop(key, None)
            self._carried_unconsumed.discard(key)
