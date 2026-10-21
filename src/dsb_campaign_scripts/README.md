# Reproducing E-DSB from the integrated PCR package

The frozen primary result tree lives at `09_Supporting_Data/DeathStarBench_Measured_Inputs/`. Do not overwrite it.

## Analysis-only reproduction

From the package root, install the lightweight DSB analysis requirements and run:

```bash
python -m pip install -r code/requirements-dsb-dynamic.txt
python scripts/reproduce_dsb_analysis.py
```

The helper creates `reproduced_dsb_dynamic/`, copies only the frozen prepared and solver inputs needed by the
analysis, reruns `dsb_dynamic.analyze_campaign`, and compares the regenerated statistical JSON/CSV outputs with
the frozen references. It never writes into `09_Supporting_Data/DeathStarBench_Measured_Inputs/`.

## Full measured-campaign rerun

A full rerun requires Linux x86_64, Docker Compose, tcpdump/tshark, passwordless sudo for unattended setup, at
least four logical CPUs, about 14 GiB RAM, and roughly 25 GB free disk. The exact source/configuration is retained
under `code/`, `config/`, and `scripts/dsb_dynamic/`.

Because the integrated package also contains frozen historical results, perform a full E-DSB rerun in a **clean
working copy** rather than in this archival tree. Copy `code/`, `config/`, `09_Supporting_Data/Topology_Zoo/`, and
`scripts/dsb_dynamic/` into a clean directory, place the stage scripts under `scripts/` as in the original runner,
and execute the primary pipeline. The pinned DeathStarBench commit is recorded in the protocol and configuration.

The unexecuted second-host subset is intentionally not included as a runnable follow-up in this clean package;
see `protocol/PROTOCOL_AMENDMENT_DSB_COMPLETION_2026-10-01.md`.
