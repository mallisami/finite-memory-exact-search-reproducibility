#!/usr/bin/env python3
"""Post hoc second-scale residence sensitivity: 32 nodes, 8 hosts, destroy 12.

The published finite-memory residence comparison runs at the (24, 6,
destroy 12) operating point selected by the structural memory screen (Online
Resource 1, S4.1), which also characterized (32, 8) and (40, 10) scales. This
analysis repeats the primary learned-versus-empirical-compatible comparison at
the neighbouring (32, 8, destroy 12) scale, with everything else unchanged:
the same 45 seeds (3301-3315 x 3 families), 200 decisions, 8-pop repair cap,
the frozen P6 predictor applied without retraining, the same exact byte
allocator and compatibility semantics, and the case-specific 25%-of-keep-all
byte budget. Residence endpoints are deterministic, so the result is hardware
independent.

Scale injection: paper2_online_pilot hardcodes make_domain_case(domain, 24, 6)
inside generate_replay_trace and run_online_replay; this script wraps the
module-level make_domain_case to substitute (32, 8) without modifying any
frozen package code.

Status: post hoc reviewer-response analysis, not prespecified. Generated
2026-10-17 in a Claude session; authors must re-verify by rerunning.
"""
from __future__ import annotations

import functools
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
from certified_assignment.domain_instances import make_domain_case  # noqa: E402

N_NODES, N_HOSTS, DESTROY = 32, 8, 12
DOMAINS = ("generic", "workflow", "microservice")
SEEDS = tuple(range(3301, 3316))
SLICE_POPS, ITERATIONS = 8, 200
BOOT_SEED, BOOT_REPS = 77001, 10000

pilot.make_domain_case = functools.partial(  # scale injection, frozen code untouched
    lambda d, _n, _m, seed, n, m: make_domain_case(d, n, m, seed=seed),
    n=N_NODES, m=N_HOSTS)


def _case(args):
    domain, seed = args
    trace = pilot.generate_replay_trace(domain, seed, iterations=ITERATIONS,
                                        destroy_size=DESTROY)
    keep = pilot.run_online_replay(domain, seed, trace, policy_name="keep_all",
                                   slice_pops=SLICE_POPS)
    budget = max(max(1, keep.max_checkpoint_size_bytes),
                 int(round(0.25 * max(1, keep.peak_bytes))))
    rows = [keep.to_dict()]
    predictor = pilot.FrozenP6Predictor(PKG / "02_Authoritative_Experimental_Evidence")
    for pol in ("empirical_compatible", "learned"):
        r = pilot.run_online_replay(domain, seed, trace, policy_name=pol,
                                    slice_pops=SLICE_POPS, budget_bytes=budget,
                                    budget_fraction=0.25,
                                    predictor=predictor if pol == "learned" else None)
        rows.append(r.to_dict())
    return rows


def main():
    out_dir = Path(__file__).parent
    rows = []
    tasks = [(d, s) for d in DOMAINS for s in SEEDS]
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_case, t): t for t in tasks}
        for i, f in enumerate(as_completed(futs), 1):
            rows.extend(f.result())
            print(f"[{i}/{len(tasks)}] {futs[f]}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "p7_second_scale_32x8_runs.csv", index=False)
    ka = df[df.policy == "keep_all"].set_index(["domain", "instance_seed"])[
        "reused_prior_branch_pops"]
    nrw = {p: (df[df.policy == p].set_index(["domain", "instance_seed"])[
        "reused_prior_branch_pops"] / ka).sort_index()
        for p in ("learned", "empirical_compatible")}
    d = (nrw["learned"] - nrw["empirical_compatible"]).values
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(d), size=(BOOT_REPS, len(d)))
    m = d[idx].mean(axis=1)
    res = {
        "scale": {"nodes": N_NODES, "hosts": N_HOSTS, "destroy_size": DESTROY,
                  "slice_pops": SLICE_POPS, "budget": "25% of case keep-all peak"},
        "mean_nrw": {p: float(v.mean()) for p, v in nrw.items()},
        "learned_minus_empirical": {
            "mean": float(d.mean()),
            "ci95": [float(np.quantile(m, .025)), float(np.quantile(m, .975))],
            "positive_cases": int((d > 0).sum()), "negative_cases": int((d < 0).sum()),
            "ties": int((d == 0).sum())},
        "keepall_structure": {
            "mean_keepall_reused_pops": float(ka.mean()),
            "mean_peak_bytes": float(df[df.policy == "keep_all"].peak_bytes.mean()),
            "mean_peak_active_checkpoints": float(
                df[df.policy == "keep_all"].peak_active_checkpoints.mean())},
    }
    (out_dir / "P7_SECOND_SCALE_32x8_ANALYSIS.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
