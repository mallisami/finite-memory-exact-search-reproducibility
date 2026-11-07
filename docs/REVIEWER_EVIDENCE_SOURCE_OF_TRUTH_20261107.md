# Reviewer evidence source of truth — PCR2 Paper 2 (7 November 2026)

## Canonical release decision

The **only public reviewer-facing code-and-evidence repository** is this GitHub repository. The author-side archive `PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip` is a preserved provenance/master archive, **not** a second reviewer code repository. The study is **not anonymous**; the public GitHub URL may identify authors. The main manuscript and Online Resource 1 must remain outside this GitHub repository.

Use `docs/REVIEWER_EVIDENCE_INDEX.csv` as the machine-readable claim-to-source matrix. Every current claim has one authoritative input location. Raw values under historical or development subfolders have their own distinct estimands; do not silently combine them with the current analysis.

## Reproduction commands

```bash
python -m pip install -r requirements.txt
bash verify.sh
bash run_tests.sh
python src/analysis/rebuild_publication_figures.py
```

For deterministic core reruns use `bash reproduce.sh`. The principal frozen source and release scripts reject destructive result-directory overwrites. Machine-dependent graph/MDKP/RQ2 original runtime results are *reanalyzed from saved records*; running those timing campaigns on new hardware creates replication evidence, not byte-identical reruns.

## Distinctions reviewers must retain

- **P8** current: corrected AWS 90-sequence records and 30 application-repetition blocks; pre-AWS P8 is historical. The learned-minus-empirical saved-work contrast is small and accompanied by substantial learned evaluation overhead. Do not assert overall runtime superiority.
- **P9** current: nested family-held-out; the fixed-specification P9 source is historical.
- **P10**: 45 original cases plus a same-case repeat of those identities. Never report 90 independent confirmation cases.
- **RQ2 four-host three-arm**: source rows and atomic medians are retained with stable public host labels. Faster direct scoring than the original learned implementation is not proof of superiority versus empirical-compatible.
- **RQ3**: official VM90 inference is negative/uncertain; corrected-label and CPU diagnostic studies were rejected (NO-GO). No corrected method was adopted.
- **Figures**: six frozen final PDFs live under `figures/publication/`. Figure 1 is a schematic. The data-plot rebuild writes under `results/reproduced/` and does not overwrite final artwork.

## Scope and remaining provenance boundary

The current repository retains the recorded numerical evidence and source/verification contracts for the principal claim families, including original P10 executed source. The original author archive additionally contains approximately 1,037 original AWS host-record files (about 516.7 MB uncompressed), three recovered original P0 host-timing tarballs, the original P10 execution-time manifest, and various historical forensic logs. They are **not** all published here. Raw host archives can include infrastructure addresses or machine-local paths; the public RQ2 scientific rows were pseudonymized without altering measured values.

Thus the public repository is a *single reviewer navigation and reanalysis source*, but not yet a byte-complete archive of every historic VM execution record. No claim of complete from-scratch reconstruction of the original AWS host captures or missing DeathStarBench packet captures is made. The original P0 coefficient fitting rows are also historically absent (see `docs/REPRODUCIBILITY_LIMITATIONS.md`). This explicit boundary is preferable to duplicating the author package inside GitHub and misleading readers about what can be reconstructed.

## Content duplication policy

Repeated per-state `inventory.json` files and deliberate retained `data/` versus `results/` aliases are not independent experiments. Git stores byte-identical blobs once. The read-only `src/analysis/audit_release_duplicates.py` reports path repetition; deletion requires proven path compatibility and independent tests. No evidence will be discarded merely to obtain a zero-duplicate count.

## Authority and closure gate

The source matrix and existing tests guard the reported analysis. Separate independent publication-figure source reconciliation remains necessary before claiming a full original-author-source port into GitHub; current `src/analysis/rebuild_publication_figures.py` is the curated data-to-plot implementation. The original repaired author builder was independently recovered and tested against the author package (five regenerated figures matched the final PDF rendering pixel-for-pixel locally). Only after that builder is migrated and verified in GitHub should the stronger byte/visual reproduction claim be made for this public repository.

This repository is a transparent, frozen-evidence reproduction resource, not an assertion of positive optimization effects or fully independent physical experiments.
