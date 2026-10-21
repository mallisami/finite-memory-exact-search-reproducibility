"""Locked Statistical Analysis Script for PCR Transactions One-Shot Campaign.

Implements the locked statistical analysis plan (Protocol V4 Section 20):
- Independent experimental unit: Case.
- Within-case median over 5 counterbalanced timing repeats.
- Estimands:
  * RQ2-A: Opportunity Conversion (Learned-pW at L4 vs L1)
  * RQ2-B: Compute-Aware Refinement (Learned-pW vs Learned-pC at L4)
  * RQ2-C: Net Acceleration (Restart vs Learned-pC at L4)
  * RQ3-A: MDKP Value Conversion (Learned-pW vs Learned-pC)
  * RQ3-B: MDKP Net Acceleration (Restart vs Learned-pC)
  * RQ3-C: MDKP Predictive Mechanism (Empirical-pC vs Learned-pC)
- 10,000 stratified case-bootstrap resamples:
  * Graph: Stratified by machine x family (6 strata)
  * MDKP: Stratified by machine (2 strata)
- Metrics:
  * Mean log effect
  * Geometric mean runtime ratio (exp(mean log))
  * Percent runtime effect
  * Mean paired ms difference
  * Median paired ms difference
  * 95% BCa / Percentile Bootstrap CI
  * Two-sided paired Wilcoxon test
  * Holm-Bonferroni step-down multiplicity correction across primary contrasts per family
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Calculate step-down Holm-Bonferroni adjusted p-values."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    adj = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        val = min(1.0, (m - rank) * p)
        running_max = max(running_max, val)
        adj[orig_idx] = running_max
    return adj


def compute_contrast_stats(
    case_df: pd.DataFrame,
    num_col: str,
    denom_col: str,
    strata_col: str,
    n_bootstraps: int = 10000,
    seed: int = 42,
) -> dict[str, object]:
    """Compute mean log effect, geometric ratio, paired differences, bootstrap CI, and Wilcoxon."""
    t_num = case_df[num_col].values.astype(float)
    t_denom = case_df[denom_col].values.astype(float)
    
    # Avoid zero/negative timings
    eps = 1e-6
    t_num = np.maximum(t_num, eps)
    t_denom = np.maximum(t_denom, eps)
    
    log_effects = np.log(t_num / t_denom)
    diff_ms = t_num - t_denom
    
    mean_log = float(np.mean(log_effects))
    geom_ratio = float(np.exp(mean_log))
    pct_effect = float((geom_ratio - 1.0) * 100.0)
    mean_diff_ms = float(np.mean(diff_ms))
    median_diff_ms = float(np.median(diff_ms))
    
    # Two-sided Wilcoxon signed-rank test
    try:
        w_stat, w_pval = wilcoxon(t_num, t_denom, alternative="two-sided")
        w_stat = float(w_stat)
        w_pval = float(w_pval)
    except Exception:
        w_stat = 0.0
        w_pval = 1.0

    # Stratified Bootstrap
    rng = np.random.default_rng(seed)
    strata_keys = case_df[strata_col].unique()
    strata_indices = {s: np.where(case_df[strata_col] == s)[0] for s in strata_keys}
    
    boot_means = []
    boot_diffs = []
    
    for _ in range(n_bootstraps):
        sampled_indices = []
        for s, idxs in strata_indices.items():
            sampled = rng.choice(idxs, size=len(idxs), replace=True)
            sampled_indices.extend(sampled)
        sampled_indices = np.array(sampled_indices)
        
        boot_means.append(np.mean(log_effects[sampled_indices]))
        boot_diffs.append(np.median(diff_ms[sampled_indices]))
        
    ci_log_low, ci_log_high = np.percentile(boot_means, [2.5, 97.5])
    ci_ratio_low, ci_ratio_high = float(np.exp(ci_log_low)), float(np.exp(ci_log_high))
    ci_diff_low, ci_diff_high = np.percentile(boot_diffs, [2.5, 97.5])
    
    return {
        "mean_log_effect": mean_log,
        "ci_95_log": [float(ci_log_low), float(ci_log_high)],
        "geometric_mean_ratio": geom_ratio,
        "ci_95_ratio": [ci_ratio_low, ci_ratio_high],
        "percent_effect": pct_effect,
        "mean_paired_diff_ms": mean_diff_ms,
        "median_paired_diff_ms": median_diff_ms,
        "ci_95_median_diff_ms": [float(ci_diff_low), float(ci_diff_high)],
        "wilcoxon_stat": w_stat,
        "wilcoxon_p_value": w_pval,
        "n_cases": len(case_df),
    }


def analyze_campaign_results(
    graph_results_df: pd.DataFrame,
    mdkp_results_df: pd.DataFrame,
    n_bootstraps: int = 10000,
    seed: int = 20261009,
) -> dict[str, object]:
    """Run full locked analysis on primary Graph and MDKP results."""
    # 1. Aggregate repeats to case-level medians
    # Graph aggregation: group by case_id, primary_machine, domain, family, level, policy
    g_agg = (
        graph_results_df.groupby(["case_id", "primary_machine", "domain", "family", "level", "policy"])[
            "end_to_end_wall_ms"
        ]
        .median()
        .reset_index()
    )
    g_pivot = g_agg.pivot(
        index=["case_id", "primary_machine", "domain", "family", "level"],
        columns="policy",
        values="end_to_end_wall_ms",
    ).reset_index()
    g_pivot["strata"] = g_pivot["primary_machine"].astype(str) + "_" + g_pivot["family"].astype(str)

    # RQ2 level slices
    g_l4 = g_pivot[g_pivot["level"] == "L4"].copy()
    g_l1 = g_pivot[g_pivot["level"] == "L1"].copy()

    # Opportunity conversion: S^{learned-pW}_{c, L4} - S^{learned-pW}_{c, L1}
    # S = log(T_restart / T_pW)
    g_merge = pd.merge(
        g_l4[["case_id", "strata", "restart", "learned_pW"]],
        g_l1[["case_id", "restart", "learned_pW"]],
        on="case_id",
        suffixes=("_L4", "_L1"),
    )
    g_merge["s_l4"] = np.log(g_merge["restart_L4"] / g_merge["learned_pW_L4"])
    g_merge["s_l1"] = np.log(g_merge["restart_L1"] / g_merge["learned_pW_L1"])
    g_merge["d_opp"] = g_merge["s_l4"] - g_merge["s_l1"]
    
    # Estimate RQ2 contrasts
    # RQ2-A: Opportunity Conversion
    rq2_a_mean = float(np.mean(g_merge["d_opp"]))
    # Bootstrap for RQ2-A
    rng = np.random.default_rng(seed)
    strata_keys = g_merge["strata"].unique()
    strata_indices = {s: np.where(g_merge["strata"] == s)[0] for s in strata_keys}
    boot_a = []
    for _ in range(n_bootstraps):
        s_idx = []
        for s, idxs in strata_indices.items():
            s_idx.extend(rng.choice(idxs, size=len(idxs), replace=True))
        boot_a.append(np.mean(g_merge["d_opp"].values[s_idx]))
    ci_a_low, ci_a_high = np.percentile(boot_a, [2.5, 97.5])
    try:
        w_stat_a, w_pval_a = wilcoxon(g_merge["s_l4"], g_merge["s_l1"], alternative="two-sided")
    except Exception:
        w_stat_a, w_pval_a = 0.0, 1.0

    res_rq2_a = {
        "mean_diff_log_score": rq2_a_mean,
        "ci_95_log": [float(ci_a_low), float(ci_a_high)],
        "wilcoxon_p_value": float(w_pval_a),
        "n_cases": len(g_merge),
    }

    # RQ2-B: Compute-Aware Refinement (Learned-pW vs Learned-pC at L4)
    res_rq2_b = compute_contrast_stats(
        g_l4, "learned_pW", "learned_pC", strata_col="strata", n_bootstraps=n_bootstraps, seed=seed + 1
    )

    # RQ2-C: Net Acceleration (Restart vs Learned-pC at L4)
    res_rq2_c = compute_contrast_stats(
        g_l4, "restart", "learned_pC", strata_col="strata", n_bootstraps=n_bootstraps, seed=seed + 2
    )

    # Holm-Bonferroni correction across RQ2-A/B/C
    rq2_raw_p = [res_rq2_a["wilcoxon_p_value"], res_rq2_b["wilcoxon_p_value"], res_rq2_c["wilcoxon_p_value"]]
    rq2_adj_p = holm_bonferroni(rq2_raw_p)
    res_rq2_a["holm_adjusted_p"] = rq2_adj_p[0]
    res_rq2_b["holm_adjusted_p"] = rq2_adj_p[1]
    res_rq2_c["holm_adjusted_p"] = rq2_adj_p[2]

    # 2. MDKP Aggregation and Contrasts
    m_agg = (
        mdkp_results_df.groupby(["case_id", "primary_machine", "domain", "policy"])["end_to_end_wall_ms"]
        .median()
        .reset_index()
    )
    m_pivot = m_agg.pivot(
        index=["case_id", "primary_machine", "domain"],
        columns="policy",
        values="end_to_end_wall_ms",
    ).reset_index()
    m_pivot["strata"] = m_pivot["primary_machine"].astype(str)

    # RQ3-A: Learned-pW vs Learned-pC
    res_rq3_a = compute_contrast_stats(
        m_pivot, "learned_pW", "learned_pC", strata_col="strata", n_bootstraps=n_bootstraps, seed=seed + 10
    )

    # RQ3-B: Restart vs Learned-pC
    res_rq3_b = compute_contrast_stats(
        m_pivot, "restart", "learned_pC", strata_col="strata", n_bootstraps=n_bootstraps, seed=seed + 11
    )

    # RQ3-C: Empirical-pC vs Learned-pC
    res_rq3_c = compute_contrast_stats(
        m_pivot, "empirical_pC", "learned_pC", strata_col="strata", n_bootstraps=n_bootstraps, seed=seed + 12
    )

    # Holm-Bonferroni correction across RQ3-A/B/C
    rq3_raw_p = [res_rq3_a["wilcoxon_p_value"], res_rq3_b["wilcoxon_p_value"], res_rq3_c["wilcoxon_p_value"]]
    rq3_adj_p = holm_bonferroni(rq3_raw_p)
    res_rq3_a["holm_adjusted_p"] = rq3_adj_p[0]
    res_rq3_b["holm_adjusted_p"] = rq3_adj_p[1]
    res_rq3_c["holm_adjusted_p"] = rq3_adj_p[2]

    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rq2_graph": {
            "RQ2_A_opportunity_conversion": res_rq2_a,
            "RQ2_B_compute_refinement": res_rq2_b,
            "RQ2_C_net_acceleration": res_rq2_c,
        },
        "rq3_mdkp": {
            "RQ3_A_compute_refinement": res_rq3_a,
            "RQ3_B_net_acceleration": res_rq3_b,
            "RQ3_C_predictive_mechanism": res_rq3_c,
        },
    }


def generate_synthetic_dry_run_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic dummy data matching exact schema to validate locked analysis pipeline."""
    rng = np.random.default_rng(12345)
    
    # Synthetic Graph
    g_rows = []
    cases = [f"graph_{i:03d}" for i in range(60)]
    fams = ["Generic"] * 20 + ["Workflow"] * 20 + ["Microservice"] * 20
    hosts = ["rack-a", "rack-b"] * 30
    
    for c, fam, host in zip(cases, fams, hosts):
        for lvl in ["L1", "L2", "L3", "L4"]:
            for rep in range(5):
                for pol in ["restart", "empirical_pW", "learned_pW", "empirical_pC", "learned_pC"]:
                    base = 100.0 if lvl == "L1" else 300.0
                    mult = 1.0 if pol == "restart" else (0.85 if "pC" in pol else 0.90)
                    t_ms = base * mult + rng.normal(0, 5.0)
                    g_rows.append({
                        "case_id": c,
                        "primary_machine": host,
                        "domain": "graph",
                        "family": fam,
                        "level": lvl,
                        "repeat": rep,
                        "policy": pol,
                        "end_to_end_wall_ms": max(1.0, t_ms),
                    })
    g_df = pd.DataFrame(g_rows)
    
    # Synthetic MDKP
    m_rows = []
    m_cases = [f"mdkp_{i:03d}" for i in range(80)]
    m_hosts = ["rack-a", "rack-b"] * 40
    
    for c, host in zip(m_cases, m_hosts):
        for rep in range(5):
            for pol in ["restart", "empirical_pW", "learned_pW", "empirical_pC", "learned_pC"]:
                base = 250.0
                mult = 1.0 if pol == "restart" else (0.80 if "pC" in pol else 0.88)
                t_ms = base * mult + rng.normal(0, 8.0)
                m_rows.append({
                    "case_id": c,
                    "primary_machine": host,
                    "domain": "mdkp",
                    "level": "MDKP",
                    "repeat": rep,
                    "policy": pol,
                    "end_to_end_wall_ms": max(1.0, t_ms),
                })
    m_df = pd.DataFrame(m_rows)
    
    return g_df, m_df


