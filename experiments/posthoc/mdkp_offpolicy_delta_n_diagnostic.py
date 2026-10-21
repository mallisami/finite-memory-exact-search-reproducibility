#!/usr/bin/env python3
"""Post hoc, future-aware fixed-trace retention diagnostic for the MDKP backend.

Purpose (manuscript Section 4.2 / 6.2): separate marginal-work TARGET headroom
from PREDICTOR error, off policy. The deployed evaluation could not make this
distinction because positive savings are sparse and conditional-magnitude
prediction is weak.

Design. For each of the 25 development cases, the retained candidate stream
(marginal_work_training.csv: one row per decision-time checkpoint candidate,
with realized counterfactual saving_nodes labels from deterministic replay) is
replayed as a FIXED trace:
  - Candidates arrive in created_iteration order.
  - A byte-capacitated resident set (3,068 bytes, the deployed budget) is
    re-selected by exact 0/1 knapsack at each arrival; evicted candidates are
    gone permanently.
  - A candidate leaves the pool at created_iteration + recurrence_delay
    (event 'compatible_recurrence' or 'invalidated') or at created_iteration
    + 40 (event 'none', the prediction horizon H).
  - A 'compatible_recurrence' candidate still resident at its recurrence
    realizes its saving_nodes.
Retention rules compared on the SAME trace:
  oracle      value = realized saving_nodes (future-aware upper reference)
  deployed    value = q_hat * clip(expm1(ridge), 0, 384) from the frozen
              two-part model (marginal_work_model.joblib), as deployed
  empirical   value = p_rec * invested_nodes_norm (empirical-style analogue)
  invested    value = invested_nodes_norm
  random      value ~ U(0,1), 10 repetitions averaged (seed 20261017)

Outputs: fraction of total realizable saving captured by each rule, per case
and pooled, plus the deployed/oracle capture ratio. Because retention cannot
change the labels on a fixed trace (the true deployed system is closed-loop),
this is a DIAGNOSTIC of valuation quality under the deployed budget, not a
policy-level result and not a deployable upper bound.

Status: post hoc analysis, NOT part of the prespecified protocol. Generated
2026-10-17 in a Claude session from retained package data only; re-verify by
rerunning this script against 14_RQ3_MDKP_Work_to_Runtime_Campaign/
01_Development_Model/marginal_work_training.csv before citing.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BUDGET_BYTES = 3068
HORIZON = 40
RANDOM_REPS = 10
RANDOM_SEED = 20261017


def knapsack_select(pool, budget):
    """Exact 0/1 knapsack over a small pool: maximize value under byte budget.

    Pools are small (typically <= 4 live candidates at 3,068 bytes), so
    exhaustive enumeration is exact and fast.
    """
    n = len(pool)
    best_val, best_set = -1.0, ()
    for mask in range(1 << n):
        size = val = 0.0
        ok = True
        for j in range(n):
            if mask >> j & 1:
                size += pool[j]["size"]
                if size > budget:
                    ok = False
                    break
                val += pool[j]["value"]
        if ok and val > best_val:
            best_val, best_set = val, tuple(
                j for j in range(n) if mask >> j & 1
            )
    return set(best_set)


def simulate(case_rows, value_key):
    pool, captured = [], 0.0
    for row in case_rows:  # already sorted by created_iteration
        t = row["created_iteration"]
        for c in list(pool):
            if c["end"] <= t:
                if c["realizes"]:
                    captured += c["saving"]
                pool.remove(c)
        pool.append(row | {"value": row[value_key]})
        if sum(c["size"] for c in pool) > BUDGET_BYTES:
            keep = knapsack_select(pool, BUDGET_BYTES)
            pool = [c for j, c in enumerate(pool) if j in keep]
    for c in pool:
        if c["realizes"]:
            captured += c["saving"]
    return captured


def main(pkg_root):
    dev = Path(pkg_root) / "14_RQ3_MDKP_Work_to_Runtime_Campaign" / "01_Development_Model"
    df = pd.read_csv(dev / "marginal_work_training.csv")
    model = joblib.load(dev / "marginal_work_model.joblib")
    feats = model["features"]
    X = df[feats]
    q = model["classifier"].predict_proba(X)[:, 1]
    mu = np.clip(np.expm1(model["conditional_regressor"].predict(X)), 0, model["clip_max"])
    df = df.assign(
        u_deployed=np.clip(q * mu, 0, model["clip_max"]),
        u_empirical=df["p_rec"] * df["invested_nodes_norm"],
        u_invested=df["invested_nodes_norm"],
        u_oracle=df["saving_nodes"],
    )
    rng = np.random.default_rng(RANDOM_SEED)
    total_realizable = float(df.loc[df["event"] == "compatible_recurrence", "saving_nodes"].sum())
    rules = ["u_oracle", "u_deployed", "u_empirical", "u_invested"]
    captured = {r: 0.0 for r in rules}
    captured["u_random"] = 0.0
    per_case = []
    for seed, g in df.groupby("seed", sort=True):
        g = g.sort_values("created_iteration", kind="stable")
        rows = [
            {
                "created_iteration": int(r.created_iteration),
                "size": float(r.size_bytes),
                "saving": float(r.saving_nodes),
                "end": int(r.created_iteration)
                + (int(r.recurrence_delay) if r.event != "none" else HORIZON),
                "realizes": r.event == "compatible_recurrence" and r.saving_nodes > 0,
                **{k: float(getattr(r, k)) for k in rules},
            }
            for r in g.itertuples()
        ]
        case = {"seed": int(seed), "candidates": len(rows),
                "realizable": float(sum(r["saving"] for r in rows if r["realizes"]))}
        for rule in rules:
            got = simulate(rows, rule)
            captured[rule] += got
            case[rule] = got
        rnd = 0.0
        for _ in range(RANDOM_REPS):
            for r in rows:
                r["u_random"] = float(rng.random())
            rnd += simulate(rows, "u_random")
        captured["u_random"] += rnd / RANDOM_REPS
        case["u_random"] = rnd / RANDOM_REPS
        per_case.append(case)

    out = {
        "design": "fixed-trace, byte-capacitated (3068 B) retention replay over the retained "
                  "1,948 development candidates; post hoc diagnostic, not prespecified",
        "total_realizable_saving_nodes": total_realizable,
        "capture_fraction": {k: captured[k] / total_realizable for k in captured},
        "deployed_over_oracle_capture_ratio": captured["u_deployed"] / captured["u_oracle"],
        "oracle_capture_fraction_is_budget_headroom": captured["u_oracle"] / total_realizable,
        "random_reps": RANDOM_REPS,
        "random_seed": RANDOM_SEED,
        "per_case": per_case,
    }
    out_path = Path(__file__).with_name("MDKP_OFFPOLICY_DELTA_N_DIAGNOSTIC.json")
    out_path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "per_case"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
