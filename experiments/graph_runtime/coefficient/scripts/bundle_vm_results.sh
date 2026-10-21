#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VM="${1:-}"
if [[ "$VM" != "A" && "$VM" != "B" && "$VM" != "C" ]]; then echo "Usage: $0 A|B|C" >&2; exit 2; fi
vml="${VM,,}"; dir="09_RESULTS/vm-${vml}"
[[ -d "$dir" ]] || { echo "Missing $dir" >&2; exit 3; }
name="PCR2_P0_VM_${VM}_RESULTS_$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
files=("$dir")
shopt -s nullglob
for f in 09_RESULTS/vm-${vml}_*warmup*.log; do files+=("$f"); done
shopt -u nullglob
tar -czf "$name" "${files[@]}"
sha256sum "$name" > "$name.sha256"
echo "$name"; cat "$name.sha256"
