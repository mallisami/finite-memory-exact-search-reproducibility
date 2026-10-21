# Reviewer-analysis provenance

This folder contains **post-freeze reviewer diagnostics**, not a replacement for the prespecified P6/P7/P8/P9 evidence hierarchy.

Authoritative source archive used for verification: `PCR_PAPER2_REPRODUCIBILITY_FINAL_2026-10-06.zip` (frozen reproducibility package). The analysis reads the frozen P6 held-out predictions, P7 confirmatory runs, P8 measured-workload runs, P9 cross-domain predictions, and DeathStarBench measurement index.

## Added diagnostics

- `p6_blind_case_bootstrap_summary.csv`: case-level uncertainty for held-out metrics; no event-level resampling.
- `p6_ablation_fold_ranges.csv`: descriptive min--max across the five grouped development folds for the selected logistic configuration within each feature family.
- `p9_case_bootstrap_summary.csv`: case-level uncertainty within each held-out structural family.
- `p8_stratified_work_saving_and_economics.csv`: reviewer-requested comparator intervals, learned-minus-empirical avoided-work contrast, and matched implementation break-even calculations.
- `p8_app_regime_heterogeneity.csv`: descriptive application-by-regime work-saving heterogeneity.
- `dsb_measurement_independence_audit.json`: counts of measured sequence/state identities, measurement seeds, and packet-capture hashes.
- `p7_posthoc_simple_baselines.csv` and `p7_posthoc_baseline_summary.csv`: post-hoc history-only and invested-work-only diagnostics on the frozen 45 P7 case identities at the 25% budget.
- `paper2_online_pilot_original.py`, `paper2_online_pilot_posthoc.py`, and `posthoc_policy_patch.diff`: exact diagnostic code change used to add the two simple policies. The patch changes only the valuation policy options; the common exact selector and frozen P7 regime/seeds remain unchanged.
- `recompute_reviewer_diagnostics.py`: reproduces the reviewer tables from the frozen raw outputs plus the post-hoc diagnostic CSVs.

## Oracle boundary

A static realized-future oracle is **not** reported. In this online process, changing retention can change the accepted repair and subsequent trajectory, so future recurrence/compatibility labels generated under one policy are not policy-invariant counterfactual values for another policy. The frozen implementation states this boundary explicitly. `keep_all` is an upper-resource opportunity reference, not a clairvoyant oracle.

## Interpretation

The prespecified confirmatory hypothesis family remains unchanged. The simple baselines, comparator confidence intervals, heterogeneity summaries, and break-even calculations are explicitly labelled post-hoc reviewer analyses in the manuscript/supplement.
