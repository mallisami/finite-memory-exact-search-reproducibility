# PCR2 public reproducibility release (7 November 2026)

This repository is the curated executable evidence subset of the full author
archive PCR2_PAPER2_FIGURES_TABLES_CORRECTED_FINAL_20261107.zip, not the
manuscript archive. It contains experiment code, test contracts, frozen
numerical inputs/results, current AWS P8, nested P9, original P10 and the
same-45-case P10 repetition, environment details, and six final figure PDFs.

## Excluded by design
Main manuscript, Online Resource 1, supplement, LaTeX source, bibliography,
author page, review letters, private host identity and credentials. Figure PDFs
are scientific outputs and are intentionally present. This public identity-
bearing GitHub repository is not a blind-review anonymous deposit.

## Reproduce
Run from repository root:

    python -m pip install -r requirements.txt
    bash verify.sh
    bash run_tests.sh
    python src/analysis/rebuild_publication_figures.py
    python src/analysis/audit_release_duplicates.py

The original author-derived publication analysis regenerates Fig2-Fig5 and FigS1 under
results/reproduced/publication_figures/ using frozen retained data and source-backed numerical checks. See docs/FIGURE_BUILDER_PROVENANCE.md. It never
overwrites frozen final publication figures and does not rerun cloud timing.
Fig1 is a frozen schematic. Identical PDF bytes are not promised across font
and rendering environments; verify.py checks frozen exact artwork hashes.
Figure 5 consumes the verified eight-row graph-runtime author-release summary
retained unchanged at figures/data/rq2_graph_runtime_figure_summary_20261107.csv.

## Source duplication classification
An exact-content audit of the November 7 repository identified 103 repeated
Git blob groups and 1,021 additional paths (about 15.46 MB uncompressed).
The main source is repeated per-state DeathStarBench inventory JSONs. Other
duplicates preserve input/output paths, model provenance and reference
snapshots. Git itself stores identical bytes in one blob. Do not delete these
paths solely based on their hashes: reproduction scripts and source history
must be checked first. A read-only duplicate report is provided.

## Evidence boundaries
November corrected AWS P8 and nested P9 supersede historical figures, but
frozen original studies remain intact. P10 repeat reuses the same 45 cases.
The core chained rerun does not replay external multi-machine timing on
new hardware as if it were the original experiment. No new scientific
outcomes or superiority claims are introduced by this repository update.
