#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import math
import sys

import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parent
FAIL: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("PASS" if cond else "FAIL"), msg)
    if not cond:
        FAIL.append(msg)


def close(x: float, y: float, tol: float = 5e-4) -> bool:
    return math.isfinite(float(x)) and abs(float(x) - float(y)) <= tol


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# Repository contract
required = [
    "README.md",
    "requirements.txt",
    "src/run_experiments.py",
    "src/analysis/rebuild_derived_diagnostics.py",
    "data/core/predictor_holdout/p6_blind_predictions.csv",
    "data/core/residence_primary/results/p7_confirmatory_matched.csv",
    "data/core/measured_replay/p8_external_runs.csv",
    "data/deathstarbench/prepared/sequence_manifest.csv",
    "results/graph_runtime/primary/raw/combined_graph_results.csv",
    "results/graph_runtime/coefficient/analysis/P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.json",
    "results/mdkp/timing/MERGED_RAW.csv",
    "results/mdkp/timing/FINAL_ANALYSIS.json",
    "docs/CLAIM_TO_EVIDENCE.md",
    "docs/REPRODUCIBILITY_LIMITATIONS.md",
]
for rel in required:
    check((ROOT / rel).is_file(), f"required file present: {rel}")

# Reviewer-facing figure/source contract. Publication PDFs are frozen final artwork;
# editable Office files and alternate generated figures must not sit beside them.
expected_publication_figures = {"Fig1.pdf", "Fig2.pdf", "Fig3.pdf", "Fig4.pdf", "Fig5.pdf", "FigS1.pdf"}
publication_dir = ROOT / "figures/publication"
actual_publication_figures = {p.name for p in publication_dir.glob("*.pdf")} if publication_dir.is_dir() else set()
check(actual_publication_figures == expected_publication_figures, "publication directory contains exactly Fig1-Fig5 and FigS1 final PDFs")
editable_office = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in {".ppt", ".pptx"}]
check(not editable_office, "no editable PowerPoint files are included in the reviewer-facing tree" + ("" if not editable_office else f"; found: {editable_office[:5]}"))
check(not (ROOT / "figures/generated").exists(), "no competing figures/generated directory exists")
builder_path = ROOT / "src/analysis/rebuild_derived_diagnostics.py"
builder_text = builder_path.read_text(encoding="utf-8") if builder_path.is_file() else ""
check("results/reproduced/diagnostic_figures" in builder_text and "figures/publication" in builder_text, "diagnostic plotter keeps auxiliary outputs separate from final publication PDFs")

# P6 held-out prediction metrics
p6 = pd.read_csv(ROOT / "data/core/predictor_holdout/p6_blind_predictions.csv")
y = p6["future_compatible_recurrence"].to_numpy(int)
p = p6["final_probability"].to_numpy(float)
metrics = {
    "log_loss": log_loss(y, p, labels=[0, 1]),
    "brier": brier_score_loss(y, p),
    "auroc": roc_auc_score(y, p),
    "ap": average_precision_score(y, p),
}
check(len(p6) == 225 and p6["case_id"].nunique() == 15, "P6 holdout contains 225 events in 15 cases")
check(close(metrics["log_loss"], 0.4161), f"P6 log loss reproduces 0.4161 ({metrics['log_loss']:.6f})")
check(close(metrics["brier"], 0.1397), f"P6 Brier score reproduces 0.1397 ({metrics['brier']:.6f})")
check(close(metrics["auroc"], 0.8460), f"P6 AUROC reproduces 0.8460 ({metrics['auroc']:.6f})")
check(close(metrics["ap"], 0.6105), f"P6 AP reproduces 0.6105 ({metrics['ap']:.6f})")

# P7 primary finite-memory residence
p7 = pd.read_csv(ROOT / "data/core/residence_primary/results/p7_confirmatory_matched.csv")
d25 = p7[p7["budget_fraction"].eq(0.25)]
means = d25.groupby("policy")["reuse_fraction_of_keep_all"].mean()
learned = float(means["learned"])
emp = float(means["empirical_compatible"])
check(d25[["domain", "instance_seed"]].drop_duplicates().shape[0] == 45, "P7 primary budget contains 45 independent cases")
check(close(learned, 0.9121), f"P7 learned residence mean reproduces 0.9121 ({learned:.6f})")
check(close(emp, 0.8242), f"P7 empirical-compatible residence mean reproduces 0.8242 ({emp:.6f})")
check(close(learned - emp, 0.0880), f"P7 paired mean difference reproduces +0.0880 ({learned-emp:.6f})")

