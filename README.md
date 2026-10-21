# Finite-Memory Retention of Interrupted Exact-Search Checkpoints

Reproducibility materials for the paper **“Finite-Memory Retention of Interrupted Exact-Search Checkpoints: Predictive Selection with Compatibility-Gated Reuse.”**

This repository is the **curated computational reproducibility release**. It contains the implementation, retained inputs, frozen experiment definitions, raw/derived results, figure data, execution-environment records, and verification utilities needed to inspect or rerun the reported studies without exposing the internal authoring/audit directory structure used during development.

> **Review access.** During double-blind review, share this source and evidence only through a review-safe, anonymized location. A repository directly linked to an identifiable account does not itself preserve anonymity.

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

The six PDFs in `figures/publication/` are the exact final artwork files used by the manuscript package. The utility `src/analysis/rebuild_derived_diagnostics.py` rebuilds derived summary tables under `results/reproduced/derived_data/` and auxiliary diagnostic plots; it does **not** regenerate these exact final publication PDFs. Diagnostic outputs are written under the ignored `results/reproduced/diagnostic_figures/` directory so they cannot be confused with publication artwork.

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
- The editable PowerPoint used during authoring is deliberately excluded; only the final publication PDF is included, avoiding identity-bearing Office metadata in a double-blind review package.

## Release scope

This Git repository contains code, retained data, frozen experimental records, numerical results, six publication **figure PDFs** (research outputs), and verification guides. It does **not** contain the manuscript PDF, supplementary manuscript, LaTeX source, editor-only title page, response letters, or the author-side full archival package. The figure PDFs are retained because they are checksum-verified evidence outputs, not the paper text.
