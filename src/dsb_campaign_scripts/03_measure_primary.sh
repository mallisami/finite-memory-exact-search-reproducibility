#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; export PYTHONPATH="$ROOT/code"
"$ROOT/.venv/bin/python" -m dsb_dynamic.measure_campaign --root "$ROOT" --config "$ROOT/10_Experiment_Configuration/dsb_dynamic.json" --docker "$ROOT/.runtime/dockerx" --python "$ROOT/.venv/bin/python" --tshark tshark --mode primary
