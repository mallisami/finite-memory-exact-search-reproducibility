# Paper 2 P7 — Confirmatory Online Persistence Protocol

**Frozen after P7B structural-regime selection and before confirmatory outcome execution.**

## Basis for confirmatory regime
The corrected P7B structural characterization used no objective outcome for regime selection. Six of nine regimes met the preregistered multi-state criteria. The fixed lexicographic selector chose:

- nodes: **24**
- hosts: **6**
- destroy size: **12**
- exact-search slice: **8 deterministic branch pops/call**

because it had the highest median fraction of iterations with `K_live >= 4` (0.88), followed by median peak live width 51 and median 59 useful resumes across the 9 characterization cases.

The pre-amendment P7 pilot/P7A results are superseded for online portfolio-width/reuse interpretation and are **not** used to choose this regime or the primary budget.

## Independent confirmatory cases
- domains: generic, workflow, microservice;
- fresh seeds/domain: **3031–3045** (15/domain);
- independent cases: **45**;
- controller iterations/case: **200**;
- repair trace: ordinary matched-controller trace with destroy size 12;
- no recurrence sampler;
- no supplied outcome-tuned trace.

These seeds were not used in P5.5/P6 development, the P6 blind test, the original P7 pilot, or P7B regime selection.

## Structural-OOD status of the frozen predictor
P6-v1 was trained on the P5.5 destroy-size-8 corpus. P7 uses destroy size 12 because that regime was selected by objective-blind portfolio mechanics. The P6 model is therefore evaluated **frozen and without recalibration** under this structural shift. Its H+D feature set contains no destroy-size/search-state feature, and no adaptation is permitted before confirmatory execution.

## Policies
1. `restart` — no persistence;
2. `empirical_compatible` — history-based recurrence × compatibility probability, exact byte-constrained selection;
3. `learned` — frozen P6-v1 calibrated logistic H+D probability, exact byte-constrained selection;
4. `keep_all` — retain every valid unfinished checkpoint; upper-resource opportunity reference, **not a clairvoyant oracle**.

## Persistence budgets
For each case, budgeted policies use exactly 25%, 50%, and 75% of that case's keep-all peak checkpoint bytes, subject only to the physical requirement that one checkpoint fit. The effective fraction is recorded.

## Primary budget
**25%** is the primary decision-pressure condition because it is the tightest preregistered budget and, in the P7B-selected regime, one checkpoint is only ~2.7% of peak keep-all bytes at the median. Thus 25% is naturally nondegenerate and imposes genuine competition. This choice does **not** depend on policy outcome.

The 50% and 75% levels are secondary dose-response conditions.

## Outcomes
Primary mechanistic outcome:
- fraction of keep-all reusable prior branch work captured.

Primary optimization outcome:
- relative best-objective improvement versus restart:
  `(restart_best - policy_best) / abs(restart_best)`; positive is better.

Secondary outcomes:
- normalized anytime improvement versus restart;
- useful resumes;
- repeated branch work reused;
- byte-time occupancy;
- capacity/invalidation evictions;
- serialization/restoration/selection/model-scoring overhead;
- case counts better/no-worse than restart;
- gap to keep-all opportunity reference;
- effective capacity fraction and realized live-portfolio width.

## Primary comparisons
At 25% capacity:
1. learned vs empirical-compatible for reuse capture;
2. learned vs restart for relative best-objective improvement;
3. learned vs empirical-compatible for relative best objective and anytime outcome.

## Inference
- independent unit: base case `(domain, seed)`, n=45;
- paired case-level comparisons only;
- deterministic case bootstrap, 10,000 resamples, for mean paired effects and 95% CIs;
- paired Wilcoxon signed-rank tests are secondary; Holm correction across the prespecified primary comparison family;
- report effect sizes and sign counts regardless of p-values.

## Interpretation rules
- `keep_all` is an upper-resource reference, not a future-aware oracle;
- no P6 model retraining/recalibration is allowed;
- no regime/seed removal based on outcome is allowed;
- if learned improves reuse but not optimization outcome, report that separation explicitly;
- if learned and empirical are indistinguishable in objective despite different reuse, do not claim ML is necessary for optimization benefit;
- if structural shift degrades P6 probability quality, report that as OOD evidence rather than adapting the model post hoc.
