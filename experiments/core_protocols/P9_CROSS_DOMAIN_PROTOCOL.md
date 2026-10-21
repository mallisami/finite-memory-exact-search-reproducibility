# Paper 2 P9 — Cross-Domain Prediction Generalization

**Frozen after P6/P7/P8 and before leave-one-domain-out outcomes are generated.**

## Question
Does the already selected P6 model form learn transferable recurrence/dynamic-context structure, or does its predictive value depend on seeing the target structured domain during training?

## Data
Use only the original P5.5 natural-controller development corpus (45 independent cases; 15/domain; 675 event rows). The blind P6 holdout and P8 measured workload are not used for training.

## Transfer design
Three leave-one-domain-out transfers:
1. train workflow + microservice; test generic;
2. train generic + microservice; test workflow;
3. train generic + workflow; test microservice.

## Frozen model form
- logistic regression;
- H+D features exactly as P6-v1;
- C=10;
- same standardization and one-hot handling;
- Platt calibration;
- no hyperparameter/feature selection in P9.

For each transfer, Platt calibration is fit from grouped out-of-fold predictions using only the two training domains. The held-out domain is touched once for final evaluation.

## Metrics
Primary: log loss and Brier score.
Secondary: AUROC and AUPRC.
Comparators: training prevalence and the frozen history-only recurrence formula.

## Interpretation
- success means the fixed model form beats both simple comparators on the held-out domain, especially on probability quality;
- failure on one domain is reported as a transfer boundary and does not trigger target-domain retuning;
- P9 is a prediction-generalization test, not an online optimization-outcome experiment.
