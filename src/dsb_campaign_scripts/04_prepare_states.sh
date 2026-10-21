#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; export PYTHONPATH="$ROOT/code"
"$ROOT/.venv/bin/python" -m dsb_dynamic.prepare_states --root "$ROOT" --config "$ROOT/10_Experiment_Configuration/dsb_dynamic.json" --mode "${PCR_MODE:-primary}"
