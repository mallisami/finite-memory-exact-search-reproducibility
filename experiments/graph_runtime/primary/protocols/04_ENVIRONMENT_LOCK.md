# Prospective Environment Lock

## Historical reference

The original PCR campaign records Python 3.12.15 with the exact package versions in the authoritative reproducibility package. A later optional reproduction capsule used Python 3.13.5; it is a different captured runtime.

For the new prospective Transactions extension, the cleanest choice is Python **3.12.15** on all three VMs, because it matches the original campaign and is known to execute the current source.

## Exact package lock

Use `config/requirements_pcr_tx.txt`.

It includes:
- numpy 2.3.5
- scipy 1.17.0
- scikit-learn 1.8.0
- pandas 2.2.3
- matplotlib 3.10.8
- joblib 1.5.3
- threadpoolctl 3.6.0
- aiohttp 3.13.3
- pytest 9.0.2

The general VM inventory supplied by the user omitted scikit-learn; do not assume the project venv is complete.

## Installation rule

Create a dedicated `~/pcr_tx_v4_venv`.

Do not modify a historical PCR environment in place.

If exact Python 3.12.15 is unavailable on a node:
- install the same exact 3.12.x patch on all three nodes; or
- select a common exact 3.12.x prospective runtime and re-run all development equivalence gates.

Do not mix Python patch versions across primary machines.

## Semantic equivalence, not false binary identity

A new OS/kernel/CPU is not the historical captured runtime.

The new extension must reproduce PCR-v1 **scientific decisions and trajectories**, not claim byte-identical numerical-library runtime behavior across different Linux environments.
