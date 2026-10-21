# Execution-environment provenance boundary

The manuscript reports two environment records with different provenance.

## Exact-search software/process environment

`EXACT_SEARCH_PROCESS_ENV_CAPTURE.txt` is the process-visible capture preserved in the original PCR archive and is the source of the reported Linux `6.8.0-1064-azure`, AMD EPYC 7452, Python 3.12.15, HiGHS 1.15.1, one visible logical CPU, and single-thread numerical-library settings. The original capture is dated 2026-10-03 and records the software/process environment, including `pip freeze`.

The final P7/P8 CSV result files do not themselves embed a fresh hostname/kernel snapshot. Therefore this package does **not** claim that the text file is a per-result-file P7/P8 execution log. It is retained because the manuscript reports these environment details and because it is the available frozen process-level provenance record for the exact-search software stack. Absolute wall-clock overhead remains environment dependent; deterministic branch pops are the primary work measure.

## DeathStarBench measurement environment

The measured-input campaign has its own direct environment capture under:

`02_Authoritative_Experimental_Evidence/09_Supporting_Data/DeathStarBench_Measured_Inputs/environment/`

including the DeathStarBench commit, git status, host preflight, tool versions, and `PIP_FREEZE.txt`. These files are the authoritative provenance for measured-state preparation.
