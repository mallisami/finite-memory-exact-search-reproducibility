# Paper 2 P9 — Cross-Domain Prediction Generalization Results

## Status
**Complete.** The P6 model form was frozen: logistic H+D, C=10, Platt calibration, no feature or hyperparameter selection in P9.

## Leave-one-domain-out results

| Held-out domain | Log loss | Brier | AUROC | AUPRC |
|---|---:|---:|---:|---:|
| generic | **0.3425** | **0.1151** | **0.8841** | **0.6500** |
| workflow | **0.3761** | **0.1257** | **0.9038** | **0.8250** |
| microservice | **0.4018** | **0.1361** | **0.8478** | **0.6713** |

Macro averages:

- log loss: **0.3735**;
- Brier: **0.1256**;
- AUROC: **0.8785**;
- AUPRC: **0.7154**.

The frozen model form beat both the training-prevalence and history-only recurrence baselines on held-out-domain **log loss in all three transfers**.

## Interpretation
P9 supports the claim that the P6 signal is not confined to one structured assignment family. The predictive relationship between recurrence history + dynamic controller context and future compatible recurrence transfers across the three generated domains without target-domain tuning.

P9 is a prediction-generalization result only; it does not by itself imply an optimization-quality benefit.
