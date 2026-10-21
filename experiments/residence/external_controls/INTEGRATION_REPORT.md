# PCR2 RQ1 external-comparator integration report

## Scientific scope
- Integrated the completed checkpoint-level FIFO/LRU/Random Replacement experiment into RQ1 only.
- Primary main-paper result: learned 0.9121 vs strongest external LRU 0.7574 at 25% memory; paired difference +0.1547, 95% CI [0.1120, 0.2002], 42/3/0 better/worse/tied cases.
- FIFO and Random primary comparisons are also shown in main Table 5.
- Complete 25/50/75% external-policy sensitivity is in Supplementary Section S4.2.
- RQ2 and RQ3 numerical results and conclusions were not revised.

## Method additions
- Explicitly defines checkpoint-level adaptations of FIFO, LRU, and Random Replacement from Medema et al. (2024).
- Same 45 RQ1 cases, byte budgets, checkpoint stream, exact-repair engine, and compatibility semantics.
- Random Replacement uses five frozen repetitions per case-budget; repetitions are averaged within case before paired inference.

## Reproducibility additions
- Frozen external-comparator protocol and SHA-256 hashes.
- 945/945 completed raw executions and task manifest.
- Complete case-level/aggregate analysis outputs.
- Comparator source and regression tests.
- Exact-equivalence documentation for the accelerated execution path; timing counters from accelerated runs excluded from RQ1 inference.
