# Paper 2 P7 — Confirmatory Execution Note

**Frozen before authoritative outcome analysis.**

The confirmatory runner originally alternated budgeted policy executions within each case (`empirical_compatible`, `learned`, then the next budget). On the execution host, repeated alternation between SciPy/HiGHS exact knapsack calls and sklearn model scoring could stall the Python process despite each replay completing normally in isolation.

The runner was therefore changed to execute the same independent replays in this order:

1. all three empirical-compatible budgets;
2. all three learned budgets.

This is an execution-only reorder. It does not change the case, trace, random variates, policy definition, exact selector, budget bytes, frozen P6 model, outcome, or inference. Each replay is reconstructed from the same deterministic case/trace and is independent of the execution order of the other policies.

A second host-specific interaction was isolated: merely loading the sklearn/joblib predictor before the empirical HiGHS allocation replays could trigger the same stall. The runner therefore defers loading the frozen predictor until the empirical-compatible replays are complete. This also changes no scientific input or output; it only delays object construction until the learned-policy block begins.
