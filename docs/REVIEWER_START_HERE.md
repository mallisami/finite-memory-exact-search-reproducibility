# Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse

## Reviewer reproducibility guide

**Begin here (Python 3.11, from the repository root):**

```bash
python -m pip install -r requirements.txt
bash verify.sh
bash run_tests.sh
python src/analysis/rebuild_publication_figures.py
```

The first two scripts check the frozen manifest, scientific quantities, and regression contracts; the plot builder regenerates five data-driven figures in `results/reproduced/` without overwriting the six frozen publication PDFs. See [the step-by-step matrix](REPRODUCIBILITY_VERIFICATION_MATRIX.md) for expected evidence and boundaries. The original multi-host timing campaigns are **not** rerun by these commands.

**Review scope:** This is a public curated code/evidence release, *not* the author-side complete archive or a copy of the manuscript. For submission packaging and anonymity checks, see [the editor guide](EDITOR_SUBMISSION_GUIDE.md).

This is the intended single public **code and evidence** repository. It deliberately contains **neither the paper nor Online Resource 1**. The six PDFs under `figures/publication/` are final research figures.

Run `python -m pip install -r requirements.txt`, `bash verify.sh`, and `bash run_tests.sh`.

**Authoritative current November data:**

| Study | Canonical files |
| --- | --- |
| P6 sealed prediction | `data/core/predictor_holdout/` |
| P7 retention | `data/core/residence_primary/results/` |
| Corrected AWS P8 | `results/measured_replay/aws_20261107/` |
| Nested held-out P9 | `results/transfer/nested_20261107/` |
| P10 independent and repeat | `results/mdkp/p10_20261107/` (same 45 cases reused) |
| RQ2 four-host three-arm | `results/rq2_three_arm_aws_20261107/` |
| RQ3 VM90 timing | `results/mdkp/timing/` |
| Graph timing | `results/graph_runtime/` |

Earlier fixed-P9 and pre-AWS P8 datasets in `data/core/` are **historical**, never sources for the current corrected November figure interpretation. For all displays use `docs/CLAIM_TO_EVIDENCE.md` and `docs/NOVEMBER_2026_SOURCE_ALIGNMENT.md`.

The four-host three-arm timing data have pseudonymized host identifiers. Four-host RQ2 shows faster direct scoring than the original learned implementation, **not a proven overall runtime advantage over the empirical-compatible policy**. The study is controller-level timing, not end-to-end application latency.

## Current boundary

The original P10 development and blind datasets, four fitted model artifacts, execution source snapshot, original/repeated P10 result seals, and case-level measurements are now included under `results/mdkp/p10_20261107/`. The author archive still retains original AWS host records and historical machine provenance outside this public GitHub. This is an intentional upstream-execution boundary rather than missing current paper numerical results. For the *available reported numerical evidence, runnable core code and author-derived figures*, this repository is the **single canonical reviewer source**, but the author-side manuscript is labeled *Anonymous submission*, so citation or exposure of this identity-bearing URL needs journal approval. It is not a byte-complete copy of 7,973 author-archive files and does not promise original raw packet capture reconstruction. See `docs/PCR2_REVIEWER_COMPLETENESS_AUDIT_20261107.md` and `docs/REPRODUCIBILITY_LIMITATIONS.md`.

Repository file paths sometimes intentionally repeat source data in preserved historic protocol snapshots. Git stores identical blobs once. The duplicate auditor `python src/analysis/audit_release_duplicates.py` reports those aliases without deleting scientific evidence.

**RQ3 diagnostic correction (NOT ADOPTED):** the full reconstructed labels, paired CPU repeatability results, and the development-only negative held-out policy experiment are retained in [`results/mdkp/rejected_rq3_diagnostics_20261106/`](../results/mdkp/rejected_rq3_diagnostics_20261106/) and explained in [`RQ3_REJECTED_DIAGNOSTIC_REPRODUCTION.md`](RQ3_REJECTED_DIAGNOSTIC_REPRODUCTION.md). Do not confuse them with the official VM90 result.

The canonical claim-to-source crosswalk is [`REVIEWER_EVIDENCE_INDEX.csv`](REVIEWER_EVIDENCE_INDEX.csv); the exact inclusion boundary is [`REVIEWER_EVIDENCE_SOURCE_OF_TRUTH_20261107.md`](REVIEWER_EVIDENCE_SOURCE_OF_TRUTH_20261107.md).

**Publication figures:** `python src/analysis/rebuild_publication_figures.py` executes the original author-derived plotting pipeline; its five generated PDFs matched author artwork at 1.2× raster comparison. See [figure builder provenance](FIGURE_BUILDER_PROVENANCE.md).
