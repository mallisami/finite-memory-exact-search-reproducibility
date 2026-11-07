# Reproduction guide

Run commands from the repository root.

## 1. Environment

```bash
python -m pip install -r requirements.txt
```

The runner forces the principal numerical thread-count variables to one and sets `PYTHONHASHSEED=0` for deterministic execution where applicable.

## 2. Fast verification

```bash
bash verify.sh
bash run_tests.sh
```

Equivalent commands:

```bash
PYTHONPATH=src python verify.py
PYTHONPATH=src pytest -q tests
```

## 3. Core chained rerun

```bash
bash reproduce.sh
```

Equivalent command:

```bash
PYTHONPATH=src python src/run_experiments.py all_paper2 --workers 3 --run-id FULL_RERUN
```

Fresh outputs are written only to `results/reproduced/<run-id>/`. The runner refuses to overwrite a non-empty run directory.

The core chain reruns, in order:

1. graph-development corpus generation;
2. sealed holdout generation;
3. predictor development and preblind freeze;
4. sealed holdout evaluation;
5. outcome-blind structural memory screen;
6. finite-memory residence experiment;
7. measured-workload replay;
8. leave-one-family-out transfer;
9. independent MDKP validation; and
10. result verification against the retained scientific evidence.

## 4. Individual stages

```bash
PYTHONPATH=src python src/run_experiments.py p55
PYTHONPATH=src python src/run_experiments.py p56
PYTHONPATH=src python src/run_experiments.py p6_train --workers 3
PYTHONPATH=src python src/run_experiments.py p6_blind
PYTHONPATH=src python src/run_experiments.py p7b
PYTHONPATH=src python src/run_experiments.py p7 --workers 3
PYTHONPATH=src python src/run_experiments.py p8 --workers 3
PYTHONPATH=src python src/run_experiments.py p9
PYTHONPATH=src python src/run_experiments.py p10_all
```

## 5. Rebuild publication figures from the original author-derived analysis

```bash
python src/analysis/rebuild_publication_figures.py
PYTHONPATH=src python src/analysis/rebuild_derived_diagnostics.py
```

The **first** command runs the source-derived original author figure and tabular analysis adapted for this repository. It writes Figures 2–5 and S1 in `results/reproduced/publication_figures/` and derived tables in `results/reproduced/publication_data/`. Figure 1 is frozen schematic artwork; the six authoritative final PDF files in `figures/publication/` are never overwritten. Independent local comparison found pixel-identical reproduction for all five generated figures at the tested rendering resolution. Their PDF bytes can differ in timestamps/metadata on other hosts. The **second** command regenerates auxiliary diagnostics only, in distinct `results/reproduced/` paths. Neither operation re-executes a scientific campaign. See `docs/FIGURE_BUILDER_PROVENANCE.md`.

## 6. Multi-machine timing studies

The graph and MDKP timing campaigns are not silently replayed by `reproduce.sh`. Their inference is tied to frozen schedules and recorded environments. The repository therefore retains the execution contracts and the exact recorded rows for reanalysis:

- primary graph timing: `experiments/graph_runtime/primary/` and `results/graph_runtime/primary/`;
- coefficient-scored graph timing: `experiments/graph_runtime/coefficient/` and `results/graph_runtime/coefficient/`;
- MDKP 90-case timing: `experiments/mdkp/` and `results/mdkp/timing/`.

This separation prevents a fresh run on an unrelated machine from being mistaken for reproduction of the recorded timing inference.

## November 2026 corrected-result source distinctions

Run `python verify.py` to check the preserved original curated studies and the additional corrected numerical summaries. See `docs/NOVEMBER_2026_SOURCE_ALIGNMENT.md` for explicit P8, P9, P10 estimand and sample-reuse distinctions. The complete November author archive is separate and includes the exact current figure-generation code and AWS source rows; this curated repository now includes the exact November figures (apart from the pixel-identical, metadata-sanitized Figure 1), as well as the corrected P8/P9/P10 retained evidence. It does not provide a full from-scratch recreation of historical cloud executions.
