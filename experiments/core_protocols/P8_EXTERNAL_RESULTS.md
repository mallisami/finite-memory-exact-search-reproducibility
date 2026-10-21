# Paper 2 P8 — Measured-Workload External Validation Results

## Status
**Complete: 90/90 frozen DeathStarBench measured sequences.**

- 3 applications: Hotel Reservation, Media Service, Social Network;
- 3 regimes: burst, step, ramp;
- 10 repetitions/application/regime;
- 10 measured states/sequence;
- 200 Paper-2 repair decisions/sequence;
- 25% persistence budget;
- frozen P6-v1, no retraining/recalibration.

The original E-DSB frozen-input verifier passed before execution.

## External retention result
The preregistered learned-minus-empirical `reuse_fraction_of_keep_all` had:

- mean difference: **+0.01774**;
- stratified 95% bootstrap CI: **[-0.01466, +0.04206]**;
- positive/negative/tied sequences: **69 / 11 / 10**;
- one-sided Wilcoxon p: **1.58e-08**.

Because online trajectories can diverge, `reuse_fraction_of_keep_all` is not strictly bounded by 1: a policy may experience more reusable work on its own trajectory than keep-all experiences on a different trajectory. The preregistered ratio is therefore retained transparently, but it is not treated as a literal capture percentage under trajectory divergence.

A trajectory-native companion metric gives the clearer mechanistic result:

- learned minus empirical reused prior branch pops: **+27.56 pops/sequence mean**;
- stratified 95% bootstrap CI: **[+11.91, +43.56]**;
- median difference: **+16**;
- positive/negative/tied: **69 / 11 / 10**;
- one-sided Wilcoxon p: **1.60e-08**.

Useful resumes also increased:

- learned minus empirical: **+1.98 resumes/sequence mean**;
- 95% stratified bootstrap CI: **[+1.44, +2.46]**.

## Realized branch-work saving
Unlike confirmatory P7, the measured dynamic workload sometimes let persistence reach exact termination earlier. Relative to restart:

- learned newly executed branch pops saved: **+24.72/sequence mean**;
- 95% stratified bootstrap CI: **[+17.53, +32.24]**;
- median: **11.5**;
- positive/negative/tied sequences: **58 / 7 / 25**.

Empirical-compatible saved **22.48** pops/sequence on average; keep-all saved **24.64**.

This is a real compute-work effect, but it is modest compared with the 1600-pop nominal 200-call budget.

## External optimization result
The frozen learned policy's mean sequence-normalized objective improvement versus restart was:

- mean: **+0.000745**;
- stratified 95% bootstrap CI: **[-0.000967, +0.002508]**;
- positive/negative/tied: **38 / 25 / 27**;
- one-sided Wilcoxon p: **0.0627**.

Thus optimization-quality improvement is **unresolved**, not established.

The keep-all reference is also unresolved:

- mean vs restart: **+0.000390**;
- 95% bootstrap CI: **[-0.001937, +0.002471]**;
- positive/negative/tied: **40 / 25 / 25**.

Because even keep-all lacks a robust objective advantage, P8 does not support claiming that better persistence necessarily improves measured-workload optimization quality.

## Recurrent vs ramp boundary
Step and burst remain the recurrent measured regimes; ramp remains the prespecified boundary condition. Results are reported separately in `p8_external_strata.csv` rather than pooling selectively after outcome inspection.

## External-validity conclusion
P8 supports transfer of the **retention/reuse mechanism** and demonstrates modest realized exact-search work saving under measured microservice dynamics. It does **not** establish a robust optimization-objective advantage. This is an external boundary result, not equivalence and not a failed execution.
