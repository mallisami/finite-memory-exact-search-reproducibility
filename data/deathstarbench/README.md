# E-DSB measured dynamic validation — frozen result summary

This directory contains the complete completed primary E-DSB result tree integrated from the Azure run.
The result archive was unpacked rather than nested as another archive so every evidence file is directly hashable.

## Campaign completeness

- 3 DeathStarBench applications: Social Network, Hotel Reservation, Media Microservices.
- 3 regimes: step, burst, ramp.
- 10 repetitions per application-regime cell.
- 90 complete measured sequences and 900 measured workload states.
- Construct-validation gate: **PASS** (99.67% good states).
- Solver run verification: **PASS** (90 sequences).

## Confirmatory contrasts

### H1 — persistent PCR vs reset PCR

- mean paired difference: `-6.36887404622e-07`;
- 95% stratified-bootstrap CI: [`-2.23553538578e-06`, `5.38272319e-07`];
- Holm-adjusted p: `0.875161506567`;
- persistent better: 14/60; ties: 24.

**Interpretation:** unresolved at this sample size; not evidence of equivalence and not evidence of a
persistence-specific anytime-quality advantage.

### H2 — persistent PCR vs matched ALNS+HiGHS

- mean paired difference: `-0.0256366952336`;
- 95% stratified-bootstrap CI: [`-0.0382232371274`, `-0.0145027002583`];
- Holm-adjusted p: `4.80774300489e-08`;
- persistent better: 51/60.

Negative differences favor persistent PCR under the frozen endpoint definition.

## Mechanism and operating boundary

- recurrent-regime mean compatible-checkpoint fraction: `0.603225`;
- recurrent-regime mean cross-state resumed calls: `0.483333`;
- recurrent-regime mean discarded-expansion saving: `10.400000`;
- exploratory Spearman compatibility-vs-anytime-gain rho: `-0.147422` (`p=0.26099`);
- ramp mean compatible-checkpoint fraction: `0.018350`.

The canonicalized repeated profile states were derived prospectively from measured DeathStarBench communication;
raw occurrence matrices are retained for construct validation. The campaign is a shadow replay: solver placements
were not redeployed into the live benchmark, so this evidence does not claim live migration latency or production
application-SLO improvement.

## Directory map

- `environment/`: host, tool, Python-package, DeathStarBench commit, and image provenance.
- `measurement/`: raw per-state wrk, packet-derived edges, container statistics, inventories, calibration, and lifecycle logs.
- `prepared/`: frozen hash-verified solver inputs, fixed demands, sequence manifest, and construct-validation outputs.
- `solver/`: complete three-arm per-sequence state, transition, anytime, and workflow summaries.
- `analysis/`: paired contrasts, mechanism tables, statistical JSON, candidate figures, and generated prose snippets.
- `logs/`, `stages/`, `RUN_VERIFICATION.json`: execution provenance and completion checks.