# P8 measured replay
p8 = pd.read_csv(ROOT / "data/core/measured_replay/p8_external_runs.csv")
idx = ["sequence", "app", "regime", "repetition"]
w = p8.pivot_table(index=idx, columns="policy", values=["branch_pops_executed", "reused_prior_branch_pops", "useful_resumes"])
learned_vs_restart = float((w["branch_pops_executed"]["restart"] - w["branch_pops_executed"]["learned"]).mean())
learned_vs_emp_reused = float((w["reused_prior_branch_pops"]["learned"] - w["reused_prior_branch_pops"]["empirical_compatible"]).mean())
learned_vs_emp_resumes = float((w["useful_resumes"]["learned"] - w["useful_resumes"]["empirical_compatible"]).mean())
learned_vs_emp_new = float((w["branch_pops_executed"]["empirical_compatible"] - w["branch_pops_executed"]["learned"]).mean())
check(p8["sequence"].nunique() == 90, "P8 retains 90 measured-replay sequences")
check(close(learned_vs_restart, 24.72, 0.02), f"P8 learned vs restart avoids 24.72 new pops/sequence ({learned_vs_restart:.4f})")
check(close(learned_vs_emp_reused, 27.56, 0.02), f"P8 learned vs empirical adds 27.56 reused prior pops ({learned_vs_emp_reused:.4f})")
check(close(learned_vs_emp_resumes, 1.98, 0.02), f"P8 learned vs empirical adds 1.98 useful resumes ({learned_vs_emp_resumes:.4f})")
check(close(learned_vs_emp_new, 2.24, 0.02), f"P8 learned vs empirical avoids 2.24 new pops ({learned_vs_emp_new:.4f})")

# DeathStarBench retained derived inputs
seq = pd.read_csv(ROOT / "data/deathstarbench/prepared/sequence_manifest.csv")
mi = pd.read_csv(ROOT / "data/deathstarbench/measurement/MEASUREMENT_INDEX.csv")
check(len(seq) == 90, "DeathStarBench sequence manifest contains 90 sequences")
check(len(mi) == 900 and mi["seed"].nunique() == 900, "DeathStarBench measurement index contains 900 independent measured states")
check(mi["pcap_sha256"].nunique() == 900, "DeathStarBench measurement index retains 900 unique PCAP hashes")

# Primary graph timing records
rq2 = pd.read_csv(ROOT / "results/graph_runtime/primary/raw/combined_graph_results.csv")
check(len(rq2) == 6000, "primary graph timing retains 6,000 raw rows")
check(rq2["case_id"].nunique() == 60, "primary graph timing retains 60 graph cases")
check(set(rq2["level"].unique()) == {"L1", "L2", "L3", "L4"}, "primary graph timing contains L1-L4 only")
check(set(rq2["policy"].unique()) == {"restart", "empirical_pW", "learned_pW", "empirical_pC", "learned_pC"}, "primary graph timing contains the five planned policies")

# Coefficient-scored graph timing headline ratios
p0 = json.loads((ROOT / "results/graph_runtime/coefficient/analysis/P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.json").read_text())
phaseb = p0["phaseB_primary_overall_L1_L4"]
p0_pw = phaseb["P0_A_overall_L1_L4_learned_pW_vs_empirical_pW"]["learned_over_empirical_ratio"]
p0_pc = phaseb["P0_B_overall_L1_L4_learned_pC_vs_empirical_pC"]["learned_over_empirical_ratio"]
check(close(p0_pw, 1.01480, 2e-5), f"coefficient pW overall ratio reproduces 1.01480 ({p0_pw:.8f})")
check(close(p0_pc, 1.01854, 2e-5), f"coefficient pC overall ratio reproduces 1.01854 ({p0_pc:.8f})")

# MDKP timing
mdkp_raw = pd.read_csv(ROOT / "results/mdkp/timing/MERGED_RAW.csv")
mdkp = json.loads((ROOT / "results/mdkp/timing/FINAL_ANALYSIS.json").read_text())
check(len(mdkp_raw) == 1350, "MDKP timing retains 1,350 raw rows (90 cases x 3 policies x 5 repeats)")
check(mdkp_raw["global_case_index"].nunique() == 90, "MDKP timing retains 90 independent cases")
check(close(mdkp["primary_wall_direct_vs_empirical"]["ratio"], 1.01286, 2e-5), "MDKP direct/empirical wall-time ratio reproduces 1.01286")
check(close(mdkp["nodes_direct_vs_empirical"]["ratio"], 1.00083, 2e-5), "MDKP direct/empirical node ratio reproduces 1.00083")

# Manifest integrity (if present). The manifest excludes itself and generated run outputs.
manifest = ROOT / "MANIFEST_SHA256.csv"
if manifest.is_file():
    rows = list(csv.DictReader(manifest.open(newline="", encoding="utf-8")))
    listed = {row["path"] for row in rows}
    bad = []
    for row in rows:
        pth = ROOT / row["path"]
        if not pth.is_file() or pth.stat().st_size != int(row["bytes"]) or sha256(pth) != row["sha256"]:
            bad.append(row["path"])
            if len(bad) >= 10:
                break
    ignored_runtime = {"__pycache__", ".pytest_cache", ".git"}
    actual = set()
    for pth in ROOT.rglob("*"):
        if not pth.is_file() or pth == manifest:
            continue
        rel = pth.relative_to(ROOT).as_posix()
        parts = set(pth.relative_to(ROOT).parts)
        if parts & ignored_runtime:
            continue
        if rel.startswith("results/reproduced/") and rel != "results/reproduced/.gitkeep":
            continue
        actual.add(rel)
    missing = sorted(actual - listed)
    unexpected = sorted(listed - actual)
    inventory_ok = not missing and not unexpected
    check(not bad and inventory_ok, "SHA-256 manifest matches exact frozen repository inventory" + ("" if not bad and inventory_ok else f"; mismatches={bad[:5]}, unlisted={missing[:5]}, absent={unexpected[:5]}"))

if FAIL:
    print(f"\nFAILED: {len(FAIL)} checks")
    sys.exit(1)
print("\nALL CURATED-REPOSITORY CHECKS PASSED")
