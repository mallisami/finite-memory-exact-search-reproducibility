# Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse

**Computational reproducibility materials accompanying the research manuscript.**

**12 November 2026 — research-only synchronization:** [Offline reproducibility update](docs/PCR2_OFFLINE_EVIDENCE_SYNC_20261112.md) and [verified 77,396-byte analysis ZIP](results/posthoc/PCR2_PUBLIC_OFFLINE_REPRODUCIBILITY_ONLY_20261112.zip) add November 10 post-hoc diagnostics and source-audit receipts. This archive contains **no manuscript/supplement, LaTeX, figure artwork, author metadata, or original host records**. It is not a complete historical author archive or a published GitHub Release.


Reproducibility materials for the paper **“Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse.”**

This repository is the **curated computational reproducibility release**. It contains the implementation, retained inputs, frozen experiment definitions, raw/derived results, figure data, execution-environment records, and verification utilities needed to inspect or rerun the reported studies without exposing the internal authoring/audit directory structure used during development.

> **Public release boundary.** This identity-bearing GitHub repository contains computational materials only; the unpublished manuscript, Online Resource 1, LaTeX, author metadata and full author archive are deliberately held outside GitHub. Follow the journal's review policy when sharing the repository URL.

## Reviewer and editor entry points

- **Reviewer first steps:** [Reviewer Start Here](docs/REVIEWER_START_HERE.md), followed by the [verification matrix](docs/REPRODUCIBILITY_VERIFICATION_MATRIX.md).
- **Editor handoff:** [Editor Submission Guide](docs/EDITOR_SUBMISSION_GUIDE.md) lists the exact package scope, checks and unresolved editorial decisions.
- **Data and claims:** [Evidence index](docs/REVIEWER_EVIDENCE_INDEX.csv), [claim map](docs/CLAIM_TO_EVIDENCE.md), and [reproducibility limitations](docs/REPRODUCIBILITY_LIMITATIONS.md).
- **Citation and availability:** [Citation instructions](CITATION.md), [manuscript code/data availability text](docs/CODE_AND_DATA_AVAILABILITY.md), and [license/release status](docs/LICENSE_AND_RELEASE_STATUS.md).
- **Versioned release preparation:** [v1.0.0 release notes](RELEASE_NOTES_v1.0.0.md). A release-note file is not itself a published GitHub Release/tag.
- **Change history:** [Changelog](CHANGELOG.md). The author-side full November 7 archive is separately preserved; this repository is a curated subset, not its byte-for-byte mirror.

### Reproduction levels

| Level | Action | What it establishes |
| --- | --- | --- |
| 1. Integrity and scientific checks | `bash verify.sh && bash run_tests.sh` | Manifest and retained-data checks; regression contracts |
| 2. Rebuild figures | `python src/analysis/rebuild_publication_figures.py` | Source-derived Fig2–Fig5 and FigS1 in ignored output, without altering frozen PDFs |
| 3. Rerun deterministic core | `bash reproduce.sh` | Fresh core outputs; separate from original multi-host timing |
| 4. Historical timing | Consult recorded schedules, environment and raw rows | Reanalysis only; a fresh machine run is a new replication |

The GitHub CI runs on Python 3.11. Installing `requirements.txt` and passing CI do **not** recreate missing packet captures, original coefficient-fitting rows or the historical cloud hardware.

## Quick start

