"""Frozen RQ1 external comparator extension (FIFO/LRU/Random Replacement)."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
import pandas as pd

from certified_assignment.paper2_external_eviction import run_external_online_replay
from certified_assignment.paper2_online_pilot import generate_replay_trace

DOMAINS = ("generic", "workflow", "microservice")
SEEDS = tuple(range(3301, 3316))
BUDGETS = (0.25, 0.50, 0.75)
DESTROY_SIZE = 12
ITERATIONS = 200
SLICE_POPS = 8
RANDOM_REPETITIONS = 5
BOOTSTRAP_REPS = 10_000

_DOMAIN_CODE = {"generic": 1, "workflow": 2, "microservice": 3}
_BUDGET_CODE = {0.25: 25, 0.50: 50, 0.75: 75}
_POLICY_CODE = {"fifo": 1, "lru": 2, "random": 3}


def random_eviction_seed(domain: str, instance_seed: int, budget_fraction: float, repetition: int) -> int:
    """Frozen unique seed formula, repetition is 1..5."""
    return (
        10_000_000 * int(repetition)
        + 1_000_000 * _DOMAIN_CODE[domain]
        + 100 * int(instance_seed)
        + _BUDGET_CODE[float(budget_fraction)]
    )


def _bootstrap_mean_ci(x, *, seed: int):
    a = np.asarray(x, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, len(a), size=(BOOTSTRAP_REPS, len(a)))
    means = a[idx].mean(axis=1)
    return float(a.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _run_case(args):
    domain, instance_seed, budget_rows = args
    trace = generate_replay_trace(domain, instance_seed, iterations=ITERATIONS, destroy_size=DESTROY_SIZE)
    rows = []
    for frac in BUDGETS:
        budget = int(budget_rows[float(frac)])
        for policy in ("fifo", "lru"):
            r = run_external_online_replay(
                domain, instance_seed, trace,
                policy_name=policy, slice_pops=SLICE_POPS,
                budget_bytes=budget, budget_fraction=frac,
            )
            d = r.to_dict(); d["random_repetition"] = np.nan; d["eviction_seed"] = np.nan
            rows.append(d)
        for rep in range(1, RANDOM_REPETITIONS + 1):
            es = random_eviction_seed(domain, instance_seed, frac, rep)
            r = run_external_online_replay(
                domain, instance_seed, trace,
                policy_name="random", slice_pops=SLICE_POPS,
                budget_bytes=budget, budget_fraction=frac, eviction_seed=es,
            )
            d = r.to_dict(); d["random_repetition"] = rep; d["eviction_seed"] = es
            rows.append(d)
    return rows


def _with_matched_metrics(df, authoritative_runs):
    keep = authoritative_runs[authoritative_runs.policy == "keep_all"].set_index(["domain", "instance_seed"])
    restart = authoritative_runs[authoritative_runs.policy == "restart"].set_index(["domain", "instance_seed"])
    rows = []
    for _, r in df.iterrows():
        idx = (r.domain, int(r.instance_seed))
        kk = keep.loc[idx]; rr = restart.loc[idx]
        denom = max(abs(float(rr.best_objective)), 1e-12)
        x = r.to_dict()
        x.update(
            reuse_fraction_of_keep_all=(
                float(r.reused_prior_branch_pops / kk.reused_prior_branch_pops)
                if float(kk.reused_prior_branch_pops) > 0 else np.nan
            ),
            avoided_branch_pops_vs_restart=float(rr.branch_pops_executed - r.branch_pops_executed),
            relative_best_improvement_vs_restart=float((rr.best_objective - r.best_objective) / denom),
            anytime_improvement_vs_restart=float(rr.mean_objective_ratio - r.mean_objective_ratio),
        )
        rows.append(x)
    return pd.DataFrame(rows)


def _case_level(ext_matched):
    deterministic = ext_matched[ext_matched.policy.isin(["fifo", "lru"])].copy()
    random_rows = ext_matched[ext_matched.policy == "random"].copy()
    numeric = [
        "reused_prior_branch_pops", "useful_resumes", "branch_pops_executed",
        "capacity_evictions", "invalidation_evictions", "peak_bytes", "byte_time",
        "selection_ms", "reuse_fraction_of_keep_all", "avoided_branch_pops_vs_restart",
        "relative_best_improvement_vs_restart", "anytime_improvement_vs_restart",
    ]
    rand_case = random_rows.groupby(
        ["domain", "instance_seed", "budget_fraction", "policy"], as_index=False
    )[numeric].mean()
    rand_case["random_repetitions"] = RANDOM_REPETITIONS
    deterministic["random_repetitions"] = 1
    keep_cols = ["domain", "instance_seed", "budget_fraction", "policy", "random_repetitions"] + numeric
    return pd.concat([deterministic[keep_cols], rand_case[keep_cols]], ignore_index=True).sort_values(
        ["budget_fraction", "policy", "domain", "instance_seed"]
    ).reset_index(drop=True)


def _aggregate(case_df):
    rows = []
    metrics = [
        "reuse_fraction_of_keep_all", "reused_prior_branch_pops", "useful_resumes",
        "avoided_branch_pops_vs_restart", "relative_best_improvement_vs_restart",
        "anytime_improvement_vs_restart",
    ]
    for (frac, policy), g in case_df.groupby(["budget_fraction", "policy"]):
        row = {"budget_fraction": float(frac), "policy": policy, "cases": int(len(g))}
        for j, metric in enumerate(metrics):
            mean, lo, hi = _bootstrap_mean_ci(
                g[metric].values,
                seed=88_000 + 100 * _BUDGET_CODE[float(frac)] + 10 * _POLICY_CODE[policy] + j,
            )
            row[f"mean_{metric}"] = mean
            row[f"bootstrap_95_low_{metric}"] = lo
            row[f"bootstrap_95_high_{metric}"] = hi
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["budget_fraction", "policy"]).reset_index(drop=True)


def _paired_learned_effects(case_df, authoritative_matched):
    learned = authoritative_matched[authoritative_matched.policy == "learned"].copy()
    rows = []
    for frac in BUDGETS:
        le = learned[learned.budget_fraction == frac].set_index(["domain", "instance_seed"]).sort_index()
        for policy in ("fifo", "lru", "random"):
            ex = case_df[(case_df.budget_fraction == frac) & (case_df.policy == policy)].set_index(
                ["domain", "instance_seed"]
            ).sort_index()
            if not le.index.equals(ex.index):
                raise AssertionError(f"case mismatch for {frac} {policy}")
            for metric in ("reuse_fraction_of_keep_all", "reused_prior_branch_pops", "useful_resumes"):
                delta = le[metric].astype(float) - ex[metric].astype(float)
                mean, lo, hi = _bootstrap_mean_ci(
                    delta.values,
                    seed=99_000 + 100 * _BUDGET_CODE[frac] + 10 * _POLICY_CODE[policy]
                    + {"reuse_fraction_of_keep_all": 1, "reused_prior_branch_pops": 2, "useful_resumes": 3}[metric],
                )
                rows.append(dict(
                    budget_fraction=float(frac), comparator=policy, metric=metric, cases=len(delta),
                    mean_learned_minus_comparator=mean, bootstrap_95_low=lo, bootstrap_95_high=hi,
                    positive_cases=int((delta > 1e-12).sum()), negative_cases=int((delta < -1e-12).sum()),
                    ties=int((np.abs(delta) <= 1e-12).sum()),
                ))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p7-dir", required=True, help="Authoritative P7 results directory")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()

    p7 = Path(a.p7_dir).resolve(); out = Path(a.out_dir).resolve(); out.mkdir(parents=True, exist_ok=True)
    budgets = pd.read_csv(p7 / "p7_confirmatory_budgets.csv")
    aruns = pd.read_csv(p7 / "p7_confirmatory_runs.csv")
    amatched = pd.read_csv(p7 / "p7_confirmatory_matched.csv")

    expected = {(d, s, float(b)) for d in DOMAINS for s in SEEDS for b in BUDGETS}
    observed = set(zip(budgets.domain, budgets.instance_seed.astype(int), budgets.budget_fraction.astype(float)))
    if observed != expected:
        raise ValueError("authoritative P7 budget table does not match frozen 45-case x 3-budget design")

    by_case = {}
    for (d, s), g in budgets.groupby(["domain", "instance_seed"]):
        by_case[(d, int(s))] = {float(r.budget_fraction): int(r.budget_bytes) for _, r in g.iterrows()}
    tasks = [(d, s, by_case[(d, s)]) for d in DOMAINS for s in SEEDS]

    rows = []
    with ProcessPoolExecutor(max_workers=int(a.workers)) as ex:
        fut = {ex.submit(_run_case, t): t for t in tasks}
        for i, f in enumerate(as_completed(fut), 1):
            t = fut[f]; rows.extend(f.result())
            print(f"[{i}/{len(tasks)}] {t[0]} {t[1]}", flush=True)

    raw = pd.DataFrame(rows).sort_values(
        ["budget_fraction", "policy", "domain", "instance_seed", "random_repetition"], na_position="first"
    ).reset_index(drop=True)
    raw.to_csv(out / "p7_external_comparator_runs.csv", index=False)

    matched = _with_matched_metrics(raw, aruns)
    matched.to_csv(out / "p7_external_comparator_matched_runs.csv", index=False)

    case_df = _case_level(matched)
    case_df.to_csv(out / "p7_external_comparator_case_level.csv", index=False)

    agg = _aggregate(case_df)
    agg.to_csv(out / "p7_external_comparator_aggregate.csv", index=False)

    paired = _paired_learned_effects(case_df, amatched)
    paired.to_csv(out / "p7_external_comparator_paired_learned.csv", index=False)

    summary = {
        "design": "RQ1_external_published_policy_extension",
        "domains": list(DOMAINS), "seeds": list(SEEDS), "independent_cases": 45,
        "iterations_per_case": ITERATIONS, "destroy_size": DESTROY_SIZE, "slice_branch_pops": SLICE_POPS,
        "budget_fractions": list(BUDGETS), "primary_budget_fraction": 0.25,
        "external_policies": ["fifo", "lru", "random"],
        "random_repetitions_per_case_budget": RANDOM_REPETITIONS,
        "random_seed_formula": "10,000,000*rep + 1,000,000*domain_code + 100*instance_seed + budget_code",
        "domain_code": _DOMAIN_CODE, "budget_code": {str(k): v for k, v in _BUDGET_CODE.items()},
        "inferential_unit": "base case; random repetitions averaged within case before cross-case bootstrap",
        "bootstrap_repetitions": BOOTSTRAP_REPS,
        "primary_external_outcome": "keep-all-normalized reusable work",
        "hypothesis_tests": "none added; paired case-bootstrap intervals are descriptive/estimation-focused",
        "aggregate": agg.to_dict(orient="records"),
        "paired_learned": paired.to_dict(orient="records"),
    }
    (out / "P7_EXTERNAL_COMPARATOR_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
