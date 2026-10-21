#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VM="${1:-}"
if [[ "$VM" != "A" && "$VM" != "B" ]]; then
  echo "Usage: $0 A|B" >&2; exit 2
fi
vml="${VM,,}"
META="09_RESULTS/vm-${vml}/meta"
mkdir -p "$META"
source .venv/bin/activate
source 02_CONFIG/timing_env.sh

python 07_SCRIPTS/verify_versions.py | tee "$META/versions.json"
python 07_SCRIPTS/verify_package_manifest.py | tee "$META/package_manifest_check.json"
python 07_SCRIPTS/validate_schedules.py | tee "$META/schedule_validation.json"
python 07_SCRIPTS/verify_coefficient_equivalence.py | tee "$META/scorer_equivalence.json"
bash 07_SCRIPTS/quiesce_for_timing.sh --apply | tee "$META/quiesce.log"
STATE="${PCR_SERVICE_STATE_FILE:-$HOME/pcr_tx_v4_service_state.tsv}"
[[ -f "$STATE" ]] && cp "$STATE" "$META/service_state_before_timing.tsv"

echo "[$VM] Waiting 300 seconds for Phase-A stabilization..."
sleep 300
python 07_SCRIPTS/preflight_vm.py --role primary --expected-vcpus 4 --required-cpus 0,1,2 --max-load 1.0 | tee "$META/phaseA_preflight.json"

for cpu in 0 1 2; do
  echo "[$VM] Non-sample warm-up on CPU $cpu"
  taskset -c "$cpu" python 07_SCRIPTS/warmup_graph_paths.py > "$META/phaseA_warmup_cpu${cpu}.log" 2>&1
done

mkdir -p "09_RESULTS/vm-${vml}/phaseA_lane0" "09_RESULTS/vm-${vml}/phaseA_lane1" "09_RESULTS/vm-${vml}/phaseA_lane2"
declare -a PIDS=()
for lane in 0 1 2; do
  sched="03_SCHEDULES/phaseA_7core/vm${vml}_lane${lane}_cpu${lane}.csv"
  out="09_RESULTS/vm-${vml}/phaseA_lane${lane}"
  label="vm-${vml}-phaseA-lane${lane}-cpu${lane}"
  echo "[$VM] Starting Phase-A lane $lane on CPU $lane"
  taskset -c "$lane" python 07_SCRIPTS/run_coefficient_graph_shard.py \
    --schedule "$sched" \
    --host-label "$label" \
    --physical-vm "$VM" \
    --phase phaseA_7core \
    --lane-id "$lane" \
    --cpu-id "$lane" \
    --concurrency-width 3 \
    --output-dir "$out" \
    --resume > "$out/console.log" 2>&1 &
  PIDS+=("$!")
done

fail=0
for i in 0 1 2; do
  if ! wait "${PIDS[$i]}"; then
    echo "[$VM] Phase-A lane $i failed. See its console.log" >&2
    fail=1
  fi
done
if [[ "$fail" -ne 0 ]]; then exit 10; fi

echo "[$VM] All three Phase-A lanes completed. Do NOT inspect timing outcomes."
echo "[$VM] Waiting 300 seconds before full isolated Phase-B rerun..."
sleep 300
python 07_SCRIPTS/preflight_vm.py --role primary --expected-vcpus 4 --required-cpus 0 --max-load 1.0 | tee "$META/phaseB_preflight.json"

echo "[$VM] Non-sample warm-up on CPU 0 for full isolated Phase B"
taskset -c 0 python 07_SCRIPTS/warmup_graph_paths.py > "$META/phaseB_warmup_cpu0.log" 2>&1
mkdir -p "09_RESULTS/vm-${vml}/phaseB_isolated_full"
sched="03_SCHEDULES/phaseB_isolated_full/vm${vml}_full_isolated_cpu0.csv"
out="09_RESULTS/vm-${vml}/phaseB_isolated_full"
label="vm-${vml}-phaseB-full-isolated-cpu0"

taskset -c 0 python 07_SCRIPTS/run_coefficient_graph_shard.py \
  --schedule "$sched" \
  --host-label "$label" \
  --physical-vm "$VM" \
  --phase phaseB_isolated_full \
  --lane-id isolated \
  --cpu-id 0 \
  --concurrency-width 1 \
  --output-dir "$out" \
  --resume | tee "$out/console.log"

echo "[$VM] COMPLETE: Phase A + full isolated Phase B. Bundle results before restoring services."
