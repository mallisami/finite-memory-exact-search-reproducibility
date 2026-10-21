# Paper 2 P6 — Prediction of Useful Compatible Recurrence

**Status:** PASS — blind generalization established; no post-test retuning permitted.

## Scientific question

P6 asks whether decision-time information can predict

\[
p_i^{use}=P(\text{at least one legally compatible recurrence within 40 controller iterations}\mid X_i).
\]

Under the exact-repeat semantics validated in P4, reusable exact work is already known from the checkpoint, so P6 predicts useful compatible recurrence rather than saved-work magnitude.

## Pre-blind protocol discipline

Before the new final holdout labels were opened, the following were frozen and hashed:
- the 23-feature firewall;
- grouped 5-fold development procedure;
- model families and hyperparameter grids;
- calibration rule;
- primary and secondary metrics;
- base-case bootstrap procedure;
- exact byte-constrained value selector;
- final fitted model and calibration artifacts.

The sealed label SHA-256 was recorded as:

`5556a2d18c928b23dbd629432223fb1eb40a117a98a848ad13c40f065625f397`

The final holdout was then released once. No feature, model, hyperparameter, calibration, or selector change is permitted in response to its performance.

## Development selection

Development corpus:
- 45 independent base cases;
- 675 decision events;
- grouped 5-fold cross-validation by `(domain, instance_seed)`;
- target prevalence: 0.2637.

The selected model was:

- **model:** logistic regression;
- **features:** H+D (recurrence/history + dynamic controller context);
- **C:** 10.0;
- **calibration:** Platt/sigmoid.

Selected mean grouped-CV metrics before calibration:

| Metric | Development CV |
|---|---:|
| Log loss | 0.3754 |
| Brier score | 0.1273 |
| AUROC | 0.8659 |
| AUPRC | 0.7206 |

Out-of-fold Platt calibration improved log loss from 0.3754 to 0.3734 and Brier score from 0.1273 to 0.1264.

## Feature-family result

The main scientific ablation is not "deep model versus simple model." It is whether history, search state, and dynamic controller context carry distinct predictive information.

Best development log loss by feature family for logistic regression:
- **H:** log loss 0.4716, Brier 0.1511, AUROC 0.7611, AUPRC 0.6227
- **S:** log loss 0.5657, Brier 0.1899, AUROC 0.6219, AUPRC 0.3818
- **D:** log loss 0.3933, Brier 0.1338, AUROC 0.8607, AUPRC 0.6982
- **H+S:** log loss 0.4702, Brier 0.1514, AUROC 0.7730, AUPRC 0.6269
- **H+D:** log loss 0.3754, Brier 0.1273, AUROC 0.8659, AUPRC 0.7206
- **H+S+D:** log loss 0.3788, Brier 0.1287, AUROC 0.8684, AUPRC 0.7203


The key result is:

\[
\boxed{H+D\;\text{best by the frozen primary metric}}
\]


Search/checkpoint state alone was weak, while dynamic context was substantially informative and recurrence history added further value. Adding search-state features to H+D did not improve the primary metric.

## Model-complexity result

Best development result for each learned model family:
- **logistic:** H+D, log loss 0.3754, Brier 0.1273, AUROC 0.8659, AUPRC 0.7206
- **hgb:** H+D, log loss 0.3895, Brier 0.1313, AUROC 0.8578, AUPRC 0.7178
- **mlp:** H+D, log loss 0.4020, Brier 0.1317, AUROC 0.8672, AUPRC 0.7262


Therefore the nonlinear models did not justify their additional complexity. P6 does **not** support adding a GNN at this stage.

## One-time blind final test

Blind holdout:
- 15 completely new independent base cases;
- 225 decision events;
- five new seeds per domain;
- target prevalence after release: 0.2578.

### Primary frozen model

| Metric | Blind result | 95% case-bootstrap CI |
|---|---:|---:|
| Log loss | 0.4161 | [0.3344, 0.5071] |
| Brier score | 0.1397 | [0.1093, 0.1732] |
| AUROC | 0.8460 | [0.7843, 0.9005] |
| AUPRC | 0.6105 | [0.4470, 0.7869] |

Calibration on the blind test:
- intercept: -0.250 (95% case-bootstrap [-0.749, 0.375]);
- slope: 0.791 (95% case-bootstrap [0.516, 1.426]).

### Predeclared baselines

| Predictor | Log loss | Brier | AUROC | AUPRC |
|---|---:|---:|---:|---:|
| Development prevalence | 0.5708 | 0.1914 | 0.5000 | 0.2578 |
| History-frequency | 0.8322 | 0.2569 | 0.6611 | 0.4141 |
| **Frozen logistic H+D** | **0.4161** | **0.1397** | **0.8460** | **0.6105** |

Relative to the development-prevalence predictor, the blind model reduces log loss by about **27.1%** and Brier score by about **27.0%**. Its AUPRC is about **2.37×** the blind positive prevalence.

## Domain-descriptive boundary

The blind test contains only five independent cases per domain. Domain-specific numbers are therefore descriptive, not separate superiority claims.

- **generic:** prevalence 0.307, log loss 0.449, AUROC 0.836, AUPRC 0.664.
- **workflow:** prevalence 0.333, log loss 0.372, AUROC 0.884, AUPRC 0.838.
- **microservice:** prevalence 0.133, log loss 0.427, AUROC 0.808, AUPRC 0.328.


## Interpretation

P6 establishes that useful compatible recurrence is predictable on unseen base cases from **history plus dynamic controller context**, using a simple calibrated logistic model. The result does not depend on a deep model or graph network.

The strongest scientific interpretation is:

> Future checkpoint usefulness is not determined only by how much exact search work is stored. Recurrence history and the current dynamics of the outer search provide enough pre-decision information to estimate whether dormant exact state will become legally reusable again.

P6 does **not** establish that prediction improves the optimizer end to end. That causal/controller claim is reserved for P7, where the frozen P6 probabilities must drive the exact finite-byte retention selector inside the online controller.

## No-retuning rule

The blind test has been released. The P6 model is now frozen permanently as version P6-v1. Any change to features, model family, hyperparameters, calibration, or decision mapping would define a new model version and require a new independent final holdout.
