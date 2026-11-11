# PCR2 computational evidence synchronization — 12 November 2026

## Explicit public scope

This GitHub repository contains **research code, selected computational evidence, reproducibility checks and reviewer guides only**. The unpublished main manuscript, Online Resource 1, all LaTeX, manuscript PDFs, paper figures, author metadata, and full author-side ZIP are **not** included and must not be uploaded here. Journal submission materials are kept privately by the authors.

## Public post-hoc evidence update

- [Non-manuscript offline analysis archive](../results/posthoc/PCR2_PUBLIC_OFFLINE_REPRODUCIBILITY_ONLY_20261112.zip), 77,396 bytes.
- SHA-256: `cbb58d060c9d6c7780cc47ef3a721cf2748fbdbc9d6cb60746b0d52515a3dcd4`.
- 31 archive entries: 29 scientific data, scripts and audit records, plus one inner SHA-256 file inventory and one public-scope README.
- Derived from the verified November 10 research/analysis layers of the author-retained R6 archive. The original code and numerical rows already tracked in `src/`, `data/`, `experiments/` and `results/` remain untouched.
- Exclusions: manuscript content; figures and bibliography; original multi-host receipts; instance identifiers and raw host data; duplicated solver snapshots and historical baseline CSV copies; the complete evidence/author archive.

The new archive retains original file bytes for the selected files. See `FILE_SHA256.csv` inside the ZIP to cross-check each file after extraction.

## What the update establishes

- **RQ3 development:** 73 positive rows of 1,948 training rows; 121 late no-recurrence records are a descriptive censoring sensitivity, not newly observed labels. The separately reconstructed 1,875-row diagnostic is a distinct, historical NO-GO cohort.
- **P7 component timing:** 45 matched graph cases have identical fresh-branch-pop outcomes; instrumented component sums are not total wall time.
- **MDKP VM90 timing:** direct-versus-empirical geometric wall-time ratio approximately 1.01286, with VM-stratified bootstrap interval crossing unity (0.99625–1.03293). This does not establish a policy runtime advantage.
- **External FIFO/LRU/random comparator integrity:** 945 retained run rows, 405 collapsed case/policy/budget rows, and 36 checked aggregate means were verified in the source audit. Historical wall-time equivalence and an external published-heuristic implementation were **not** established.
- **Source provenance:** the original RQ3 label-producing script was not recovered. Some offline scripts require the separately held immutable original evidence archive; the new ZIP is not a standalone rerun of the original multi-machine campaigns.

All scientific limitations, historical negative results and Path A/B NO-GO conclusions remain in force. Do not treat retrospective diagnostics as confirmatory experiments.

## Reproduce and review

1. Start with [Reviewer First Steps](REVIEWER_START_HERE.md) and [Claim-to-Evidence](CLAIM_TO_EVIDENCE.md) for data in the existing repository.
2. Extract the [public offline update ZIP](../results/posthoc/PCR2_PUBLIC_OFFLINE_REPRODUCIBILITY_ONLY_20261112.zip), verify `FILE_SHA256.csv`, and inspect `09_POSTHOC_P0_DIAGNOSTICS_20261110/PCR2_P0_DIAGNOSTICS.json` and `10_OFFLINE_COMPARATOR_AND_RQ3_RECOVERY/EXTERNAL_COMPARATOR_RETAINED_DATA_AUDIT.json`.
3. Scripts that expect a private immutable author archive cannot be run solely from this public ZIP. The original cloud VMs are gone; any new hardware measurements are a new replication.
4. For the exact public repository snapshot, cite the verified Git commit; a GitHub Release or DOI has not been asserted or created here.

**Distribution scope:** This update is supplemental *research evidence*, not a paper/supplement package or blanket code/data reuse license.
