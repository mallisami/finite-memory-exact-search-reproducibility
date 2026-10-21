#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export DEBIAN_FRONTEND=noninteractive
sudo -n apt-get update
sudo -n apt-get install -y git curl jq build-essential make gcc libssl-dev zlib1g-dev libluajit-5.1-dev luarocks lua-socket tcpdump tshark python3 python3-venv python3-pip ca-certificates docker.io
if ! docker compose version >/dev/null 2>&1 && ! sudo -n docker compose version >/dev/null 2>&1; then
  sudo -n apt-get install -y docker-compose-v2 || sudo -n apt-get install -y docker-compose-plugin
fi
sudo -n systemctl enable --now docker || true
sudo -n luarocks install luasocket >/dev/null 2>&1 || true
mkdir -p "$ROOT/.runtime"
cat > "$ROOT/.runtime/dockerx" <<'EOF'
#!/usr/bin/env bash
set -e
if docker info >/dev/null 2>&1; then exec docker "$@"; else exec sudo -n docker "$@"; fi
EOF
chmod +x "$ROOT/.runtime/dockerx"
"$ROOT/.runtime/dockerx" info >/dev/null
"$ROOT/.runtime/dockerx" compose version
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip wheel setuptools
"$ROOT/.venv/bin/pip" install -r "$ROOT/code/requirements-dsb-dynamic.txt"
"$ROOT/.venv/bin/pip" freeze > "$ROOT/results/environment/PIP_FREEZE.txt"
{ "$ROOT/.runtime/dockerx" version; tshark --version | head -2; tcpdump --version | head -1; "$ROOT/.venv/bin/python" --version; } > "$ROOT/results/environment/TOOL_VERSIONS.txt"
echo "BOOTSTRAP PASS"
