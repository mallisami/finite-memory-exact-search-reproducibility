#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
python src/run_experiments.py all_paper2 --workers "${WORKERS:-3}" --run-id "${RUN_ID:-FULL_RERUN}"
