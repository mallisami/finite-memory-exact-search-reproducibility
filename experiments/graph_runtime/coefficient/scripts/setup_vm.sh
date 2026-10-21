#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
for cmd in taskset systemctl sudo; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Required command not found: $cmd" >&2; exit 2; }
done
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)'; then
    PYTHON_BIN=python3
  else
    echo "Python 3.12 not found. Install Python 3.12 and the venv module before running this setup." >&2
    exit 2
  fi
fi
cd "$ROOT"
mkdir -p 09_RESULTS
if ! "$PYTHON_BIN" -m venv .venv; then
  echo "Could not create .venv. Ensure the Python 3.12 venv module is installed." >&2
  exit 2
fi
source .venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -r 02_CONFIG/requirements_pcr_tx.txt
python 07_SCRIPTS/verify_versions.py
python 07_SCRIPTS/verify_package_manifest.py
python 07_SCRIPTS/validate_schedules.py
python 07_SCRIPTS/verify_coefficient_equivalence.py
