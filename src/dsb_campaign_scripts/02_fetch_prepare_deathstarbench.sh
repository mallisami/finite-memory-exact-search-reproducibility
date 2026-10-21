#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; PY="$ROOT/.venv/bin/python"; export PYTHONPATH="$ROOT/code"
REPO="$ROOT/external/DeathStarBench"; COMMIT="6ecb09706140f8730b5385c08f1386c654c3c526"
if [[ ! -d "$REPO/.git" ]]; then git clone --recurse-submodules https://github.com/delimitrou/DeathStarBench.git "$REPO"; fi
git -C "$REPO" fetch --all --tags
git -C "$REPO" checkout --detach "$COMMIT"
git -C "$REPO" submodule update --init --recursive
[[ "$(git -C "$REPO" rev-parse HEAD)" == "$COMMIT" ]] || { echo "commit pin failure"; exit 20; }
for APPDIR in socialNetwork hotelReservation mediaMicroservices; do (cd "$REPO/$APPDIR" && "$ROOT/.runtime/dockerx" compose config >/dev/null); done
make -C "$REPO/wrk2" clean >/dev/null 2>&1 || true
make -C "$REPO/wrk2" -j2
mkdir -p "$ROOT/workloads/generated" "$ROOT/results/environment"
$PY -m dsb_dynamic.workload_tools prepare-script --app socialNetwork --src "$REPO/socialNetwork/wrk2/scripts/social-network/compose-post.lua" --dst "$ROOT/workloads/generated/socialNetwork.lua" > "$ROOT/workloads/generated/socialNetwork.manifest.json"
$PY -m dsb_dynamic.workload_tools prepare-script --app hotelReservation --src "$REPO/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua" --dst "$ROOT/workloads/generated/hotelReservation.lua" > "$ROOT/workloads/generated/hotelReservation.manifest.json"
$PY -m dsb_dynamic.workload_tools prepare-script --app mediaMicroservices --src "$REPO/mediaMicroservices/wrk2/scripts/media-microservices/compose-review.lua" --dst "$ROOT/workloads/generated/mediaMicroservices.lua" > "$ROOT/workloads/generated/mediaMicroservices.manifest.json"
git -C "$REPO" status --porcelain > "$ROOT/results/environment/DEATHSTARBENCH_GIT_STATUS.txt"
echo "$COMMIT" > "$ROOT/results/environment/DEATHSTARBENCH_COMMIT.txt"
echo "DEATHSTARBENCH PREP PASS"
