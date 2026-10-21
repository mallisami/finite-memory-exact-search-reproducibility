# P10 Final Package Revalidation Report

**Status:** completed before authoritative P10 execution.

This report is a package/code-contract audit, not a scientific result. No authoritative P10 screen, holdout, or confirmatory identity was executed to produce a manuscript claim.

## Additional issues found in the final revalidation

1. **Primary wall-clock contrast was pointed at learned vs empirical rather than net learned vs restart.** Corrected: restart-minus-learned median controller time is now the primary wall-clock endpoint; empirical-minus-learned time remains secondary.
2. **Secondary endpoints promised in the frozen configuration were present in raw counters but not emitted by the analysis.** Corrected: the inference CSV and new policy-descriptive CSV now report useful resumes, byte-time/peak bytes, evictions, timing components, objective comparisons, and keep-all policy-level reference summaries.
3. **P10 still imported the original Paper-2 byte allocator.** Corrected: P10 now owns `independent_mdkp/allocation.py`; wide pools request `mip_rel_gap=0.0`, and a regression test checks the wide-pool objective against brute force.
4. **The execution seal bound the config and results but not the code actually executed.** Corrected: the seal now records SHA-256 hashes for the P10 execution script, core, controller, model, allocator, environment, package manifest, and confirmatory results.
5. **Standalone dependency pins did not match the environment used for testing and included an unused `highspy` dependency.** Corrected: `requirements.txt` now matches the exact tested environment and removes unused `highspy`.
6. **Confirmatory execution could be launched without completing the sealed holdout stage.** Corrected: confirmatory execution now requires the holdout marker.
7. **The standalone archive had a manifest but no executable manifest verifier.** Corrected: `run_p10.py verify` validates hashes, dependency pins, seed/feature firewalls, the wall-clock estimand, and local allocator independence; `run_p10.py all` reruns verify + tests + engineering before authoritative stages.

## Validation performed after corrections

- Python syntax compilation for all P10 modules/scripts;
- 9/9 standalone P10 regression tests;
- 12/12 representative engineering certificates, including restart-minus-resume node identity and HiGHS optimum agreement;
- complete non-authoritative screen → development → holdout → four-policy confirmatory → inference smoke run using identities outside every authoritative seed block;
- output-contract inspection confirming all 12 inferential rows, keep-all policy descriptives, timing components, and strengthened execution-seal fields;
- full-package verifier and regression suite after synchronization;
- byte-for-byte comparison confirming that the original P5.5–P9 frozen-evidence tree remains unchanged.

## Remaining deliberate boundaries

- P10 is not yet scientific evidence until the authoritative frozen run is executed.
- P10 is a live optimization-controller experiment, not a production DeathStarBench/SLO deployment.
- The P10 probability model is retrained on MDKP development cases; the experiment tests transfer of the persistence architecture, not zero-shot transfer of P6 coefficients.
- A null wall-clock, work-saving, or objective result after authoritative execution is retained; it does not trigger P11 outcome shopping.
