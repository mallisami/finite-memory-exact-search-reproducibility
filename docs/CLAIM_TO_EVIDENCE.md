# Claim-to-evidence map

This map links the paper's principal displays and claims to the curated repository paths.

| Paper item / claim | Retained evidence |
|---|---|
| Fig. 2(a): development model/feature selection | `data/core/predictor_development/p6_feature_ablation_best_configs.csv` |
| Fig. 2(b), Table 4: held-out prediction/calibration | `data/core/predictor_holdout/p6_blind_predictions.csv`, `p6_blind_reliability_bins.csv` |
| Fig. 3, Table 5: finite-memory residence | `data/core/residence_primary/results/p7_confirmatory_runs.csv`, `p7_confirmatory_matched.csv` |
| Table 5: FIFO/LRU/Random controls | `data/core/residence_external_controls/` and `results/residence/external_controls/` |
| Fig. 4 (October release): original measured-workload work displacement | `data/core/measured_replay/p8_external_runs.csv`, `p8_external_strata.csv` |
| Fig. 4 (November corrected AWS result): derived figure-data summaries | `figures/data/p8_aws_triplet_block_work_saving_20261107.csv`, `figures/data/p8_aws_app_regime_heterogeneity_20261107.csv`; full raw AWS records are in the separate author-side archive |
| Historical P9 fixed-specification transfer | `data/core/cross_family_transfer/p9_cross_domain_metrics.csv` |
| Current nested family-held-out P9 | `figures/data/p9_nested_family_heldout_20261107.csv`; full nested analysis in the author-side archive |
| Tables 6-7, Fig. 5: primary graph timing | `results/graph_runtime/primary/raw/combined_graph_results.csv` and `analysis/` |
| Table 6: coefficient-scored timing | `results/graph_runtime/coefficient/analysis/P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.json` plus `raw/` |
| Table 8: MDKP executed nodes and wall time | `results/mdkp/timing/MERGED_RAW.csv`, `FINAL_ANALYSIS.json` |
| MDKP depth-cost / matched-trajectory diagnostics | `results/mdkp/diagnostics/MDKP_WORK_TO_RUNTIME_FINAL_ANALYSIS.json` |
| Fixed-byte, bound-aware, second-scale RQ1 sensitivities | `results/posthoc/` |
| Future-aware fixed-trace MDKP diagnostic | `results/posthoc/MDKP_OFFPOLICY_DELTA_N_DIAGNOSTIC.json` |

| Original P10 and same-case replication (45 cases each, not independent) | `results/mdkp/p10_original_vs_replication_20261107.csv`; original sealed result files are in the author-side archive |

## Guardrails

- `results/posthoc/` contains revision-stage analyses and must not be interpreted as prespecified primary evidence.
- keep-all is an upper-resource opportunity reference, not a same-budget optimum;
- the future-aware MDKP diagnostic is in-sample and non-deployable;
- cross-environment timing differences are descriptive, while within-campaign matched policy contrasts are inferential.
