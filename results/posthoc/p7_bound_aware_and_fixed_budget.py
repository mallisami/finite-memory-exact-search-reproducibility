#!/usr/bin/env python3
"""Two reviewer-response residence analyses on the P7 graph-retention harness.

Both analyses reuse the frozen P7 machinery (traces, repair engine, exact byte
allocator, compatibility semantics) unchanged from
04_Source_Code_and_Tests/certified_assignment/paper2_online_pilot.py, and both
are deterministic residence (work) endpoints, so they are hardware independent.
They are post hoc reviewer-response analyses, not part of the prespecified
protocol; eligibility was fixed before results were inspected and the same 45
cases (3 domains x seeds 3301-3315), 200 iterations, destroy size 12 and
8-pop repair cap are reused unchanged.

Analysis A: bound-aware mechanism-matched comparators (UB-inspired).
  The Related Work discusses the UB/SYS limited-memory schemes of Wang et al.
  (CP 2022) as the closest search-aware precedents but does not reproduce them
  because their child-specific bound bookkeeping is not represented in the
  serialized frontier. The closest faithful analogue expressible on this
  checkpoint representation values a dormant frontier by its certified
  remaining admissible improvement:
      bound_gap:      v_i = additive certified gap of the stored frontier
                            (frontier upper bound minus incumbent gain)
      bound_gap_work: v_i = gap_norm_i * W_i, where gap_norm_i is the
                            relative certified gap clipped to [0, 1]
                            (a work-weighted variant on the same scale
                            as the deployed p*W values)
  Both use the SAME exact byte-constrained allocator and compatibility gates
  as the learned and empirical-compatible policies; only the stored value
  changes, exactly like the deployed ablations. bound_gap is designated
  primary between the two before execution; bound_gap_work is descriptive.

Analysis B: fixed absolute byte budget (deployability sensitivity).
  The published budgets are case-specific fractions of each case's keep-all
  peak, an offline normalization unavailable to a deployed controller. Here a
  single absolute budget B_fixed = median over the 45 retained case-specific
  25% budgets (p7_confirmatory_budgets.csv, fixed before execution) is applied
  uniformly to every case, for learned, empirical-compatible and both
  bound-aware policies.

Endpoints: keep-all-normalized reusable work (NRW) per policy per case; paired
learned-minus-comparator effects with 10,000-resample case bootstrap intervals
(seed 77001, matching the published P7 analysis convention).

Validation built in: the keep-all, 25%-budget learned and 25%-budget
empirical-compatible replays must reproduce the retained
p7_confirmatory_runs.csv rows exactly; the script fails loudly otherwise.

Generated 2026-10-17 in a Claude session from the frozen package code and
retained inputs only. Re-verify by rerunning before citing.
"""
from __future__ import annotations

import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

warnings.filterwarnings("ignore")

