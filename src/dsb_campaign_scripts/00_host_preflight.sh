#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$ROOT/results/environment"
LOG="$ROOT/results/environment/HOST_PREFLIGHT.txt"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "uname=$(uname -a)"
  echo "arch=$(uname -m)"
  echo "nproc=$(nproc)"
  echo "mem_kib=$(awk '/MemTotal/{print $2}' /proc/meminfo)"
  echo "disk_free_kib=$(df -Pk "$ROOT" | awk 'NR==2{print $4}')"
  command -v lsb_release >/dev/null && lsb_release -a 2>/dev/null || true
} | tee "$LOG"
[[ "$(uname -s)" == "Linux" ]] || { echo "ERROR: Linux required"; exit 10; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "ERROR: x86_64 required by DeathStarBench wrk2 path"; exit 11; }
(( $(nproc) >= 4 )) || { echo "ERROR: at least 4 logical CPUs required"; exit 12; }
MEM=$(awk '/MemTotal/{print $2}' /proc/meminfo); (( MEM >= 14000000 )) || { echo "ERROR: at least about 14 GiB RAM required"; exit 13; }
FREE=$(df -Pk "$ROOT" | awk 'NR==2{print $4}'); (( FREE >= 25000000 )) || { echo "ERROR: at least about 25 GB free disk required"; exit 14; }
sudo -n true || { echo "ERROR: passwordless sudo is required for unattended Docker/tcpdump setup"; exit 15; }
echo "PREFLIGHT PASS"
