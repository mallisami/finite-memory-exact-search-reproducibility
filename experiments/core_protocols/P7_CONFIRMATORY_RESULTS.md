# Paper 2 P7 — Confirmatory Online Persistence Results

## Status
**Complete on the fresh confirmatory seed block 3301–3315 (15/domain; 45 independent cases).**

The originally proposed 3031–3045 block was excluded before authoritative execution because pre-protocol working outputs existed. The seed amendment is preserved in `PAPER2_P7_CONFIRMATORY_SEED_AMENDMENT.md`.

## Frozen regime
- 24 nodes / 6 hosts;
- destroy size 12;
- 200 repair decisions/case;
- 8 deterministic branch pops/call;
- frozen P6-v1 calibrated logistic H+D predictor, no retraining/recalibration;
- exact byte-constrained selector;
- primary budget 25%, secondary 50% and 75%.

## Primary 25% mechanistic result
The frozen learned policy captured a larger fraction of keep-all reusable prior search work than the exact empirical-compatible comparator:

- learned mean reuse fraction: **0.9121**;
- empirical-compatible mean reuse fraction: **0.8242**;
- paired mean difference: **+0.08798**;
- 95% case-bootstrap CI: **[+0.06313, +0.11308]**;
- positive/negative/tied cases: **41 / 4 / 0**;
- Holm-adjusted one-sided Wilcoxon p: **1.15e-08**.

The result therefore supports the narrow claim that the frozen predictor improves finite-byte retention of later reusable exact-search state in the selected multi-state regime.

## Optimization result
There was **no best-objective or anytime separation** among restart, empirical-compatible, learned, or keep-all in the 45 confirmatory cases:

- learned better than restart: **0/45**;
- learned worse than restart: **0/45**;
- all 45 were ties for best-objective improvement;
- learned-vs-restart mean and median relative best-objective improvement: **0**;
- learned-vs-empirical best-objective and anytime differences: **0**;
- keep-all-vs-restart best-objective difference: **0 in all 45 cases**.

This is a confirmatory boundary result: better checkpoint retention did **not** translate into better optimization quality in this fixed 8-pop online regime.

## Executed-work result
Although the policies reused large amounts of previously explored search state, actual newly executed branch-pop reduction was negligible in P7:

- restart: 1600 branch pops/case by design;
- learned/empirical/keep-all: mean 1599.78, median 1600;
- mean newly executed branch pops saved vs restart: **0.22**, median **0**.

Therefore `reused_prior_branch_pops` must not be described as equivalent to realized compute saving in this regime.

## Overhead
At 25% capacity, median measured persistence/scoring overhead over the 200-decision run was approximately:

- empirical-compatible: **189 ms**;
- learned: **733 ms**.

The learned overhead is dominated by the Python/sklearn deployment path and is reported as implementation overhead, not an intrinsic cost of a linear score.

## Scientific interpretation
P7 establishes:
1. genuine multi-state online persistence pressure;
2. significant learned-vs-empirical retention advantage;
3. no corresponding optimization-quality benefit under the frozen slice regime;
4. no material realized branch-pop reduction despite large reused-state accounting.

Accordingly, the manuscript must separate **retention accuracy**, **reused historical state**, **new compute avoided**, and **optimization outcome**.
