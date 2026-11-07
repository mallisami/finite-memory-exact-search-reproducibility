#!/usr/bin/env python3
"""Rebuild retained-data summaries and canonical publication figures.

This is an analysis-only rebuild. It reads authoritative retained P6/P7/P8/P9
outputs and the nested RQ2 timing archive. It does not execute any experiment.
Publication PDFs are written to a separate ignored results/reproduced path. Raw
experimental CSVs are read in place and are never copied into figure_data/.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
from time import perf_counter
import zipfile

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/core"
DERIVED = ROOT / "results/reproduced"
FIGURE_DATA = DERIVED / "publication_data"
FIGURES = ROOT / "results/reproduced/publication_figures"
POSTHOC = ROOT / "results/posthoc"
P8_AWS = ROOT / "results/measured_replay/aws_20261107"
P8_REANALYSIS = P8_AWS / "P8_AWS_TRIPLET_BLOCK_REANALYSIS.json"

FIGURE_DATA.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)
stage_clock = perf_counter()
print("[1/7] rebuilding P6 summaries", flush=True)

# Do not delete, replace or reinterpret original experimental records.
# Derived publication tables are checked against retained current inputs.


def metrics(y, probability):
    p = np.clip(np.asarray(probability, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=int)
    return {
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
        "auroc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else np.nan,
        "auprc": float(average_precision_score(y, p)),
    }


def case_bootstrap_ci(df, ycol, pcol, casecol, *, reps=2000, seed=20261005):
    rng = np.random.default_rng(seed)
    cases = np.asarray(sorted(df[casecol].unique()))
    case_values = df[casecol].to_numpy()
    groups = [np.flatnonzero(case_values == case) for case in cases]
    y = df[ycol].to_numpy()
    p = df[pcol].to_numpy()
    draws = {k: [] for k in ("log_loss", "brier", "auroc", "auprc")}
    for _ in range(reps):
        indices = np.concatenate([groups[j] for j in rng.integers(0, len(cases), len(cases))])
        result = metrics(y[indices], p[indices])
        for key, value in result.items():
            if np.isfinite(value):
                draws[key].append(value)
    return {k: [float(np.quantile(v, .025)), float(np.quantile(v, .975))] for k, v in draws.items()}


def mean_case_bootstrap(values, *, reps=10000, seed=77025):
    x = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(reps, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, .025)), float(np.quantile(means, .975))


def set_publication_style():
    plt.rcParams.update({
        "font.family": "Liberation Sans",
        "font.size": 8.5,
        "axes.labelsize": 8.5,
        "xtick.labelsize": 7.7,
        "ytick.labelsize": 7.7,
        "legend.fontsize": 7.4,
        "axes.linewidth": .8,
        "lines.linewidth": 1.35,
        "lines.markersize": 5.0,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": .025,
    })


def tidy(ax, grid="x"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3, width=.7)
    if grid:
        ax.grid(axis=grid, color=".86", linewidth=.6)
    ax.set_axisbelow(True)


def panel(ax, label):
    ax.text(-.11, 1.04, label, transform=ax.transAxes, fontweight="bold", fontsize=9.5, va="bottom")


def save_pdf(fig, name):
    fig.savefig(FIGURES / name, format="pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# P6 development ablation and sealed holdout summaries
# ---------------------------------------------------------------------------
cv = pd.read_csv(ROOT / "data/core/predictor_development/p6_development_cv_metrics.csv")
ablation = pd.read_csv(ROOT / "data/core/predictor_development/p6_feature_ablation_best_configs.csv")
feature_rows = []
for family in ("H", "S", "D", "H+S", "H+D", "H+S+D"):
    selected_config = ablation[
        (ablation.model_family == "logistic") & (ablation.feature_family == family)
    ].iloc[0].config
    d = cv[
        (cv.model_family == "logistic")
        & (cv.feature_family == family)
        & (cv.config == selected_config)
        & cv["fold"].astype(str).isin(["0", "1", "2", "3", "4"])
    ]
    if d["fold"].nunique() != 5:
        raise ValueError(f"P6 ablation {family} does not contain all five grouped folds")
    feature_rows.append({
        "feature_family": family,
        "config": selected_config,
        "mean_log_loss": float(d.log_loss.mean()),
        "min_log_loss": float(d.log_loss.min()),
        "max_log_loss": float(d.log_loss.max()),
        "folds": int(d["fold"].nunique()),
    })
pd.DataFrame(feature_rows).to_csv(FIGURE_DATA / "p6_ablation_fold_ranges.csv", index=False)

p6 = pd.read_csv(ROOT / "data/core/predictor_holdout/p6_blind_predictions.csv")
# Case-bootstrap confidence bounds are preserved from the frozen independent
# P6 analysis. We independently recalculate each direct point estimate below
# before plotting, avoiding a costly duplicate bootstrap with no new samples.
p6_rows = pd.read_csv(ROOT / "figures/data/p6_blind_case_bootstrap_summary.csv").to_dict("records")
if len(p6) != 225 or p6.case_id.nunique() != 15 or len(p6_rows) != 3:
    raise ValueError("P6 blind prediction and retained bootstrap population mismatch")
for name, probability_col in (
    ("Prevalence", "constant_probability"),
    ("History frequency", "history_probability"),
    ("Calibrated logistic H+D", "final_probability"),
):
    actual = metrics(p6.future_compatible_recurrence, p6[probability_col])
    saved = next(row for row in p6_rows if row["predictor"] == name)
    for key in actual:
        if not np.isclose(actual[key], saved[key], rtol=0, atol=1e-12):
            raise ValueError(f"P6 {name} retained {key} differs from recalculated source")
reliability = pd.read_csv(ROOT / "data/core/predictor_holdout/p6_blind_reliability_bins.csv")
print(f"[2/7] P6 summaries complete in {perf_counter()-stage_clock:.1f}s; rebuilding P7 summaries", flush=True)
stage_clock = perf_counter()
if len(reliability) != 10 or reliability.n.sum() != len(p6):
    raise ValueError("P6 reliability bins must contain ten bins covering all held-out predictions")

# ---------------------------------------------------------------------------
# P7 confirmatory retention summaries and post-hoc comparators
# ---------------------------------------------------------------------------
structural = pd.read_csv(ROOT / "data/core/residence_screen/p7b_structural_aggregate.csv")
p7_matched = pd.read_csv(ROOT / "data/core/residence_primary/results/p7_confirmatory_matched.csv")
p7_primary = pd.read_csv(ROOT / "data/core/residence_primary/results/p7_confirmatory_primary_inference.csv")
posthoc_summary = pd.read_csv(POSTHOC / "p7_posthoc_baseline_summary.csv")
retention_rows = []
for budget in (.25, .50, .75):
    d = p7_matched[p7_matched.budget_fraction == budget]
    learned = d[d.policy == "learned"].set_index(["domain", "instance_seed"]).sort_index()
    empirical = d[d.policy == "empirical_compatible"].set_index(["domain", "instance_seed"]).sort_index()
    if len(learned) != 45 or not learned.index.equals(empirical.index):
        raise ValueError(f"P7 matched policy rows incomplete at budget {budget}")
    difference = learned.reuse_fraction_of_keep_all.to_numpy() - empirical.reuse_fraction_of_keep_all.to_numpy()
    if budget == .25:
        row = p7_primary[p7_primary.comparison == "learned_minus_empirical_reuse"].iloc[0]
        mean = float(row.mean_paired_effect)
        lo = float(row.bootstrap_95_low)
        hi = float(row.bootstrap_95_high)
    else:
        mean, lo, hi = mean_case_bootstrap(difference, seed=77000 + int(budget * 100))
    retention_rows.append({
        "budget_fraction": budget,
        "n_cases": len(difference),
        "empirical_mean_capture": float(empirical.reuse_fraction_of_keep_all.mean()),
        "learned_mean_capture": float(learned.reuse_fraction_of_keep_all.mean()),
        "mean_paired_effect": mean,
        "ci_lo": lo,
        "ci_hi": hi,
    })
retention_summary = pd.DataFrame(retention_rows)
retention_summary.to_csv(FIGURE_DATA / "p7_retention_summary.csv", index=False)
retention_summary[retention_summary.budget_fraction > .25][
    ["budget_fraction", "n_cases", "mean_paired_effect", "ci_lo", "ci_hi"]
].to_csv(FIGURE_DATA / "p7_budget_sensitivity_bootstrap.csv", index=False)
print(f"[3/7] P7 summaries complete in {perf_counter()-stage_clock:.1f}s; rebuilding P8 reanalysis", flush=True)
stage_clock = perf_counter()

# ---------------------------------------------------------------------------
# Corrected AWS P8 source: NEVER re-run pre-AWS P8 reanalysis in the current release.
# Figure 4's dedicated generator reads frozen corrected AWS publication tables.
# Validate the current publication copies before using their summary values.
# ---------------------------------------------------------------------------

source_p8 = ROOT / "figures/data/p8_aws_triplet_block_work_saving_20261107.csv"
source_hetero = ROOT / "figures/data/p8_aws_app_regime_heterogeneity_20261107.csv"
pub_p8 = ROOT / "figures/data/p8_aws_triplet_block_work_saving_20261107.csv"
pub_hetero = ROOT / "figures/data/p8_aws_app_regime_heterogeneity_20261107.csv"
if source_p8.read_bytes() != pub_p8.read_bytes() or source_hetero.read_bytes() != pub_hetero.read_bytes():
    raise ValueError("Corrected P8 publication data diverge from frozen AWS sources")
work_rows = pd.read_csv(source_p8)
heterogeneity = pd.read_csv(source_hetero)
p8_reanalysis = json.loads(P8_REANALYSIS.read_text(encoding="utf-8"))
endpoint_map = p8_reanalysis["endpoints"]
if len(heterogeneity) != 9 or len(work_rows) != 4:
    raise ValueError("Corrected AWS P8 table has unexpected policy/cell count")
if not np.isclose(work_rows.set_index("policy").loc["learned", "mean_saved_pops"],
                  endpoint_map["learned_saved_vs_restart"]["mean"]):
    raise ValueError("Corrected P8 learned work-saving estimate mismatch")
subprocess.run([sys.executable, str(ROOT / "src/analysis/rebuild_Fig4_AWS_author.py")], check=True)
print(f"[4/7] corrected AWS P8 Fig4 generated in {perf_counter()-stage_clock:.1f}s; checking nested P9", flush=True)
stage_clock = perf_counter()

# ---------------------------------------------------------------------------
# Current P9 is NESTED family held-out; the original fixed-specification P9
# source is retained separately in 04_Results/Historical/.
# ---------------------------------------------------------------------------
p9_nested = ROOT / "results/transfer/nested_20261107/nested_p9_domain_metrics.csv"
p9 = pd.read_csv(p9_nested)
p9_current = p9[p9["model"] == "nested_selected"].sort_values("held_out_domain")
if len(p9_current) != 3 or set(p9_current.held_out_domain) != {"generic", "workflow", "microservice"}:
    raise ValueError("Current nested P9 source must contain exactly three held-out families")
if not p9_current.n_cases.eq(15).all() or not p9_current.n_rows.eq(225).all():
    raise ValueError("Nested P9 source case and event counts are inconsistent")
p9_current.to_csv(FIGURE_DATA / "p9_nested_family_heldout_metrics.csv", index=False)
print(f"[5/7] nested P9 checked in {perf_counter()-stage_clock:.1f}s; rebuilding measurement summaries", flush=True)
stage_clock = perf_counter()

# ---------------------------------------------------------------------------
# Measurement-independence audit (derived count summary only)
# ---------------------------------------------------------------------------
dsb = ROOT / "data/deathstarbench"
measurement_index = pd.read_csv(dsb / "measurement/MEASUREMENT_INDEX.csv")
sequence_manifest = pd.read_csv(dsb / "prepared/sequence_manifest.csv")
measurement_audit = {
    "measurement_rows": int(len(measurement_index)),
    "unique_sequences": int(measurement_index.sequence.nunique()),
    "unique_measurement_seeds": int(measurement_index.seed.nunique()),
    "unique_pcap_sha256": int(measurement_index.pcap_sha256.nunique()),
    "prepared_sequences": int(sequence_manifest.sequence.nunique()),
}
(FIGURE_DATA / "dsb_measurement_independence_audit.json").write_text(
    json.dumps(measurement_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)

# ---------------------------------------------------------------------------
# Figure 5 uses the archived verified eight-row graph runtime summary.
# This is an analysis/plot rebuild from retained results, not a new VM run.
# ---------------------------------------------------------------------------
runtime_source = ROOT / "figures/data/rq2_graph_runtime_figure_summary_20261107.csv"
runtime_summary = pd.read_csv(runtime_source)
if len(runtime_summary) != 8 or not runtime_summary.n_cases.eq(60).all():
    raise ValueError("RQ2 graph-runtime summary must contain 8 policy/level rows with 60 cases each")
if set(runtime_summary.policy) != {"empirical_pW", "learned_pW"} or set(runtime_summary.level) != {"L1", "L2", "L3", "L4"}:
    raise ValueError("RQ2 graph-runtime source levels/policies inconsistent")
print(f"[6/7] retained runtime summary checked in {perf_counter()-stage_clock:.1f}s; generating figures", flush=True)
stage_clock = perf_counter()

# ---------------------------------------------------------------------------
# Machine-readable headline summary
# ---------------------------------------------------------------------------
p6_selected = pd.DataFrame(p6_rows).set_index("predictor").loc["Calibrated logistic H+D"]
r25 = retention_summary.set_index("budget_fraction").loc[.25]
p7_runs = pd.read_csv(ROOT / "data/core/residence_primary/results/p7_confirmatory_runs.csv")
p7_work = p7_runs.pivot_table(index=["domain", "instance_seed"], columns="policy", values="branch_pops_executed")
confirmatory_saved = float((p7_work.restart - p7_work.learned).mean())
p8_learned_saved = float(endpoint_map["learned_saved_vs_restart"]["mean"])
objective_endpoint = endpoint_map["learned_objective_improvement_vs_restart"]
headline = json.loads((ROOT / "figures/data/paper_headline_summary.json").read_text(encoding="utf-8"))
if not np.isclose(headline["prediction"]["heldout_auroc"], p6_selected.auroc, atol=1e-10):
    raise ValueError("P6 publication headline does not match source")
if not np.isclose(headline["retention"]["budget_25_effect"], r25.mean_paired_effect, atol=1e-10):
    raise ValueError("P7 publication headline does not match source")
if not np.isclose(headline["work_saving"]["external_pops_per_sequence"], p8_learned_saved, atol=1e-10):
    raise ValueError("AWS P8 publication headline does not match source")
if not np.isclose(headline["objective"]["external_mean_effect"], objective_endpoint["mean"], atol=1e-10):
    raise ValueError("AWS P8 objective headline does not match source")

# ---------------------------------------------------------------------------
# Publication figures: all PDFs are written to the LaTeX source directory.
# ---------------------------------------------------------------------------
set_publication_style()
cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
EMP, LEARN, KEEP, CONTRAST = cycle[0], cycle[1], cycle[2], cycle[3]

# Figure 2: feature-family ablation and sealed holdout calibration.
ab2 = pd.DataFrame(feature_rows)
fig, axes = plt.subplots(1, 2, figsize=(7.15, 3.05), gridspec_kw={"width_ratios": [1.05, .95]})
ax = axes[0]
order = ["H", "S", "D", "H+S", "H+D", "H+S+D"]
d = ab2.set_index("feature_family").loc[order].reset_index()
y = np.arange(len(d))[::-1]
mean = d.mean_log_loss.to_numpy()
ax.errorbar(
    mean, y,
    xerr=np.vstack([mean - d.min_log_loss.to_numpy(), d.max_log_loss.to_numpy() - mean]),
    fmt="o", capsize=2.2, color=EMP, ecolor=EMP,
)
selected = d.feature_family.eq("H+D").to_numpy()
ax.plot(mean[selected], y[selected], marker="s", linestyle="None", markersize=6.2, color=LEARN)
ax.set_yticks(y, d.feature_family)
ax.set_xlabel("Grouped-CV log loss (lower is better)")
ax.set_xlim(.32, .64)
ax.xaxis.set_major_locator(MultipleLocator(.05))
tidy(ax)
panel(ax, "(a)")

ax = axes[1]
x = reliability.mean_predicted_probability.to_numpy()
yy = reliability.observed_frequency.to_numpy()
counts = reliability.n.to_numpy(dtype=int)
ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1, color=".55")
ax.scatter(x, yy, s=18 + .72 * counts, marker="o", color=EMP, edgecolor="white", linewidth=.55, zorder=3)
label_offsets = [(7, 8), (7, -12), (7, 8), (7, 9), (7, 8), (7, -11), (7, 8), (7, 8), (7, 8), (-18, 8)]
for xi, yi, n, (dx, dy) in zip(x, yy, counts, label_offsets):
    ax.annotate(
        f"n={n}", (xi, yi), xytext=(dx, dy), textcoords="offset points",
        ha="right" if dx < 0 else "left", va="center", fontsize=7.0, color=".25",
        annotation_clip=True,
    )
ax.set_xlabel("Mean predicted probability")
ax.set_ylabel("Observed frequency")
ax.set_xlim(-.02, 1.04)
ax.set_ylim(-.02, 1.02)
ax.xaxis.set_major_locator(MultipleLocator(.2))
ax.yaxis.set_major_locator(MultipleLocator(.2))
tidy(ax, "both")
panel(ax, "(b)")
fig.subplots_adjust(wspace=.34, left=.10, right=.99, bottom=.18, top=.94)
save_pdf(fig, "Fig2.pdf")

# Figure 3: three persistence budgets and 25%-budget comparator effects.
rs = retention_summary.set_index("budget_fraction")
budgets = np.array([25, 50, 75])
empirical = np.array([rs.loc[b / 100, "empirical_mean_capture"] for b in budgets])
learned = np.array([rs.loc[b / 100, "learned_mean_capture"] for b in budgets])
post = posthoc_summary.set_index("policy")
contrasts = pd.DataFrame({
    "Comparator": ["Empirical-compatible", "History only", "Invested-work only"],
    "mean": [
        rs.loc[.25, "mean_paired_effect"],
        post.loc["history_only", "learned_minus_policy_mean"],
        post.loc["work_only", "learned_minus_policy_mean"],
    ],
    "lo": [rs.loc[.25, "ci_lo"], post.loc["history_only", "ci_lo"], post.loc["work_only", "ci_lo"]],
    "hi": [rs.loc[.25, "ci_hi"], post.loc["history_only", "ci_hi"], post.loc["work_only", "ci_hi"]],
})
fig, axes = plt.subplots(1, 2, figsize=(7.15, 3.0), gridspec_kw={"width_ratios": [1.05, .95]})
ax = axes[0]
ax.plot(budgets, empirical, marker="o", linestyle="--", label="Empirical-compatible", color=EMP)
ax.plot(budgets, learned, marker="s", label="Learned", color=LEARN)
ax.axhline(1, linestyle=":", linewidth=1.1, label="Keep-all reference", color=KEEP)
ax.set_xlabel("Persistence budget (% of keep-all peak bytes)")
ax.set_ylabel("Keep-all-normalized reusable work")
ax.set_xticks(budgets)
ax.set_ylim(.78, 1.015)
ax.yaxis.set_major_locator(MultipleLocator(.05))
ax.legend(frameon=False, loc="lower right")
tidy(ax, "y")
ax.grid(axis="x", color=".86", linewidth=.6)
panel(ax, "(a)")
ax = axes[1]
y = np.arange(len(contrasts))[::-1]
means = contrasts["mean"].to_numpy()
ax.errorbar(
    means, y,
    xerr=np.vstack([means - contrasts.lo.to_numpy(), contrasts.hi.to_numpy() - means]),
    fmt="o", capsize=2.4, color=LEARN, ecolor=LEARN,
)
ax.plot(means[0], y[0], marker="s", linestyle="None", markersize=6.3, color=LEARN)
ax.axvline(0, linestyle=":", linewidth=1, color=".55")
ax.set_yticks(y, contrasts.Comparator)
ax.set_xlabel("Learned - comparator at 25% budget\n(reusable-work capture)")
ax.set_xlim(-.015, .39)
ax.xaxis.set_major_locator(MultipleLocator(.05))
tidy(ax)
panel(ax, "(b)")
fig.subplots_adjust(wspace=.47, left=.10, right=.99, bottom=.22, top=.94)
save_pdf(fig, "Fig3.pdf")

# Figure 4 was rebuilt above by the corrected AWS generator, not the historical
# pre-AWS general plotting code. Its numeric source remains immutable.

# Figure 5: restart-relative empirical-pW and learned-pW runtime from the nested RQ2 archive.
fig, ax = plt.subplots(figsize=(7.15, 2.05))
for policy, label, marker, color in (
    ("empirical_pW", "Empirical-pW", "o", EMP),
    ("learned_pW", "Learned-pW", "s", LEARN),
):
    d = runtime_summary[runtime_summary.policy == policy].sort_values("repair_cap")
    ax.plot(
        d.repair_cap, d.geometric_restart_to_policy_runtime_ratio,
        marker=marker, label=label, color=color,
    )
ax.axhline(1, linestyle=":", linewidth=1.1, label="Restart parity", color=KEEP)
ax.set_xlabel("Repair cap (branch pops per repair)")
ax.set_ylabel("Geometric runtime ratio: restart / policy")
ax.set_xticks([8, 16, 32, 64])
ax.set_xlim(6, 66)
ax.set_ylim(.88, 1.09)
ax.yaxis.set_major_locator(MultipleLocator(.025))
ax.legend(frameon=False, loc="lower right", ncol=3)
tidy(ax, "y")
fig.subplots_adjust(left=.11, right=.99, bottom=.23, top=.97)
save_pdf(fig, "Fig5.pdf")

# Supplementary Figure S1: outcome-blind structural memory screen.
scales = [(24, 6), (32, 8), (40, 10)]
destroys = [5, 8, 12]
peak = np.full((3, 3), np.nan)
fraction = np.full((3, 3), np.nan)
for i, (nodes, hosts) in enumerate(scales):
    for j, destroy in enumerate(destroys):
        row = structural[(structural.n_nodes == nodes) & (structural.n_hosts == hosts) & (structural.destroy_size == destroy)]
        if len(row) != 1:
            raise ValueError(f"missing/duplicate P7B structural cell {(nodes, hosts, destroy)}")
        peak[i, j] = row.iloc[0].median_peak_active_checkpoints
        fraction[i, j] = 100 * row.iloc[0].median_fraction_iterations_k_ge_4
fig, axes = plt.subplots(1, 2, figsize=(7.15, 2.65), sharey=True)
for ax, matrix, title, colorbar_label in (
    (axes[0], peak, "Median peak live checkpoints", "checkpoints"),
    (axes[1], fraction, "Iterations with at least four live checkpoints", "% of iterations"),
):
    image = ax.imshow(matrix, aspect="auto", origin="upper")
    ax.set_xticks(range(3), destroys)
    ax.set_yticks(range(3), [f"{n} nodes / {h} hosts" for n, h in scales])
    ax.set_xlabel("Destroy size")
    for i in range(3):
        for j in range(3):
            label = f"{matrix[i, j]:.0f}" if colorbar_label == "checkpoints" else f"{matrix[i, j]:.0f}%"
            color = "white" if matrix[i, j] > np.nanmedian(matrix) else "black"
            ax.text(j, i, label, ha="center", va="center", fontsize=8, fontweight="bold", color=color)
    ax.add_patch(Rectangle((1.5, -.5), 1, 1, fill=False, linewidth=2, edgecolor="black"))
    ax.set_title(title, fontsize=8.6, pad=6)
    colorbar = fig.colorbar(image, ax=ax, fraction=.045, pad=.035)
    colorbar.ax.tick_params(labelsize=7)
    colorbar.set_label(colorbar_label, fontsize=7.5)
    ax.tick_params(length=0)
axes[1].tick_params(labelleft=False)
panel(axes[0], "(a)")
panel(axes[1], "(b)")
fig.subplots_adjust(wspace=.20, left=.14, right=.97, bottom=.20, top=.86)
save_pdf(fig, "FigS1.pdf")
print(f"[7/7] all publication PDFs generated in {perf_counter()-stage_clock:.1f}s", flush=True)

# Fail if this script accidentally recreated a second publication-figure directory.
if (DERIVED / "alternate_figures").exists():
    raise RuntimeError("non-canonical alternate figure directory exists")

print(json.dumps(headline, indent=2, sort_keys=True))
print("Publication PDFs rebuilt in", FIGURES)
print("Derived summaries rebuilt in", FIGURE_DATA)
print("No experiment campaign was executed.")
