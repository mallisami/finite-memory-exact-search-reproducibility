#!/usr/bin/env bash
set -euo pipefail
APPLY="${1:-}"
STATE="${PCR_SERVICE_STATE_FILE:-$HOME/pcr_tx_v4_service_state.tsv}"
[[ -f "$STATE" ]] || { echo "missing $STATE" >&2; exit 2; }
cat "$STATE"
if [[ "$APPLY" != "--apply" ]]; then
  echo "DRY RUN. Re-run with --apply."
  exit 0
fi
while IFS=$'\t' read -r u prior; do
  if [[ "$prior" == "active" ]]; then
    echo "Restoring $u"
    sudo systemctl start "$u"
  fi
done < "$STATE"
