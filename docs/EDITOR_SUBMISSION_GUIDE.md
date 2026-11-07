# PCR2 Paper 2 — editor and journal submission handoff

This document describes the **available** public reproducibility deposit, not a venue-specific acceptance certificate. Confirm the journal's code, data, citation, license, archival, and peer-review requirements separately.

## Two different deliverables

| Deliverable | Where | Contents and authority |
| --- | --- | --- |
| Reviewer code and evidence | This GitHub repository | Runnable core, retained public numerical evidence, frozen protocols, six final figure PDFs, verification scripts and claim index |
| Full author-side November 7 archive | `PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip`, held separately by authors | 50,609,135-byte full research/manuscript package; SHA-256 `5e826e0112e5b17cba5703fa5e8df3abbbbd06aa7ff98ae2744e76d4e384fc01`; 7,972 file hashes reported and independently checked |
| Main paper and Online Resource 1 | Submit through the journal portal as requested | Current November 7 clean 35-page manuscript and 24-page Online Resource 1; intentionally not deposited in this repository |

**Do not describe GitHub as a byte-complete mirror of the author ZIP.** The author-side archive has original historical host provenance outside this public curated subset.

## What editors and reviewers can verify

1. Run `bash verify.sh` and `bash run_tests.sh` under Python 3.11 after `pip install -r requirements.txt`.
2. Regenerate the five data-driven publication figures with `python src/analysis/rebuild_publication_figures.py`; Figure 1 is a frozen schematic.
3. Follow `docs/REVIEWER_EVIDENCE_INDEX.csv` to the authoritative source for each claim. Previous pre-AWS P8 and fixed-specification P9 records are historical, not current paper estimates.
4. Distinguish original P10's **45 cases** from the same-45-case repetition; distinguish optimized learned/direct scoring from the empirical-compatible comparator; retain negative/uncertain official RQ3 outcomes.
5. Consult `docs/REPRODUCIBILITY_LIMITATIONS.md` and `docs/REVIEWER_EVIDENCE_SOURCE_OF_TRUTH_20261107.md` for irrecoverable historical inputs and non-deposited original host records.

## Editorial decisions that are not silently closed

- **Anonymous review:** The current paper PDF says *Anonymous submission*; this public repository and its owner are identity-bearing, and existing documentation had previously called the submission non-anonymous. Obtain a venue-specific decision before supplying this public URL to reviewers. If the journal requires anonymous code review, use an editor-approved anonymized deposit rather than claiming this URL is anonymous.
- **Licensing:** No explicit code/data license is present. The authors must approve a license after reviewing ownership and third-party input rights; see `docs/LICENSE_AND_RELEASE_STATUS.md`.
- **Permanent citation:** No DOI or archival snapshot is asserted. The editor/authors should determine the required Zenodo or institutional archive, tag, version, and bibliographic metadata.
- **Historical provenance:** Original packet-capture binaries and graph coefficient-fitting raw rows are unavailable; some original host archives stay author-side. A fresh cloud rerun is replication, not byte-identical reconstruction.
- **Editorial artifacts:** Cover letter, author contribution/ethics statements, declarations, title page and reviewer responses belong in the journal system when required; this repository does not fabricate them.

## Release identity and safeguards

The frozen evidence remains governed by `MANIFEST_SHA256.csv` and CI. Documentation-only revisions must update the manifest, rerun tests, and reference the tested Git commit. Do not overwrite experimental rows, reclassify historical results or assert method superiority. The final manuscript citation should point to an immutable reviewed commit/tag/release once the editor authorizes the exposure and the authors freeze it.
