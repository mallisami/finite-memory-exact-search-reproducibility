# Known Protocol / Provenance Deviations

These items were identified after the V4 campaign and are documented rather than hidden or repaired by new outcome-driven experimentation.

1. **Profiling phase not executed before unblinding.** The frozen profiling subset exists, but `12_profiling/` contains no run outputs and the autonomous orchestrator implementation does not execute the profiling phase despite its docstring. Primary RQ2/RQ3 inference does not depend on profiling. Do not make profiling-bucket claims from V4.

2. **Timing-preflight/quiescence output is not preserved in the archive.** Inventory shows the pre-quiescence service state and the scripts are supplied, but no machine-readable PASS log from `strict_timing_preflight.py` or `quiesce_for_timing.sh` was found. Therefore the archive cannot independently prove that every timing-isolation check was executed, even though repeat timing variability is low and the primary design counterbalances run order.

3. **Pre-confirmation freeze manifest is incomplete as a cryptographic source seal.** It binds the protocol, configs, analysis script, calibration summaries, and key scripts, but not all extension/runner files. The pC engine source timestamps predate seed generation, whereas `scripts/run_primary_confirmatory_shard.py` has a timestamp after the pre-confirmation manifest and after seed generation but before timed execution. No evidence shows outcome-driven modification, but the paper/package must not claim a perfect pre-seed cryptographic freeze of every executable file.

4. **Original outer campaign checksum ledger is stale for `scripts/assign_roles.py`.** The final audited package regenerates checksums and is internally consistent. This is a packaging-integrity defect, not evidence that the scientific results changed.

5. **Raw calibration sample rows were not retained.** Calibration/validation summaries, frozen integer weights, gate metrics, and cross-machine replay hashes are preserved, but the raw timing/counter sample table used for NNLS is absent. Reproduction therefore requires rerunning the documented development calibration rather than replaying a stored calibration table.

These deviations do not justify rerunning the valid 8,000 primary and 600 secondary timed runs merely to obtain a more favorable result. They constrain what can be claimed about protocol execution and reproducibility.
