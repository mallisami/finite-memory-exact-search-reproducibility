# Paper 2 P8 — Measured-Workload External Validation Protocol

**Frozen after confirmatory P7 analysis and before Paper-2 policy outcomes are generated on the measured workload.**

## Purpose
Test whether the frozen Paper-2 persistence valuation mechanism transfers from the structured synthetic development environment to previously measured DeathStarBench dynamics without retraining, recalibration, regime selection, or outcome-tuned filtering.

## External dataset
Use the existing hash-frozen E-DSB prepared sequences that passed the original construct-validation gate before solver outcomes:
- applications: Social Network, Hotel Reservation, Media Service;
- regimes: `step`, `burst`, `ramp`;
- repetitions: 10/application/regime;
- total independent measured sequences: **90**;
- states/sequence: **10**;
- measured interaction matrices and fixed application demands are consumed unchanged from `results/dsb_dynamic/prepared/sequences`;
- original frozen-input hash verification must pass before execution.

These measured workload sequences were not used to train, tune, calibrate, or select the Paper-2 P6 predictor.

## External replay construction
For every measured sequence:
1. reconstruct the same deterministic 10-host environment from the existing E-DSB preparation/solver protocol;
2. keep the measured state order unchanged;
3. generate a common exogenous ordinary-controller repair-context trace for each state, **20 repair decisions/state** (200/sequence), destroy size **12**;
4. all Paper-2 policies receive the same repair contexts and acceptance random variates;
5. at each measured external state transition, every dormant checkpoint is reconciled against the new measured interaction state using the existing exact PCR cache-equality compatibility rule; incompatible checkpoints are invalidated before the next repair decision.

## Frozen search/prediction settings
- exact-search slice: **8 deterministic branch pops/call**;
- learned predictor: frozen P6-v1 calibrated logistic H+D model;
- **no retraining or recalibration**;
- future horizon: 40 repair decisions, unchanged;
- same exact byte-constrained expected-value selector as confirmatory P7.

## Policies
1. `restart` — no persistence;
2. `empirical_compatible` — deployable recurrence × compatibility estimate with exact selector;
3. `learned` — frozen P6-v1 probability with exact selector;
4. `keep_all` — retain every currently valid unfinished checkpoint, upper-resource opportunity reference only.

## Persistence pressure
Use **25% of each sequence's keep-all peak valid checkpoint bytes**, subject only to the physical requirement that one checkpoint fit. The effective fraction is reported. No alternate budget is selected after inspecting external outcomes.

## Outcomes
Primary external mechanistic outcome:
- fraction of keep-all reusable prior branch work captured by learned vs empirical-compatible.

Primary external optimization outcome:
- sequence-normalized mean objective improvement versus restart; positive favors persistence.

Secondary outcomes:
- final-state objective difference vs restart;
- useful compatible resumes;
- repeated branch work reused;
- transition compatibility/invalidation counts;
- live portfolio width and byte-time;
- capacity evictions;
- persistence/model/selector overhead;
- sign counts by application and regime.

## Prespecified external interpretation
- `step` and `burst` are recurrent measured regimes;
- `ramp` is an operating-boundary/low-recurrence control and is not pooled to manufacture a positive recurrent-regime result;
- the primary Paper-2 external mechanistic contrast is learned minus empirical-compatible on all 90 sequences, with recurrent-regime stratification reported;
- objective effects are reported whether positive, null, or adverse;
- if keep-all itself does not improve optimization quality, no learned-policy optimization advantage is claimed;
- if the frozen learned model improves retention but not objective quality, that separation is reported as an external boundary, not repaired post hoc.

## Inference
- independent unit: complete measured sequence, n=90;
- paired sequence-level effects;
- 10,000-replicate stratified bootstrap, resampling repetitions within application × regime cells;
- paired Wilcoxon tests are secondary;
- report application/regime strata descriptively regardless of significance.

## External-validity boundary
This is measured-workload shadow replay. It validates policy behavior under measured microservice interaction dynamics, not live migration latency, deployment SLO improvement, or production hardware overhead.
