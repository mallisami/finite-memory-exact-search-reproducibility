#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-cluster_inventory}"
mkdir -p "$OUT"
CFG="$ROOT/config/ssh_config.local.sample"
for H in rack-a rack-b rack-c; do
  echo "Collecting $H ..."
  ssh -F "$CFG" "$H" 'python3 -' < "$ROOT/scripts/collect_vm_inventory.py" > "$OUT/$H.json"
done
echo "Inventory written to $OUT/"