PKG = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()
sys.path.insert(0, str(PKG / "04_Source_Code_and_Tests"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import certified_assignment.paper2_online_pilot as pilot  # noqa: E402
from certified_assignment.anytime_gap_certified_repair import _certificate  # noqa: E402

DOMAINS = ("generic", "workflow", "microservice")
SEEDS = tuple(range(3301, 3316))
ITERATIONS, DESTROY_SIZE, SLICE_POPS = 200, 12, 8
BOOT_SEED, BOOT_REPS = 77001, 10000

_ACTIVE_BOUND_POLICY = []  # set per-process while a bound-aware replay runs

_OrigStored = pilot.StoredCheckpoint


def _stored_with_bound_value(**kw):
    """Replace the stored expected value for bound-aware policies.

    paper2_online_pilot computes expected_value = p * cumulative_pops at the
    single StoredCheckpoint construction site in OnlineStepPolicy.repair().
    For bound-aware policies the active policy object stashes the certified
    gap of the entry just serialized (captured in _serialize below), and the
    stored value becomes that gap (bound_gap) or the relative-gap-weighted
    invested work (bound_gap_work). Every other field and the allocator are
    untouched.
    """
    if _ACTIVE_BOUND_POLICY:
        pol = _ACTIVE_BOUND_POLICY[0]
        gap_abs, gap_rel = pol._pending_gap
        if pol.bound_variant == "bound_gap":
            kw["expected_value"] = float(max(gap_abs, 0.0))
        else:  # bound_gap_work
            kw["expected_value"] = float(np.clip(gap_rel, 0.0, 1.0)) * float(kw["cumulative_pops"])
    return _OrigStored(**kw)


class BoundAwarePolicy(pilot.OnlineStepPolicy):
    """UB-inspired bound-aware valuation on the unchanged P7 machinery."""

    def __init__(self, variant: str, **kw):
        super().__init__("empirical_compatible", **kw)  # reuse deployable bookkeeping
        self.bound_variant = variant
        self._pending_gap = (0.0, 0.0)

    def _serialize(self, entry):
        cert = _certificate(entry.checkpoint, epsilon_target=0.0,
                            tol=float(entry.checkpoint.pruning_tol_used))
        self._pending_gap = (float(cert.additive_gap), float(cert.relative_gap))
        return super()._serialize(entry)

    def _score_probability(self, **kw):  # stored probability field only
        return 1e-6  # unused for value; overwritten by _stored_with_bound_value


_OrigPolicyCls = pilot.OnlineStepPolicy


def run_bound(domain, seed, trace, variant, budget_bytes, budget_fraction):
    """Run one bound-aware replay through the unchanged run_online_replay.

    run_online_replay instantiates the policy via the module-level name
    OnlineStepPolicy, so a factory patch injects BoundAwarePolicy without
    modifying any frozen package code. The factory also registers the policy
    so _stored_with_bound_value can read its stashed certified gap.
    """

    def factory(policy_name, **kw):
        kw.pop("predictor", None)
        kw.pop("future_horizon", None)
        pol = BoundAwarePolicy(variant, slice_pops=kw["slice_pops"],
                               budget_bytes=kw["budget_bytes"])
        _ACTIVE_BOUND_POLICY[:] = [pol]
        return pol

    pilot.OnlineStepPolicy = factory
    pilot.StoredCheckpoint = _stored_with_bound_value
    try:
        result = pilot.run_online_replay(
            domain, seed, trace, policy_name="empirical_compatible",
            slice_pops=SLICE_POPS, budget_bytes=budget_bytes,
            budget_fraction=budget_fraction)
    finally:
        pilot.OnlineStepPolicy = _OrigPolicyCls
        pilot.StoredCheckpoint = _OrigStored
        _ACTIVE_BOUND_POLICY[:] = []
    d = result.to_dict()
    d["policy"] = variant
    return d


def _case(args):
    domain, seed, b_fixed = args
    trace = pilot.generate_replay_trace(domain, seed, iterations=ITERATIONS,
                                        destroy_size=DESTROY_SIZE)
    keep = pilot.run_online_replay(domain, seed, trace, policy_name="keep_all",
                                   slice_pops=SLICE_POPS)
    peak, max_cp = max(1, keep.peak_bytes), max(1, keep.max_checkpoint_size_bytes)
    b_case25 = max(max_cp, int(round(0.25 * peak)))
    rows = [keep.to_dict()]
    predictor = pilot.FrozenP6Predictor(PKG / "02_Authoritative_Experimental_Evidence")
    for budget, frac in ((b_case25, 0.25), (max(max_cp, b_fixed), -1.0)):
        for pol in ("empirical_compatible", "learned"):
            r = pilot.run_online_replay(
                domain, seed, trace, policy_name=pol, slice_pops=SLICE_POPS,
                budget_bytes=budget, budget_fraction=frac,
                predictor=predictor if pol == "learned" else None)
            rows.append(r.to_dict())
        for variant in ("bound_gap", "bound_gap_work"):
            rows.append(run_bound(domain, seed, trace, variant, budget, frac))
    return rows


def _boot(diffs):
    a = np.asarray(diffs, float)
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(a), size=(BOOT_REPS, len(a)))
    m = a[idx].mean(axis=1)
    return float(a.mean()), float(np.quantile(m, .025)), float(np.quantile(m, .975))


def main():
    out_dir = Path(__file__).parent
    retained_budgets = pd.read_csv(
        PKG / "02_Authoritative_Experimental_Evidence/06_P7_Confirmatory_Retention"
              "/results/p7_confirmatory_budgets.csv")
    b_fixed = int(retained_budgets.query("budget_fraction == 0.25")["budget_bytes"].median())
    print(f"B_fixed (median retained 25% budget) = {b_fixed} bytes", flush=True)

    tasks = [(d, s, b_fixed) for d in DOMAINS for s in SEEDS]
    rows = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_case, t): t for t in tasks}
        for i, f in enumerate(as_completed(futs), 1):
            rows.extend(f.result())
            print(f"[{i}/{len(tasks)}] {futs[f][0]} {futs[f][1]}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "p7_bound_aware_fixed_budget_runs.csv", index=False)

    # --- replication gate against retained confirmatory rows -----------------
    retained = pd.read_csv(
        PKG / "02_Authoritative_Experimental_Evidence/06_P7_Confirmatory_Retention"
              "/results/p7_confirmatory_runs.csv")
    gate = []
    for pol in ("keep_all", "empirical_compatible", "learned"):
        mine = df[(df.policy == pol) & (df.budget_fraction.isin([0.25]) | (pol == "keep_all"))]
        ref = retained[(retained.policy == pol) &
                       ((retained.budget_fraction == 0.25) | (pol == "keep_all"))]
        key = ["domain", "instance_seed"]
        m = mine.set_index(key)["reused_prior_branch_pops"].sort_index()
        r = ref.set_index(key)["reused_prior_branch_pops"].sort_index()
        same = bool((m == r).all()) and len(m) == len(r) == 45
        gate.append({"policy": pol, "exact_match_45_cases": same})
        if not same:
            raise SystemExit(f"REPLICATION GATE FAILED for {pol}")
    print("replication gate: PASS (keep_all, empirical 25%, learned 25% exact)", flush=True)

    # --- NRW analysis ---------------------------------------------------------
    ka = df[df.policy == "keep_all"].set_index(["domain", "instance_seed"])[
        "reused_prior_branch_pops"]
    res = {"B_fixed_bytes": b_fixed, "replication_gate": gate, "budgets": {}}
    for frac, label in ((0.25, "case_specific_25pct"), (-1.0, "fixed_absolute_bytes")):
        sub = df[df.budget_fraction == frac]
        nrw = {}
        for pol in ("learned", "empirical_compatible", "bound_gap", "bound_gap_work"):
            s = sub[sub.policy == pol].set_index(["domain", "instance_seed"])[
                "reused_prior_branch_pops"] / ka
            nrw[pol] = s.sort_index()
        entry = {"mean_nrw": {p: float(v.mean()) for p, v in nrw.items()}}
        for comp in ("empirical_compatible", "bound_gap", "bound_gap_work"):
            d = (nrw["learned"] - nrw[comp]).values
            mean, lo, hi = _boot(d)
            entry[f"learned_minus_{comp}"] = {
                "mean": mean, "ci95": [lo, hi],
                "positive_cases": int((d > 0).sum()), "negative_cases": int((d < 0).sum()),
                "ties": int((d == 0).sum())}
        res["budgets"][label] = entry
    (out_dir / "P7_BOUND_AWARE_FIXED_BUDGET_ANALYSIS.json").write_text(
        json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
