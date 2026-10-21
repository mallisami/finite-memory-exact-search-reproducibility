# Paper 2 P7 — Effective Confirmatory Protocol (Consolidated)

This is the **current effective protocol**. The earlier top-level protocol plus seed/execution amendment files are retained only for provenance.

- independent domains: generic, workflow, microservice;
- fresh authoritative seeds: **3301–3315** (15/domain; 45 independent cases);
- regime: 24 nodes, 6 hosts, destroy size 12;
- 200 controller iterations/case;
- 8 deterministic exact-search branch pops/call;
- frozen P6-v1 calibrated logistic H+D predictor; no retraining/recalibration;
- policies: restart, empirical-compatible, learned, keep-all;
- byte budgets: 25%, 50%, 75% of case-specific keep-all peak valid checkpoint bytes;
- primary budget: 25%;
- primary mechanistic comparison: learned minus empirical-compatible reuse;
- primary optimization comparison: learned vs restart best-objective improvement;
- independent inferential unit: base case;
- 10,000 case-bootstrap CIs; paired Wilcoxon secondary; Holm across the frozen primary family;
- execution grouping/order changes documented in `PAPER2_P7_CONFIRMATORY_EXECUTION_NOTE.md` are operational only and do not alter any scientific input, trace, policy, or outcome.

The superseded 3031–3045 working block is **not admissible confirmatory evidence** because pre-protocol outputs existed for those seeds.