def main():
    parser = argparse.ArgumentParser(description="Locked Statistical Analysis")
    parser.add_argument("--graph-results", default=None)
    parser.add_argument("--mdkp-results", default=None)
    parser.add_argument("--out-dir", default="16_locked_analysis")
    parser.add_argument("--dry-run-synthetic", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run_synthetic:
        print("[ANALYSIS DRY RUN] Generating synthetic dummy data...")
        g_df, m_df = generate_synthetic_dry_run_data()
    else:
        if not args.graph_results or not args.mdkp_results:
            raise ValueError("Must provide --graph-results and --mdkp-results or specify --dry-run-synthetic")
        g_df = pd.read_csv(args.graph_results)
        m_df = pd.read_csv(args.mdkp_results)

    print(f"[ANALYSIS] Running locked statistical analysis over {len(g_df)} graph runs and {len(m_df)} MDKP runs...")
    analysis = analyze_campaign_results(g_df, m_df, n_bootstraps=10000)

    out_json = out_dir / ("SYNTHETIC_ANALYSIS_DRY_RUN.json" if args.dry_run_synthetic else "LOCKED_STATISTICAL_ANALYSIS.json")
    with open(out_json, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"[ANALYSIS] Saved statistical analysis results to {out_json}")


if __name__ == "__main__":
    main()
