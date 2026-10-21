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

## 5. Rebuild derived summaries and diagnostic figures

```bash
PYTHONPATH=src python src/analysis/rebuild_derived_diagnostics.py
```

The utility reconstructs derived summary CSVs in `results/reproduced/derived_data/` and auxiliary diagnostic plots in `results/reproduced/diagnostic_figures/`. It never overwrites the frozen `figures/data/` source summaries or the final publication figures. It does **not** rerun the experiments and does **not** regenerate the exact final publication PDFs. The six frozen publication PDFs are stored separately in `figures/publication/` and match the figure files bundled with the current manuscript package. Keep diagnostic plots separate from those final publication files.

## 6. Multi-machine timing studies

The graph and MDKP timing campaigns are not silently replayed by `reproduce.sh`. Their inference is tied to frozen schedules and recorded environments. The repository therefore retains the execution contracts and the exact recorded rows for reanalysis:

- primary graph timing: `experiments/graph_runtime/primary/` and `results/graph_runtime/primary/`;
- coefficient-scored graph timing: `experiments/graph_runtime/coefficient/` and `results/graph_runtime/coefficient/`;
- MDKP 90-case timing: `experiments/mdkp/` and `results/mdkp/timing/`.

This separation prevents a fresh run on an unrelated machine from being mistaken for reproduction of the recorded timing inference.
