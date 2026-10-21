# P10 Pre-execution Validation Report — Re-audited

This report records **engineering-only** checks. No values below are scientific P10 results and none use authoritative screen, sealed-holdout, or confirmatory identities.

## Re-audit findings corrected before execution

The re-audit identified and corrected issues that could otherwise weaken a high-impact wall-clock/generalization claim:

1. **Timing-order bias:** fixed policy order was replaced by deterministic 4×4 Latin-square counterbalancing with interleaved repeats and a non-authoritative warm-up.
2. **Screen stability:** the screen was expanded from 3 to **9 independent cases per candidate cell**, with cell order rotated/interleaved across seeds.
3. **Predictor firewall:** the synthetic hot/warm/cold generator label `current_context_class` was removed from the learned feature contract.
4. **Work-accounting validity:** engineering tests now verify restart-minus-resume exact-node identity, not only optimum equality.
5. **Exactness breadth:** HiGHS certificates now include representative P10 repair scales, not only small repairs.
6. **Nested holdout inference:** P10 holdout metrics now include independent-case bootstrap intervals and simple prediction baselines.
7. **Primary multiplicity:** formal rank tests, if reported, are Holm-adjusted across the three P10 primary contrasts.
8. **Timing reproducibility:** thread caps, environment capture, timing scope, and counterbalanced execution positions are recorded.
9. **Output preservation:** existing authoritative stage outputs cannot be silently overwritten.
10. **Package hygiene:** runtime `__pycache__` and pytest-cache artifacts are excluded from the final release.

## Engineering checks required/passed on non-authoritative cases

- custom serializable MDKP B&B optimum matches SciPy/HiGHS MILP;
- interrupted/serialized/restored exact completion matches uninterrupted completion;
- restart-minus-resume new-node difference equals invested checkpoint nodes under compatible deterministic repeat semantics;
- outside residual-capacity changes invalidate stale checkpoints;
- complete screen → development → holdout → four-policy confirmatory → paired-inference code paths smoke-test on non-authoritative identities;
- optimized NumPy scoring is algebraically equivalent to the scikit-learn StandardScaler + logistic + Platt path;
- regression tests cover the new feature firewall, representative-scale exactness, work identity, serialization, compatibility, and live-controller behavior.

## Remaining scope boundary

P10 supplies an unrelated optimization problem, independent exact-search implementation, real checkpoint execution, and live controller timing. It **does not** become a live DeathStarBench/microservice-SLO deployment. That limitation must remain explicit after P10, regardless of its outcome.

## Final revalidation additions

A second package/code-contract audit found and corrected four additional issues before authoritative execution:

1. the primary wall-clock estimand is now restart minus learned, directly testing net wall-clock benefit; empirical minus learned timing remains secondary;
2. all secondary endpoints promised by the frozen configuration are now emitted, including policy-level memory/eviction/timing descriptives and the keep-all upper-resource reference;
3. P10 now uses a local exact byte allocator rather than importing the original Paper-2 allocation module, with zero requested MIP relative gap for wide portfolios and dedicated regression coverage;
4. the execution seal now hashes the actual P10 source files and pre-execution package manifest in addition to configuration, environment, and results.

The standalone dependency pins were also aligned to the environment actually used for this validation, and the unused `highspy` dependency was removed.
