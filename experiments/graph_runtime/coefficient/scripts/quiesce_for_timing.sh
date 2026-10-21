#!/usr/bin/env bash
set -euo pipefail
APPLY="${1:-}"
STATE="${PCR_SERVICE_STATE_FILE:-$HOME/pcr_tx_v4_service_state.tsv}"
UNITS=(k3s k3s-agent docker.socket docker containerd zeek unattended-upgrades apt-daily.timer apt-daily-upgrade.timer)
TMP="${STATE}.proposed"
: > "$TMP"
for u in "${UNITS[@]}"; do
  if systemctl status "$u" >/dev/null 2>&1 || systemctl list-unit-files "$u" --no-legend 2>/dev/null | grep -q .; then
    a="$(systemctl is-active "$u" 2>/dev/null || true)"
    printf '%s\t%s\n' "$u" "$a" >> "$TMP"
  fi
done
cat "$TMP"
if [[ "$APPLY" != "--apply" ]]; then
  echo "DRY RUN. Re-run with --apply."
  exit 0
fi
cp "$TMP" "$STATE"
# stop sockets/timers before daemons where relevant
ORDER=(apt-daily.timer apt-daily-upgrade.timer docker.socket k3s-agent k3s docker containerd zeek unattended-upgrades)
for u in "${ORDER[@]}"; do
  if awk -F '\t' -v x="$u" '$1==x && $2=="active"{found=1} END{exit !found}' "$STATE"; then
    echo "Stopping $u"
    sudo systemctl stop "$u"
  fi
done
bad=0
while IFS=$'\t' read -r u prior; do
  now="$(systemctl is-active "$u" 2>/dev/null || true)"
  if [[ "$prior" == "active" && "$now" == "active" ]]; then
    echo "FAILED TO QUIESCE: $u" >&2; bad=1
  fi
done < "$STATE"
[[ "$bad" -eq 0 ]] || exit 4
echo "Saved service state: $STATE"
