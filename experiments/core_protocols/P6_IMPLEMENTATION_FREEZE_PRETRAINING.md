# Paper 2 P6 — Implementation Freeze Before Training

Date: 2026-10-05
Base protocol: `PAPER2_P6_FROZEN_PROTOCOL_PRETRAINING.md`

This file resolves implementation details that were not numerically specified in the base protocol. It is written before any P6 model fitting and before the sealed holdout labels are opened.

## History-frequency baseline
For decision iteration t, historical exact-context count c, and horizon h=40, estimate a per-iteration recurrence rate with Jeffreys/Laplace-style smoothing:

lambda_hat = (c + 0.5) / (t + 1.0)

and map it to a horizon event probability with a Poisson approximation:

p_hist = 1 - exp(-h * lambda_hat).

Clip probabilities to [1e-6, 1-1e-6] for log-loss evaluation. This is a recurrence-only baseline and intentionally does not use future compatibility.

## Preprocessing
Categorical decision-time features:
- `current_destroy_op_index`
- `current_repair_arm_index`

Logistic regression and MLP:
- one-hot encode these two categorical features using categories learned on each training fold only and `handle_unknown='ignore'`;
- standardize all remaining continuous/numeric features using training-fold mean and scale only.

Histogram gradient boosting:
- use the same two operator variables as ordinal integer inputs plus the remaining numeric features without standardization; no future or identifier field is used.

## Development folds
Use the frozen 5 grouped folds from seed-list position modulo 5 independently inside each domain. No `(domain, instance_seed)` group may cross folds.

## Model/configuration selection
Evaluate every frozen model-grid configuration for every frozen feature family H, S, D, H+S, H+D, H+S+D.
Select by mean held-out fold log loss, then mean Brier score, then mean AUPRC, then simpler model/configuration.

For MLP, fit seeds 17/29/43 on each training fold and average their held-out probabilities before scoring.

## Calibration
After selecting one base model/configuration/feature family, concatenate its out-of-fold development probabilities. Compare:
1. no calibration;
2. Platt/sigmoid calibration fit on the logit of the out-of-fold probabilities.

Choose by development log loss, tie by Brier score. A Platt model is a one-variable logistic regression with effectively unregularized C=1e6.

## Final refit
Refit the selected base configuration on all 45 development cases. For an MLP, refit all three frozen seeds and average probabilities. Apply the frozen calibration mapping selected above.

## Metrics
Primary: log loss, Brier score.
Secondary: AUROC, AUPRC, calibration intercept/slope.

## Case-level bootstrap
The blind-test confidence interval procedure is frozen before label release:
- nonparametric bootstrap over the 15 independent `(domain, instance_seed)` base cases;
- 2,000 bootstrap replicates;
- random seed 20261005;
- all event rows belonging to a sampled case are carried together;
- 95% percentile intervals;
- for AUROC/AUPRC/calibration metrics, bootstrap replicates lacking both classes are omitted for that metric only.

## Blind release
Before opening the sealed labels, hash:
- this implementation-freeze file;
- the development-result tables;
- the selected model specification;
- the fitted final development model artifact(s);
- the calibration artifact;
- the 23-feature firewall.

No change is permitted after blind-label release without declaring a new model version and generating a new independent holdout.
