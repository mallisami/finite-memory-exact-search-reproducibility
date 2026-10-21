# Paper 2 P5.6 — Selector Fairness and Final-Test Correction

## Status
**PASS — ready for P6 model fitting under the frozen P6 protocol.**

P5.6 addresses the two issues identified by the full-program audit without rerunning the expensive exact-repair experiments.

## 1. Stronger allocation baseline
P4/P5 previously used a greedy expected-value-density retention rule while the future-aware oracle solved the byte-constrained subset exactly. P5.6 separates prediction from allocation and adds an exact sparse dynamic-programming selector:

\[
\max_x \sum_i x_i\hat p_i W_i^{invested}
\quad\text{s.t.}\quad
\sum_i x_i m_i\le M.
\]

The greedy density policies remain in the tables as transparent baselines.

### Corrected P4 exact empirical recurrence baseline
Mean fraction of future-aware oracle in nonzero-headroom cases:

| Byte budget | Greedy empirical | Exact empirical |
|---|---:|---:|
| 25% | 0.514 | **0.698** |
| 50% | 0.655 | **0.690** |
| 75% | 0.768 | **0.817** |

### Corrected P5 exact empirical compatible-recurrence baseline

| Byte budget | Greedy compatible | Exact compatible |
|---|---:|---:|
| 25% | 0.517 | **0.694** |
| 50% | 0.713 | **0.794** |
| 75% | 0.858 | **0.880** |

At 50% memory, exact compatibility-aware selection captures:
- stable: **0.738** of oracle;
- stationary localized: **0.890**;
- shifted localized: **0.764**.

Thus the remaining gap is smaller but still meaningful. Future ML must beat the **exact predicted-value selector**, not only greedy cache heuristics.

## 2. No expensive solver rerun
The corrected P4/P5 tables are recomputed entirely from the already frozen candidate/label CSVs. Independent rerun of the recomputation produced byte-identical corrected outputs.

## 3. Clean P6 feature firewall
P5.5 remains unchanged for provenance. P5.6 creates a 23-feature default matrix by dropping five dead/redundant fields:
- `current_recurrent` — constant zero;
- `leaves_evaluated` — constant;
- `best_gain_at_checkpoint` — constant;
- `partial_branches_expanded` — duplicate of `invested_branch_pops`;
- `residual_opportunity` — duplicate of `additive_gap_at_checkpoint`.

Future/oracle fields remain forbidden.

## 4. Final blind holdout
Because the earlier P5.5 test partition was inspected during audit, it is no longer treated as the final blind test.

A new holdout was generated with five new seeds per domain:
`1616, 1717, 1818, 1919, 2020`.

Totals:
- 15 independent base cases;
- 225 decision events;
- 23 decision-time features;
- features and labels stored separately.

The label file is sealed. **No target prevalence or model performance was inspected.**

Seal hashes are recorded in `PAPER2_P56_BLIND_HOLDOUT/P56_BLIND_HOLDOUT_SEAL.json`.

## 5. P6 protocol frozen before training
`PAPER2_P6_FROZEN_PROTOCOL_PRETRAINING.md` fixes before model fitting:
- grouped 5-fold development procedure over the 45 P5.5 cases;
- 23-feature matrix and H/S/D ablations;
- prevalence, history-frequency, logistic, boosted-tree, and MLP hierarchy;
- hyperparameter grids;
- calibration rule;
- prediction metrics;
- exact byte-constrained selector;
- one-time blind-test release rule.

No GNN is allowed in the primary P6 run.

## Verification
- P1–P5.6 focused unit tests: **24 passed**.
- broader relevant regression: **57 passed, 1 skipped**.
- controlled-table P5.6 recomputation rerun: byte-identical outputs.
- blind holdout: generated and sealed without label-summary inspection.

## Scientific consequence
The fairness issue is now closed: later performance differences can be attributed to prediction/calibration rather than an intentionally weaker allocation heuristic. The final-test protocol is also protected from further model-selection leakage.
