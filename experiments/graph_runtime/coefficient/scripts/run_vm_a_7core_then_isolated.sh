#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/07_SCRIPTS/run_primary_7core_then_isolated.sh" A
