# P10 Expected Result Schema — Re-audited Freeze

After `p10_all`, the output directory contains:

- `screen/p10_screen_runs.csv`
- `screen/p10_screen_aggregate.csv`
- `screen/p10_screen_selection.json`
- `development/p10_development_dataset.csv`
- `development/p10_oof_predictions.csv`
- `development/p10_final_model.joblib`
- `development/p10_calibration.joblib`
- `development/p10_history_model.joblib`
- `development/p10_history_calibration.joblib`
- `development/P10_MODEL_SUMMARY.json`
- `blind_holdout/p10_blind_dataset.csv`
- `blind_holdout/p10_blind_predictions.csv`
- `blind_holdout/P10_BLIND_METRICS.json`
- `confirmatory/P10_ENVIRONMENT.json`
- `confirmatory/p10_confirmatory_runs.csv`
- `confirmatory/p10_timing_repeats.csv`
- `confirmatory/p10_confirmatory_inference.csv`
- `confirmatory/p10_policy_descriptives.csv`
- `confirmatory/P10_CONFIRMATORY_SUMMARY.json`
- `confirmatory/P10_EXECUTION_SEAL.json`

`P10_BLIND_METRICS.json` contains prevalence, history-only, and learned H+D-analogue metrics, 2,000 case-bootstrap intervals, and learned calibration intercept/slope with case-bootstrap intervals.

The authoritative confirmatory inference CSV contains the frozen endpoint names:

1. `primary_mechanistic_learned_minus_empirical_reused_prior_nodes` — resume-weighted cumulative prior nodes represented at legal compatible resumes (not unique nodes; actual new work avoided is endpoint 2)
2. `primary_operational_empirical_minus_learned_new_nodes`
3. `primary_wallclock_restart_minus_learned_ms` — the net wall-clock test
4. `secondary_incremental_wallclock_empirical_minus_learned_ms`
5. `secondary_restart_minus_learned_new_nodes`
6. `secondary_mechanistic_learned_minus_empirical_useful_resumes`
7. `secondary_memory_learned_minus_empirical_byte_time`
8. `secondary_memory_learned_minus_empirical_peak_checkpoint_bytes`
9. `secondary_capacity_evictions_learned_minus_empirical`
10. `secondary_invalidation_evictions_learned_minus_empirical`
11. `downstream_relative_best_objective_learned_vs_restart`
12. `secondary_relative_best_objective_learned_vs_empirical`

For the first three rows, the CSV also records one-sided Wilcoxon p-values and Holm-adjusted p-values across the three-primary-endpoint family. `p10_policy_descriptives.csv` reports policy-level means/medians for retention, work, memory, eviction, objective, and median timing components, including the keep-all reference. Case-bootstrap intervals remain the principal estimation summaries.

`p10_timing_repeats.csv` records repeat number, execution position, total elapsed time, and serialization/restoration/selection/scoring/repair timing components so the frozen Latin-square counterbalancing and timing decomposition are auditable.

No result is considered manuscript evidence until the full confirmatory block passes the engineering gates and package verification is rerun.
