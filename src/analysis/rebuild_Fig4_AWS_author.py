#!/usr/bin/env python3
"""Rebuild manuscript Fig. 4 from the authoritative corrected AWS P8 analysis CSVs.

Run from any working directory:
    python rebuild_Fig4_AWS.py

The script expects the researcher-facing five-folder release layout. It reads only the sealed
AWS P8 reanalysis outputs and writes Fig4.pdf beside this script.
"""
from pathlib import Path
import csv
import matplotlib.pyplot as plt
import numpy as np

SOURCE_DIR = Path(__file__).resolve().parents[2] / "results/reproduced/publication_figures"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = PACKAGE_ROOT / "figures/data"
FIGURE_DATA = ANALYSIS_DIR / "p8_aws_triplet_block_work_saving_20261107.csv"
HETEROGENEITY_DATA = ANALYSIS_DIR / "p8_aws_app_regime_heterogeneity_20261107.csv"
OUTPUT = SOURCE_DIR / "Fig4.pdf"

for required in (FIGURE_DATA, HETEROGENEITY_DATA):
    if not required.is_file():
        raise FileNotFoundError(f"Required authoritative P8 input not found: {required}")

SOURCE_DIR.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(FIGURE_DATA.open(newline="", encoding="utf-8")))
by_policy = {row["policy"]: row for row in rows}
heterogeneity = list(csv.DictReader(HETEROGENEITY_DATA.open(newline="", encoding="utf-8")))

required_policies = {"empirical_compatible", "learned", "keep_all", "learned_minus_empirical"}
if not required_policies.issubset(by_policy):
    raise ValueError(f"P8 Figure 4 data is missing policies: {required_policies - set(by_policy)}")
if len(heterogeneity) != 9:
    raise ValueError(f"Expected nine application-by-regime rows, found {len(heterogeneity)}")

plt.rcParams.update({"font.size": 8, "axes.labelsize": 9, "xtick.labelsize": 8,
                     "ytick.labelsize": 8, "legend.fontsize": 8})
fig = plt.figure(figsize=(10.4, 6.1))
ax1 = fig.add_axes([0.10, 0.60, 0.31, 0.30])
ax2 = fig.add_axes([0.10, 0.13, 0.31, 0.30])
ax3 = fig.add_axes([0.62, 0.13, 0.33, 0.77])

series = [("empirical_compatible", "Empirical-compatible", "o"),
          ("learned", "Learned", "s"), ("keep_all", "Keep-all", "^")]
for i, (key, label, marker) in enumerate(series):
    row = by_policy[key]
    mean = float(row["mean_saved_pops"])
    low = float(row["triplet_block_ci_lo"])
    high = float(row["triplet_block_ci_hi"])
    ax1.errorbar(mean, i, xerr=[[mean - low], [high - mean]], fmt=marker,
                 capsize=3, markersize=5, label=label)
ax1.set_yticks(range(3), [item[1] for item in series])
ax1.invert_yaxis()
ax1.set_xlabel("Mean avoided new branch pops vs restart")
ax1.set_title("(a)", loc="left", fontweight="bold")
ax1.grid(axis="x", alpha=0.35)

row = by_policy["learned_minus_empirical"]
mean = float(row["mean_saved_pops"])
low = float(row["triplet_block_ci_lo"])
high = float(row["triplet_block_ci_hi"])
ax2.errorbar(mean, 0, xerr=[[mean - low], [high - mean]], fmt="D", capsize=3, markersize=6)
ax2.axvline(0, linestyle=":", linewidth=1)
ax2.set_yticks([0], ["Learned - empirical"])
ax2.set_xlabel("Incremental avoided new branch pops")
ax2.set_title("(b)", loc="left", fontweight="bold")
ax2.grid(axis="x", alpha=0.35)

order = [("Hotel Reservation", "burst", "Hotel Reservation - burst"),
         ("Hotel Reservation", "step", "Hotel Reservation - step"),
         ("Hotel Reservation", "ramp", "Hotel Reservation - ramp"),
         ("Media Service", "burst", "Media Service - burst"),
         ("Media Service", "step", "Media Service - step"),
         ("Media Service", "ramp", "Media Service - ramp"),
         ("Social Network", "burst", "Social Network - burst"),
         ("Social Network", "step", "Social Network - step"),
         ("Social Network", "ramp", "Social Network - ramp")]
y_values = range(len(order))
for i, (app, regime, label) in enumerate(order):
    row = next(item for item in heterogeneity
               if item["application_label"] == app and item["regime"] == regime)
    empirical = float(row["empirical_mean_saved"])
    learned = float(row["learned_mean_saved"])
    ax3.plot([empirical, learned], [i, i], linewidth=1.0, alpha=0.65, color="0.55")
    ax3.plot(empirical, i, "o", color="#1f77b4",
             label="Empirical-compatible" if i == 0 else None)
    ax3.plot(learned, i, "s", color="#ff7f0e", label="Learned" if i == 0 else None)
ax3.set_yticks(list(y_values), [item[2] for item in order])
ax3.invert_yaxis()
ax3.set_xlabel("Mean new branch pops avoided vs restart")
ax3.set_title("(c)", loc="left", fontweight="bold")
ax3.grid(axis="x", alpha=0.35)
ax3.legend(loc="lower right", frameon=False)

fig.savefig(OUTPUT, bbox_inches="tight")
print(f"Wrote {OUTPUT}")
print(f"Inputs: {FIGURE_DATA.name}; {HETEROGENEITY_DATA.name}")