Tested dependencies are pinned in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
bash verify.sh
bash run_tests.sh
```

To rerun the core deterministic/controlled chain in a fresh output directory:

```bash
bash reproduce.sh
```

Set `WORKERS` to change the default worker count:

```bash
WORKERS=3 bash reproduce.sh
```

The core runner regenerates the graph-development corpus, sealed holdout, recurrence predictor, structural memory screen, residence experiment, measured-workload replay, cross-family transfer, and independent MDKP validation. The later multi-machine timing campaigns are retained as frozen protocols plus raw timing rows because their inference depends on the recorded machine environments and counterbalanced schedules.

## Repository layout

```text
.
├── README.md
├── requirements.txt
├── verify.py
├── verify.sh
├── run_tests.sh
├── reproduce.sh
├── src/                    # implementation, stage runners, analysis code
├── tests/                  # regression and scientific-contract tests
├── data/                   # retained study inputs and frozen core evidence
│   ├── core/
│   ├── deathstarbench/
│   └── topology_zoo/
├── experiments/            # frozen protocols, configs, schedules, run scripts
│   ├── residence/
│   ├── graph_runtime/
│   ├── mdkp/
│   ├── core_protocols/
│   └── posthoc/
├── results/                # primary, secondary, timing, and diagnostic outputs
│   ├── prediction/
│   ├── residence/
│   ├── measured_replay/
│   ├── transfer/
│   ├── graph_runtime/
│   ├── mdkp/
│   ├── posthoc/
│   └── reproduced/         # fresh reruns and diagnostic outputs (ignored runtime files)
├── figures/                # final publication PDFs and numerical figure inputs
│   ├── publication/        # exact final artwork used in the manuscript
│   └── data/               # retained/derived numeric plot inputs
├── environment/            # hardware/software/runtime records
└── docs/                   # reproduction guide, claim map, limitations
```

## Main studies

| Study | Evidence in this repository |
|---|---|
| Useful-compatible-recurrence prediction | `data/core/predictor_development/`, `data/core/predictor_holdout/`, `results/prediction/` |
| Finite-memory checkpoint residence | `data/core/residence_primary/`, `results/residence/` |
| FIFO/LRU/Random external controls | `data/core/residence_external_controls/`, `experiments/residence/external_controls/` |
| Measured DeathStarBench-derived replay | `data/deathstarbench/`, `data/core/measured_replay/`, `results/measured_replay/` |
| Cross-family predictive transfer | `data/core/cross_family_transfer/`, `results/transfer/` |
| Primary graph timing | `experiments/graph_runtime/primary/`, `results/graph_runtime/primary/` |
| Coefficient-scored graph timing | `experiments/graph_runtime/coefficient/`, `results/graph_runtime/coefficient/` |
| MDKP work/runtime study | `experiments/mdkp/`, `results/mdkp/` |
| Revision-stage sensitivity analyses | `experiments/posthoc/`, `results/posthoc/` |

See [`docs/CLAIM_TO_EVIDENCE.md`](docs/CLAIM_TO_EVIDENCE.md) for the display/claim-to-file mapping and [`docs/REPRODUCTION_GUIDE.md`](docs/REPRODUCTION_GUIDE.md) for exact commands.

## Verification

`verify.py` checks repository integrity and recomputes several headline quantities directly from the retained rows, including the held-out prediction metrics, primary residence means, measured-replay work differences, graph-timing record counts, and MDKP timing summary. It also checks that the publication directory contains only the six final manuscript figures and that no editable PowerPoint source is included.

Measured-replay diagnostic uncertainty uses application-stratified resampling of the **30 application–repetition blocks**, keeping each block's burst/step/ramp sequences together. For the objective-effect headline displayed in the auxiliary figure, the utility checks the retained rows and the frozen final 10,000-resample block-bootstrap interval (`results/mdkp/diagnostics/P8_BLOCK_BOOTSTRAP_FINAL.json`); its independent resampling may differ slightly at the reported last decimal place. This is distinct from the earlier P8 stage summary, which used 90 sequence-level resampling units and was superseded for manuscript inference.

The six PDFs in `figures/publication/` are the current November 2026 manuscript artwork. Figures 2–5 and S1 are byte-identical to the corrected author manuscript; Figure 1 is visually identical but has its embedded Content Credentials removed in this public copy. The utility `src/analysis/rebuild_derived_diagnostics.py` rebuilds derived summary tables under `results/reproduced/derived_data/` and auxiliary diagnostic plots; it does **not** regenerate these exact final publication PDFs. Diagnostic outputs are written under the ignored `results/reproduced/diagnostic_figures/` directory so they cannot be confused with publication artwork.

A SHA-256 manifest for this curated repository is stored in `MANIFEST_SHA256.csv`. The manifest covers the frozen repository files and excludes itself and generated run outputs under `results/reproduced/`.

## Site-specific timing configuration

The cluster SSH configuration and local-cluster JSON in `experiments/graph_runtime/primary/config/` are **redacted templates**, not the original machine connection information. Supply host addresses and login details only in private local copies when conducting a new timing replication. The frozen timing rows, schedules, scientific data, and environment/hardware reports are unchanged. Historical host connection coordinates are not necessary to reproduce the reported numerical analyses.

## Reproducibility boundaries

Two upstream historical inputs are not available in their original form:

1. the historical raw rows used to fit the graph pC operation-cost coefficients; and
2. the original DeathStarBench packet-capture binaries.

The fixed pC coefficients, downstream measurements, packet-capture SHA-256 identifiers, derived replay states, frozen configs, raw analysis rows, and downstream outputs used by the paper are retained. Details are in [`docs/REPRODUCIBILITY_LIMITATIONS.md`](docs/REPRODUCIBILITY_LIMITATIONS.md).

## Scope and interpretation

- Keep-all is an upper-resource reference, **not** a same-budget oracle.
- Measured replay is evidence about retained/reused search work, **not** production QoS.
- Cross-environment differences between original and coefficient-scored timing campaigns are descriptive; inferential claims use matched within-evaluation contrasts.
- Revision-stage analyses under `posthoc/` are explicitly post hoc and are not part of the prespecified primary multiplicity families.
- The editable PowerPoint used during authoring is deliberately excluded; only the final publication PDF is included, avoiding redundant editable authoring artifacts and their metadata in the public evidence repository.

## Release scope

This Git repository contains code, retained data, frozen experimental records, numerical results, six publication **figure PDFs** (research outputs), and verification guides. It does **not** contain the manuscript PDF, supplementary manuscript, LaTeX source, editor-only title page, response letters, or the author-side full archival package. The figure PDFs are retained because they are checksum-verified evidence outputs, not the paper text.

## November 2026 corrected manuscript alignment

The final author-side research ZIP has newer corrected AWS P8 and nested family-held-out P9 analyses, plus a same-case P10 repeat. The original curated data in this public repository are deliberately preserved. See [November source alignment](docs/NOVEMBER_2026_SOURCE_ALIGNMENT.md) and the additional `figures/data/*20261107.csv` files for corrected numerical summaries. The six current `figures/publication/` PDFs have now been synchronized with the corrected November paper (with Figure 1 sanitized for public distribution). The complete author-side archive still contains additional experimental and figure-generation records not duplicated here. This GitHub subset is not a replacement for that full package.


## November 7 reproducibility release verification

The current public repository is the curated code/evidence subset, not the
author manuscript package. Neither the main paper nor Online Resource 1 is
included. The frozen figures remain at `figures/publication/`.

The current P8/P9/P10 numerical evidence, release-boundary regression test,
duplicate-path inventory, and publication-data plot reconstruction are
documented at `docs/PCR2_RELEASE_REPRODUCIBILITY_20261107.md`.
To rebuild Fig2-Fig5 and FigS1 into an ignored directory without overwriting
their frozen final PDFs, run:

```bash
python src/analysis/rebuild_publication_figures.py
```

The repository's original SHA-256 verification, scientific tests and
historical timing-evidence boundaries remain in force.


## Reviewer entry point and full-release audit

Use [Reviewer Start Here](docs/REVIEWER_START_HERE.md) for the single canonical experiment navigation and [Reviewer Completeness Audit](docs/PCR2_REVIEWER_COMPLETENESS_AUDIT_20261107.md) for the author-archive-to-GitHub coverage boundary. The corrected AWS four-host RQ2 three-arm raw evidence is in [results/rq2_three_arm_aws_20261107/](results/rq2_three_arm_aws_20261107/) with source-recomputing tests. The manuscript, Online Resource 1 and author-side full historical host archives are deliberately not silently merged into this public repository. The current reviewer-facing numerical-evidence gate is a **qualified GO**, with disclosed upstream provenance boundaries. The authors have approved a versioned GitHub release; formal GitHub Release publication remains pending. A DOI is optional unless required by the journal. Public-link anonymity and specific code/data reuse licenses still require explicit venue/author decisions.

## Canonical reviewer evidence index

For one authoritative location per claim and for the full versus curated provenance boundary, see [Reviewer evidence source of truth](docs/REVIEWER_EVIDENCE_SOURCE_OF_TRUTH_20261107.md) and [Machine-readable evidence index](docs/REVIEWER_EVIDENCE_INDEX.csv).

## Source-derived author figure regeneration

The recovered author-side figure builder is now included as `src/analysis/rebuild_publication_figures.py` and `src/analysis/rebuild_Fig4_AWS_author.py`, adapted only for repository-relative inputs and a safe derived-output directory. Rebuild Figures 2–5 and S1 with `python src/analysis/rebuild_publication_figures.py`. The output matches the final artwork at the tested raster resolution; Figure 1 is a frozen schematic. See [`docs/FIGURE_BUILDER_PROVENANCE.md`](docs/FIGURE_BUILDER_PROVENANCE.md).
