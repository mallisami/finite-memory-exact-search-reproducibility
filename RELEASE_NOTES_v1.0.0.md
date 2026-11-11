# Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse

## Reproducibility Release v1.0.0 — publication notes

**Publication state:** The authors approve this versioned GitHub release. These notes are ready to paste into a formal release, but the `v1.0.0` Git tag and GitHub Release are **not published yet**. This file alone is not a release.

This curated computational release accompanies the manuscript and contains implementation and matched controls; retained processed inputs; frozen configuration and measurement protocols; recorded case-level results and analyses; six final publication figure PDFs; original-author-derived figure rebuild scripts for Fig2–Fig5 and FigS1; SHA-256 integrity verification; and the reviewer/evidence crosswalk.

### Quick verification

```bash
python -m pip install -r requirements.txt
bash verify.sh
bash run_tests.sh
python src/analysis/rebuild_publication_figures.py
```

The optional core rerun uses `bash reproduce.sh` to generate new outputs. Original physical multi-host timings are not recreated by this command.

### Essential evidence boundaries

- Current P8 is corrected AWS replay; current P9 is nested family-held-out, not the older historical analyses.
- Original P10 and its repeat reuse the **same 45 cases**, not 90 independent cases.
- Optimized learned scoring improves overhead versus the original learned implementation but does not prove better elapsed time than empirical-compatible policy.
- Official RQ3 VM90 remains negative/uncertain; development-only RQ3 correction attempts remain rejected.
- Original graph pC coefficient-fitting rows and initial DeathStarBench packet captures are unavailable. Historical host archives and the manuscript/supplement are kept in the separate author-side package, not all replicated here.
- The public GitHub link is identity-bearing; comply with the journal's anonymity policy.
- No DOI is necessary unless required by the journal. No unselected code/data license is implied by public visibility.

### Publish this version

After final `main` CI succeeds, create a release tag `v1.0.0` **on that tested commit**, set the public title to **Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse — Reproducibility Release v1.0.0**, and publish as a normal GitHub Release (not prerelease). This step must be confirmed on the GitHub Release page; do not merely assume this release exists because these notes or a version label have been committed.


### November 12 research-only synchronization (pre-release)

The repository now also contains a separate checked 77,396-byte [offline analysis update ZIP](results/posthoc/PCR2_PUBLIC_OFFLINE_REPRODUCIBILITY_ONLY_20261112.zip) and [verification/claim-boundary guide](docs/PCR2_OFFLINE_EVIDENCE_SYNC_20261112.md). This is **not** the manuscript, Online Resource 1, editable paper source, full historical author archive, or a GitHub Release asset. Preserve the original negative experiments and previous frozen results; no new performance claim follows from the post-hoc outputs. A release tag must refer to a tested commit and must not be treated as published before it actually exists.
