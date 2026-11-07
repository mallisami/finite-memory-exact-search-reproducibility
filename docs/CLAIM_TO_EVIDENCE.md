# Claim-to-evidence map

This map links the paper's principal displays and claims to the curated repository paths.

| Paper item / claim | Retained evidence |
|---|---|
| Fig. 2(a): development model/feature selection | `data/core/predictor_development/p6_feature_ablation_best_configs.csv` |
| Fig. 2(b), Table 4: held-out prediction/calibration | `data/core/predictor_holdout/p6_blind_predictions.csv`, `p6_blind_reliability_bins.csv` |
| Fig. 3, Table 5: finite-memory residence | `data/core/residence_primary/results/p7_confirmatory_runs.csv`, `p7_confirmatory_matched.csv` |
| Table 5: FIFO/LRU/Random controls | `data/core/residence_external_controls/` and `results/residence/external_controls/` |
| Fig. 4 (October release): original measured-workload work displacement | `data/core/measured_replay/p8_external_runs.csv`, `p8_external_strata.csv` |
| Fig. 4 (November corrected AWS result): derived figure-data summaries | `results/measured_replay/aws_20261107/p8_external_runs.csv`, `results/measured_replay/aws_20261107/P8_AWS_TRIPLET_BLOCK_REANALYSIS.json`, plus `figures/data/p8_aws_triplet_block_work_saving_20261107.csv` and `figures/data/p8_aws_app_regime_heterogeneity_20261107.csv` |
| Historical P9 fixed-specification transfer | `data/core/cross_family_transfer/p9_cross_domain_metrics.csv` |
| Current nested family-held-out P9 | `results/transfer/nested_20261107/nested_p9_domain_metrics.csv`, `results/transfer/nested_20261107/NESTED_P9_SUMMARY.json`, and `figures/data/p9_nested_family_heldout_20261107.csv` |
| Tables 6-7, Fig. 5: primary graph timing | `results/graph_runtime/primary/raw/combined_graph_results.csv` and `analysis/` |
| Table 6: coefficient-scored timing | `results/graph_runtime/coefficient/analysis/P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.json` plus `raw/` |
| Table 8: MDKP executed nodes and wall time | `results/mdkp/timing/MERGED_RAW.csv`, `FINAL_ANALYSIS.json` |
| MDKP depth-cost / matched-trajectory diagnostics | `results/mdkp/diagnostics/MDKP_WORK_TO_RUNTIME_FINAL_ANALYSIS.json` |
| Fixed-byte, bound-aware, second-scale RQ1 sensitivities | `results/posthoc/` |
| Future-aware fixed-trace MDKP diagnostic | `results/posthoc/MDKP_OFFPOLICY_DELTA_N_DIAGNOSTIC.json` |

| Original P10 and same-case replication (45 cases each, not independent) | `results/mdkp/p10_20261107/original/` and `results/mdkp/p10_20261107/same_case_repeat/` (inference, case results, timing repeats); comparison summary: `results/mdkp/p10_original_vs_replication_20261107.csv` |

## Guardrails

- `results/posthoc/` contains revision-stage analyses and must not be interpreted as prespecified primary evidence.
- keep-all is an upper-resource opportunity reference, not a same-budget optimum;
- the future-aware MDKP diagnostic is in-sample and non-deployable;
- cross-environment timing differences are descriptive, while within-campaign matched policy contrasts are inferential.

## Full P10 provenance and sample independence

Original P10 development/OOF records (30 development cases), blinded evaluation (15 held-out cases), frozen model artifacts, and executed source are in `results/mdkp/p10_20261107/original/{development,blind_holdout}/` and `experiments/mdkp/p10_20261107/executed_source_snapshot/`. Both P10 execution seals and associated metadata are under each run's `confirmatory/` subfolder; the six original curated inference, case-run and timing CSVs remain at the run roots `results/mdkp/p10_20261107/{original,same_case_repeat}/`, without duplication. The same 45 case identities recur in the timing repeat; never treat them as 90 independent cases. `tests/test_p10_complete_source.py` verifies both seals and source hashes.
