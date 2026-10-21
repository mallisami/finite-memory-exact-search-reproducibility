# P10 Final Independent Validation — Pending Execution (Revalidated Final Freeze)

This directory contains the frozen prospective configuration for the **one final independent validation block** added after P6–P9.

No P10 scientific result is included. This is intentional: the package is execution-ready, but authoritative P10 outcomes have not been inspected or fabricated.

## What P10 adds

- unrelated optimization domain: 0–1 multidimensional knapsack;
- separately implemented serializable exact B&B repair engine;
- P10-local exact finite-byte allocator, independent of the original Paper-2 allocator;
- HiGHS exactness certificates on small and representative repair scales;
- deterministic restart/resume work-accounting verification;
- real checkpoint serialization/restoration/compatibility execution;
- nine-case-per-cell outcome-blind structural/runtime screen;
- predictor development plus 15-case sealed holdout with case-bootstrap uncertainty;
- four-policy 45-case confirmatory run;
- counterbalanced three-repeat sequential controller timing;
- deterministic search-work, wall-clock, memory, reuse, and objective endpoints;
- primary net wall-clock endpoint = restart minus learned; empirical minus learned timing is secondary;
- complete secondary memory/eviction/timing descriptives and keep-all upper-resource reference;
- fixed-byte confirmatory capacity derived only from the outcome-blind screen;
- Holm multiplicity control for formal tests across the three P10 primary endpoints;
- explicit stop rule preventing another post-result experiment loop.

See `../03_PROTOCOLS_AND_NOTES/P10_REAUDIT_REPORT.md` and `../03_PROTOCOLS_AND_NOTES/P10_FINAL_REVALIDATION_REPORT.md` for the pre-execution and final package/code-contract audits.

## One-command execution

```bash
python -m pip install -r 08_P10_FINAL_VALIDATION_PENDING/P10_REQUIREMENTS_TESTED.txt
PYTHONPATH=04_CODE python 04_CODE/run_experiments.py p10_verify
PYTHONPATH=04_CODE python 04_CODE/run_experiments.py p10_engineering
PYTHONPATH=04_CODE python 04_CODE/run_experiments.py p10_all
```

`p10_all` first reruns package verification, regression tests, and engineering certificates, then executes screen → development → sealed holdout → confirmatory in that order. Outputs go to `07_REPRODUCED_RESULTS/PAPER2_P10_INDEPENDENT_VALIDATION/`. Existing P6–P9 frozen evidence is never overwritten.

P10 remains a live optimization-controller validation, not a live DeathStarBench/microservice-SLO deployment.
