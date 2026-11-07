# PCR2: reviewer reproducibility entry point

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

The original P10 development and blind datasets, four fitted model artifacts, execution source snapshot, original/repeated P10 result seals, and case-level measurements are now included under `results/mdkp/p10_20261107/`. The complete author archive still contains additional original AWS host records and diagnostic provenance that have not all been synchronized into public GitHub. The author archive contains 7,973 files with only two intentionally repeated P8 numerical summary copies. This curated GitHub is **not yet certified to replace that full author package**. See `docs/PCR2_REVIEWER_COMPLETENESS_AUDIT_20261107.md`. Do not update the manuscript's data-availability URL until that gate is closed.

Repository file paths sometimes intentionally repeat source data in preserved historic protocol snapshots. Git stores identical blobs once. The duplicate auditor `python src/analysis/audit_release_duplicates.py` reports those aliases without deleting scientific evidence.
