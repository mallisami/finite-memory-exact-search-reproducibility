#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
META="09_RESULTS/vm-c/meta"
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

echo "[C] Waiting 300 seconds for stabilization..."
sleep 300
python 07_SCRIPTS/preflight_vm.py --role secondary --expected-vcpus 2 --required-cpus 0 --max-load 1.0 | tee "$META/phaseA_preflight.json"
mkdir -p 09_RESULTS/vm-c/phaseA_lane0
taskset -c 0 python 07_SCRIPTS/warmup_graph_paths.py > "$META/phaseA_warmup_cpu0.log" 2>&1

taskset -c 0 python 07_SCRIPTS/run_coefficient_graph_shard.py \
  --schedule 03_SCHEDULES/phaseA_7core/vmc_lane0_cpu0.csv \
  --host-label vm-c-phaseA-lane0-cpu0 \
  --physical-vm C \
  --phase phaseA_7core \
  --lane-id 0 \
  --cpu-id 0 \
  --concurrency-width 1 \
  --output-dir 09_RESULTS/vm-c/phaseA_lane0 \
  --resume | tee 09_RESULTS/vm-c/phaseA_lane0/console.log

echo "[C] COMPLETE. Bundle results before restoring services."
