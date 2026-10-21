# Paper 2 P5.6 — Fair Selector + Final-Test Protocol Correction

## Status
**Frozen pre-P6 correction gate.** P5.6 changes neither the PCR base evidence nor the P4/P5 checkpoint/label generation.

## C1 — Separate prediction from allocation
For each checkpoint `i`, a pre-decision estimator supplies expected reusable work

\[
\hat v_i = \hat p_i^{use} W_i^{invested}.
\]

The primary finite-budget allocation layer now solves

\[
\max_x \sum_i x_i\hat v_i
\qquad \text{s.t.}\qquad
\sum_i x_i m_i\le M,\quad x_i\in\{0,1\}.
\]

The implementation uses an exact sparse dynamic program with deterministic ties. The old greedy value-density policy remains a transparent comparator but is no longer the strongest empirical allocation baseline.

## C2 — Controlled evidence correction
P4 and P5 are recomputed from their already-frozen candidate/label tables. No exact-repair generation is rerun.

New P4 policy:
- `empirical_value_exact`

New P5 policies:
- `empirical_recurrence_value_exact`
- `empirical_compatible_value_exact`

## C3 — Clean P6 feature firewall
P5.5 remains frozen for provenance. P6 uses a 23-feature amendment that removes five dead/redundant fields:
- `current_recurrent` (constant zero in ordinary-controller mode);
- `leaves_evaluated` (constant in the frozen corpus);
- `best_gain_at_checkpoint` (constant in the frozen corpus);
- `partial_branches_expanded` (exact duplicate of `invested_branch_pops`);
- `residual_opportunity` (exact duplicate of `additive_gap_at_checkpoint`).

Future/outcome/oracle fields remain prohibited.

## C4 — Blind final holdout
The earlier P5.5 test partition is reclassified as a development/audit holdout because it was inspected during the full-program audit.

A new sealed final holdout uses 5 new seeds/domain:

`1616, 1717, 1818, 1919, 2020`

for generic, workflow, and microservice domains: 15 independent cases total.

The holdout generator writes:
- decision-time features;
- future labels in a separate `SEALED` file;
- case metadata;
- SHA-256 seal manifest.

No target prevalence, model score, or label summary may be inspected before the P6 model and calibration protocol is frozen.

## Interpretation boundary
P5.6 is a fairness/test-protocol correction. It is not an ML result and is not an online-controller performance result.
