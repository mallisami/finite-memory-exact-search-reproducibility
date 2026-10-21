# Paper 2 P7 — Confirmatory Seed Amendment

**Status: frozen before authoritative confirmatory execution.**

## Reason
A previously excluded working-directory result set was discovered for the originally proposed confirmatory seeds `3031–3045`. Its file timestamps precede the final confirmatory protocol freeze. Those seeds are therefore treated as development-contaminated and are not admissible as confirmatory evidence, even though the prior outputs are outside the reviewer-facing SSOT.

## Sole amendment
Replace the confirmatory seed block:

- superseded: `3031–3045` (15/domain)
- authoritative fresh block: **`3301–3315` (15/domain)**

All other frozen elements are unchanged:

- domains: generic, workflow, microservice;
- 45 independent cases;
- 24 nodes, 6 hosts, destroy size 12;
- 200 controller iterations/case;
- 8 deterministic branch pops/call;
- frozen P6-v1 logistic H+D model, no retraining/recalibration;
- policies: restart, empirical-compatible, learned, keep-all;
- budgets: 25%, 50%, 75%;
- primary budget: 25%;
- outcomes, comparisons, bootstrap, Wilcoxon/Holm procedures, and interpretation rules.

No outcome from seeds `3301–3315` was inspected before this amendment was frozen.
