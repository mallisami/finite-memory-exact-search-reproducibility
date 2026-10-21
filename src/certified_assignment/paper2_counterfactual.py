from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import pickle
from typing import Iterable

from .anytime_gap_certified_repair import (
    AnytimeRepairCheckpoint,
    GuidancePolicy,
    initialize_anytime_repair,
)
from .instance import AssignmentInstance
from .step_resumption import advance_anytime_repair_steps


@dataclass(frozen=True)
class CounterfactualReusePair:
    """Matched restart/resume states for one exact repair context.

    ``restart_checkpoint`` is the untouched initial search state.  The
    ``resume_checkpoint`` is the same state after ``invested_branch_pops``
    deterministic branch pops.  Keeping both states lets a label collector
    compare restart and resume without reconstructing a possibly different
    initial incumbent or queue ordering.
    """

    restart_checkpoint: AnytimeRepairCheckpoint
    resume_checkpoint: AnytimeRepairCheckpoint
    invested_branch_pops: int


@dataclass(frozen=True)
class CounterfactualReuseLabel:
    destroy_set: tuple[int, ...]
    invested_branch_pops: int
    checkpoint_bytes: int
    future_pop_cap: int
    resume_branch_pops: int
    restart_branch_pops: int
    resume_exact: bool
    restart_exact: bool
    resume_gain: float
    restart_gain: float
    resume_additive_gap: float
    restart_additive_gap: float
    saved_branch_pops: int | None
    label_complete: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def make_counterfactual_reuse_pair(
    instance: AssignmentInstance,
    placement,
    nodes: Iterable[int],
    invested_branch_pops: int,
    *,
    initial_target_hosts: Iterable[int] | None = None,
    tol: float = 1e-12,
    guidance_policy: GuidancePolicy | None = None,
    numeric_mode: str = "binary64",
    bound_mode: str = "independent",
) -> CounterfactualReusePair:
    """Create an exactly matched restart/resume pair using deterministic work.

    The helper is intended for Paper-2 label collection.  It initializes one
    search state, deep-copies it, and invests a fixed number of branch pops in
    the retained copy.  The untouched copy is the restart counterfactual.

    The step-counted path deliberately avoids wall-clock budgets, making the
    label independent of machine speed.  The primal dive is disabled on both
    copies so invested and future work use the same best-first work unit.
    """

    if invested_branch_pops < 0:
        raise ValueError("invested_branch_pops must be non-negative")
    seed = initialize_anytime_repair(
        instance,
        placement,
        nodes,
        initial_target_hosts=initial_target_hosts,
        tol=tol,
        guidance_policy=guidance_policy,
        numeric_mode=numeric_mode,
        bound_mode=bound_mode,
    )
    seed.primal_dive_done = True
    restart = deepcopy(seed)
    resume = deepcopy(seed)
    _, _, used = advance_anytime_repair_steps(
        instance,
        resume,
        invested_branch_pops,
        epsilon_target=0.0,
        tol=tol,
    )
    return CounterfactualReusePair(restart, resume, used)


def _advance_to_exact_or_cap(
    instance: AssignmentInstance,
    state: AnytimeRepairCheckpoint,
    pop_cap: int,
    batch_pops: int,
    tol: float,
) -> tuple[int, object, object]:
    if pop_cap < 0:
        raise ValueError("pop_cap must be non-negative")
    if batch_pops < 1:
        raise ValueError("batch_pops must be positive")

    move, cert, _ = advance_anytime_repair_steps(
        instance, state, 0, epsilon_target=0.0, tol=tol
    )
    total = 0
    while not cert.exact and total < pop_cap:
        step = min(batch_pops, pop_cap - total)
        move, cert, used = advance_anytime_repair_steps(
            instance, state, step, epsilon_target=0.0, tol=tol
        )
        total += used
        if used == 0:
            break
    return total, move, cert


def measure_counterfactual_reuse(
    instance: AssignmentInstance,
    pair: CounterfactualReusePair,
    *,
    future_pop_cap: int = 100_000,
    batch_pops: int = 128,
    tol: float | None = None,
) -> CounterfactualReuseLabel:
    """Measure future exact-search work saved by retaining a checkpoint.

    Both branches start from the *same original repair context*:

    * restart: untouched initial checkpoint;
    * resume: checkpoint after already-invested deterministic search work.

    Each branch is advanced until exact closure or ``future_pop_cap`` branch
    pops.  ``saved_branch_pops`` is reported only when both branches close, so
    censored cases are never silently treated as complete labels.
    """

    restart = deepcopy(pair.restart_checkpoint)
    resume = deepcopy(pair.resume_checkpoint)
    if restart.cache.nodes != resume.cache.nodes:
        raise ValueError("restart and resume checkpoints use different destroy sets")
    if restart.instance_fingerprint and resume.instance_fingerprint:
        if restart.instance_fingerprint != resume.instance_fingerprint:
            raise ValueError("restart and resume checkpoints use different instances")
    if restart.context_fingerprint and resume.context_fingerprint:
        if restart.context_fingerprint != resume.context_fingerprint:
            raise ValueError("restart and resume checkpoints use different repair contexts")
    if restart.numeric_mode != resume.numeric_mode or restart.bound_mode != resume.bound_mode:
        raise ValueError("restart and resume checkpoints use different numerical/search modes")

    effective_tol = max(restart.pruning_tol_used, resume.pruning_tol_used) if tol is None else float(tol)
    if effective_tol + 1e-30 < max(restart.pruning_tol_used, resume.pruning_tol_used):
        raise ValueError("tol is smaller than a checkpoint's historical pruning tolerance")

    resume_pops, resume_move, resume_cert = _advance_to_exact_or_cap(
        instance, resume, future_pop_cap, batch_pops, effective_tol
    )
    restart_pops, restart_move, restart_cert = _advance_to_exact_or_cap(
        instance, restart, future_pop_cap, batch_pops, effective_tol
    )

    complete = bool(resume_cert.exact and restart_cert.exact)
    saved = int(restart_pops - resume_pops) if complete else None
    try:
        checkpoint_bytes = len(pickle.dumps(pair.resume_checkpoint, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        checkpoint_bytes = -1

    return CounterfactualReuseLabel(
        destroy_set=tuple(int(v) for v in resume.cache.nodes),
        invested_branch_pops=int(pair.invested_branch_pops),
        checkpoint_bytes=int(checkpoint_bytes),
        future_pop_cap=int(future_pop_cap),
        resume_branch_pops=int(resume_pops),
        restart_branch_pops=int(restart_pops),
        resume_exact=bool(resume_cert.exact),
        restart_exact=bool(restart_cert.exact),
        resume_gain=float(resume_move.gain),
        restart_gain=float(restart_move.gain),
        resume_additive_gap=float(resume_cert.additive_gap),
        restart_additive_gap=float(restart_cert.additive_gap),
        saved_branch_pops=saved,
        label_complete=complete,
    )
