# MDKP work-to-runtime diagnosis

This record summarizes the mechanism analysis used to interpret the controlled 90-case MDKP timing study. It is explanatory evidence, not an additional confirmatory timing campaign.

## Primary controlled result

Across 90 fresh cases executed on three VMs, the geometric paired wall-time ratio for direct marginal-work retention versus empirical-pW was 1.01286 (95% VM-stratified bootstrap CI 0.99683–1.03357). The corresponding ratio versus restart was 1.00490 (95% CI 0.97362–1.03690). The study therefore did not establish wall-clock superiority.

## Logical search work

On the same 90 cases, direct marginal-work retention versus restart had an executed-node ratio of 0.94876 (95% CI 0.91098–0.98779), while empirical-pW versus restart had a ratio of 0.94797 (95% CI 0.90682–0.98950). Direct versus empirical-pW was 1.00083 (95% CI 0.98242–1.02426). A secondary study-stratified sensitivity analysis over 150 unseen cases gave direct versus empirical-pW 0.99371 (95% CI 0.98068–1.00877).

## Why node savings do not translate directly into time savings

Instrumented re-execution shows that the cost of a branch-and-bound node depends strongly on search depth. Estimated time per node fell from 0.057 ms at depths 0–9 to 0.006 ms at depths 50–59. Thus, equal node counts can represent very different amounts of computation.

Stored checkpoints are also disproportionately difficult contexts because a checkpoint is retained only when a slice has not already satisfied the stopping target. For representative seed 2122060784, 48 of 59 resumptions re-hit the 384-node cap and only 11 retired early. Cap-hitting resumed slices therefore save little logical work while paying restoration and shallow-frontier search costs.

Among 50 cases in which direct retention and restart followed the same outer trajectory, the diagnostic regression was

    repair_time_saved_ms = -1.8819 + 0.04331 * nodes_saved - 1.7658 * resumes.

The coefficient should not be interpreted as a universal hardware-independent constant. It is a mechanism estimate for the tested implementation. In these matched-trajectory cases, direct retention executed about 2.91% fewer nodes but reduced repair time by only about 0.12% on average.

## Interpretation

The evidence separates three quantities that should not be conflated:

1. retained or reusable historical work;
2. logical search work avoided after resumption; and
3. elapsed wall-clock time.

Under the tested MDKP engine, logical work savings do not automatically yield time savings because per-node cost varies with depth and most resumptions return to hard search regions that re-hit the slice cap. A diagnostic oracle calculation places the allocator-only wall-time headroom at approximately 2.5% under the tested engine and settings. This ceiling is explanatory, not a confirmatory performance bound.

## Provenance

Numerical values in this record are derived from `MDKP_WORK_TO_RUNTIME_FINAL_ANALYSIS.json`, the completed 90-case VM timing bundle, and deterministic instrumented re-execution whose node counts reproduced the VM evidence.
