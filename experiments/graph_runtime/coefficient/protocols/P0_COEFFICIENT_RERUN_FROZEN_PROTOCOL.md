# P0 Coefficient-Only Graph Timing Rerun — Frozen 7-Core + Full Isolated Confirmation Protocol

## Scientific purpose
The reviewer concern is that the original learned-policy wall-time disadvantage may have been dominated by avoidable per-decision pandas/scikit-learn inference overhead. The frozen fitted logistic + Platt model has an algebraically equivalent coefficient-only implementation. This protocol reruns the graph timing study with that scorer while preserving cases, traces, budgets, opportunity levels, policies, compute weights, and search logic.

## Two-phase execution
### Phase A — full-regime 7-core campaign (supporting)
VM-A and VM-B each run three disjoint CPU-pinned lanes on logical CPUs 0, 1, and 2. VM-C runs one pinned lane on CPU 0. One vCPU remains free on every VM. Across the three VMs, seven timed processes can run concurrently. The primary A/B lanes collectively cover all 60 primary cases, L1-L4, all five policies, and all five repeats.

### Phase B — full isolated L1-L4 rerun (authoritative P0 inference)
After all three local Phase-A lanes finish, each primary VM waits at least 300 s, re-passes low-load preflight, performs a non-sample warm-up, and reruns its complete original 3,000-row schedule with a single process pinned to CPU 0. Across VM-A and VM-B, Phase B therefore contains 6,000 isolated observations: the same 60 cases, four opportunity levels, five policies, and five repeats as the original graph timing campaign.

This full isolated rerun is the reviewer-facing result. Relative to the original repeated timing design, the intended scientific implementation change is the learned-policy scorer. VM-C remains descriptive robustness evidence and is never pooled into primary inference.

## Frozen design
Opportunity levels remain L1=8, L2=16, L3=32, and L4=64. Per-case/level byte budgets, graph compute weights, 200-iteration replay traces, five policy definitions, original A/B case-to-machine assignment, and five-repeat cyclic policy counterbalancing are unchanged.

Phase-A lane allocation changes only which pinned process on the same original VM executes a case. Every case remains wholly within one lane. Lane assignment was frozen using only historical original-campaign runtime to balance expected duration and family composition. No coefficient-only outcome was available when the assignment was constructed. Phase B uses the original A/B schedules directly and therefore preserves their row order as well as their case assignment and counterbalancing.

## Hardware roles
- **VM-A:** exactly 4 logical CPUs / nominal 16 GB RAM. Phase A uses CPUs 0,1,2; CPU 3 is reserved. Phase B uses only CPU 0.
- **VM-B:** exactly 4 logical CPUs / nominal 16 GB RAM. Same layout.
- **VM-C:** exactly 2 logical CPUs / nominal 8 GB RAM. Phase A uses CPU 0; CPU 1 is reserved. Descriptive only.

Primary Azure VMs must not be burstable B-series instances.

## Scorer-equivalence gate
Before timing, `verify_coefficient_equivalence.py` must pass all retained held-out feature rows at maximum absolute probability error <1e-12 and must pass development-case trajectory/counter equivalence. Any failure aborts execution.

## Primary estimands
The independent inferential unit is the **case**. Within each case-level-policy cell, five repeats are reduced to the median wall time. For each case, the four level-specific log learned/empirical ratios are averaged to obtain one case-level L1-L4 summary. Two prespecified primary contrasts are then evaluated:

1. overall L1-L4 `learned_pW / empirical_pW`;
2. overall L1-L4 `learned_pC / empirical_pC`.

Inference uses a 10,000-resample case bootstrap stratified by physical VM × family. Two-sided Wilcoxon signed-rank tests on the case-level aggregated log ratios are Holm-adjusted across the two primary contrasts. Ratio <1 favors learned; ratio >1 favors empirical. No practical-equivalence margin is prespecified, so an interval spanning 1 is interpreted as unresolved.

The eight level-specific learned-versus-empirical ratios (pW and pC at L1-L4) are reported as prespecified secondary effect estimates with 95% stratified bootstrap intervals. Phase-A L1-L4 results are supporting only and use lane-aware stratification. VM-C is descriptive only.

## Integrity rules
- Do not modify schedules, models, source, budgets, or levels after timing starts.
- Do not selectively rerun successful observations after seeing outcomes.
- `--resume` is only for technical interruption recovery. Successful run IDs are skipped; failed attempts remain in the append-only WAL.
- New runs must reproduce the original campaign trajectory hashes and non-timing scientific counters. Any mismatch is a hard analysis failure.
- Numerical-library thread counts remain one per process.
- Keep one vCPU free on each VM during Phase A.
- Quiesce timing services and pass preflight before Phase A; re-pass preflight after the cooldown before Phase B.
- Do not pool Phase-A concurrent wall times with Phase-B isolated wall times in primary inference.
- Do not inspect Phase-A timing outcomes before Phase B completes.
