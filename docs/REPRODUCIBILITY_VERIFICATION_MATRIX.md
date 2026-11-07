# Reviewer verification matrix

**Study:** Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse

Run all commands at repository root. GitHub CI uses **Ubuntu and Python 3.11**; `requirements.txt` pins the listed direct Python dependencies. Platform-dependent and unpinned transitive dependencies can differ on other machines. See `environment/` for retained execution records.

| Step | Command / input | Expected check | Boundary |
| --- | --- | --- | --- |
| 1. Environment | `python --version`; `python -m pip install -r requirements.txt` | Python 3.11 used by CI; required packages install | Not the original AWS hardware |
| 2. Integrity and numerical checks | `bash verify.sh` | Ends with `ALL CURATED-REPOSITORY CHECKS PASSED` and exits 0 | Checks retained data and SHA-256 inventory, not unavailable upstream captures |
| 3. Regression and source contracts | `bash run_tests.sh` | Pytest exits 0 | Includes public scientific/release checks, not an external physical experiment |
| 4. Final figures | `python src/analysis/rebuild_publication_figures.py` | Fig2–Fig5 and FigS1 produced under `results/reproduced/publication_figures/` | Figure 1 is frozen; generated PDF bytes need not match platform-specific metadata |
| 5. Core chain (optional extended rerun) | `bash reproduce.sh` | A new `results/reproduced/` run ID; existing runs preserved | Does not recreate original multi-host timing campaigns |
| 6. Claim mapping | `docs/REVIEWER_EVIDENCE_INDEX.csv` | One current source per listed claim family | Historical and current estimands are never silently pooled |
| 7. Runtime evidence | `results/rq2_three_arm_aws_20261107/`; `results/graph_runtime/`; `results/mdkp/timing/` | Recorded rows, schedules and analyses inspectable | New hardware timings are new replication evidence |

## Principal interpretation safeguards

- **RQ1/P7:** keep-all is a larger-resource reference, not a same-memory-budget oracle. Retained search work is not automatically saved wall time.
- **P8:** use corrected AWS data in `results/measured_replay/aws_20261107/`, not earlier pre-AWS publication summaries; 90 sequences are grouped into **30 application–repetition blocks** for the relevant uncertainty analysis.
- **P9:** nested family-held-out analysis is current; earlier fixed-selection P9 is historical.
- **P10:** original and repetition reuse the **same 45 case identities**; never claim 90 independent confirmations.
- **RQ2 three-arm:** the public raw records retain P7 3,240 and P8 2,160 measurement rows with pseudonymized host IDs. Faster optimized scoring does not establish an overall policy wall-time advantage over empirical-compatible.
- **RQ3:** the official MDKP 90-case result is negative/uncertain. Reconstructed-label and CPU-label proposals in `results/mdkp/rejected_rq3_diagnostics_20261106/` are development-only **NO-GO**, not adopted methods.
- **Time and portability:** controller-level AWS RQ2 is not full end-to-end production latency. Original timing conditions cannot be replayed identically by running `reproduce.sh`.

## Reviewer evidence map

Start with [Reviewer Start Here](REVIEWER_START_HERE.md), [Claim to Evidence](CLAIM_TO_EVIDENCE.md), [machine-readable evidence index](REVIEWER_EVIDENCE_INDEX.csv), [original-versus-public boundary](REVIEWER_EVIDENCE_SOURCE_OF_TRUTH_20261107.md), and [documented limitations](REPRODUCIBILITY_LIMITATIONS.md). Record the *exact tested Git commit* in any review report. No statistical superiority claim follows merely from a successful verification script.
