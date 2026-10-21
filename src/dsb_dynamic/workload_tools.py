from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

import numpy as np


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_seed(base: int, *parts: int) -> int:
    out = int(base)
    for p in parts:
        out = (out * 1000003 + int(p) * 9176 + 37) % 2147483647
    return max(out, 1)


def parse_quantity_bytes(text: str) -> float:
    s = text.strip().split("/")[0].strip()
    m = re.match(r"^([0-9.]+)\s*([KMGT]?i?B)$", s, re.I)
    if not m:
        raise ValueError(f"cannot parse memory quantity: {text!r}")
    val = float(m.group(1))
    unit = m.group(2).lower()
    scale = {
        "b": 1.0,
        "kb": 1e3, "kib": 1024.0,
        "mb": 1e6, "mib": 1024.0**2,
        "gb": 1e9, "gib": 1024.0**3,
        "tb": 1e12, "tib": 1024.0**4,
    }[unit]
    return val * scale


def parse_time_ms(text: str) -> float:
    s = text.strip()
    m = re.match(r"^([0-9.]+)\s*(us|ms|s)$", s, re.I)
    if not m:
        raise ValueError(f"cannot parse latency: {text!r}")
    v = float(m.group(1)); u = m.group(2).lower()
    return v / 1000.0 if u == "us" else v if u == "ms" else v * 1000.0


def parse_wrk_output(text: str, requested_rps: float) -> dict[str, float | int | str]:
    req = re.search(r"Requests/sec:\s*([0-9.]+)", text)
    requests = re.search(r"\b([0-9]+)\s+requests in\s+", text)
    p99 = re.search(r"^\s*99\.000%\s+([0-9.]+(?:us|ms|s))", text, re.M)
    non2xx = re.search(r"PCR_NON2XX=([0-9]+)", text)
    socket = re.search(
        r"Socket errors:\s*connect\s*([0-9]+),\s*read\s*([0-9]+),\s*write\s*([0-9]+),\s*timeout\s*([0-9]+)",
        text,
    )
    achieved = float(req.group(1)) if req else float("nan")
    n_requests = int(requests.group(1)) if requests else 0
    p99_ms = parse_time_ms(p99.group(1)) if p99 else float("nan")
    n_non2xx = int(non2xx.group(1)) if non2xx else 0
    socket_errors = sum(int(x) for x in socket.groups()) if socket else 0
    denom = max(n_requests, 1)
    return {
        "requested_rps": float(requested_rps),
        "achieved_rps": achieved,
        "achieved_fraction": achieved / max(float(requested_rps), 1e-12),
        "requests": n_requests,
        "p99_ms": p99_ms,
        "non2xx": n_non2xx,
        "non2xx_fraction": n_non2xx / denom,
        "socket_errors": socket_errors,
        "socket_error_fraction": socket_errors / denom,
    }


def transform_workload_script(src: Path, dst: Path, app: str) -> dict[str, str]:
    text = src.read_text(encoding="utf-8")
    original = text
    # Freeze Lua RNG from environment instead of wall clock.
    text, n = re.subn(r"math\.randomseed\([^\n]*\)", 'math.randomseed(tonumber(os.getenv("PCR_SEED")) or 1)', text, count=1)
    if n != 1:
        raise RuntimeError(f"expected one math.randomseed line in {src}")

    if app == "hotelReservation":
        needle = "local function reserve()\n"
        if needle not in text:
            raise RuntimeError("hotel workload source changed: reserve() marker not found")
        insert = (
            "local function reserve()\n"
            "  local lat = 38.0235 + (math.random(0, 481) - 240.5)/1000.0\n"
            "  local lon = -122.095 + (math.random(0, 325) - 157.0)/1000.0\n"
        )
        text = text.replace(needle, insert, 1)

    if "PCR_NON2XX=" not in text:
        text += r'''

local pcr_non2xx = 0
response = function(status, headers, body)
  if status < 200 or status >= 400 then
    pcr_non2xx = pcr_non2xx + 1
  end
end

done = function(summary, latency, requests)
  io.write("\nPCR_NON2XX=" .. tostring(pcr_non2xx) .. "\n")
end
'''
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    import hashlib
    return {
        "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "generated_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source": str(src),
        "generated": str(dst),
    }


def profile_schedule(regime: str, low: int, high: int, n: int = 10) -> list[tuple[str, int]]:
    if n != 10:
        raise ValueError("frozen protocol requires ten states")
    if low <= 0 or high <= low:
        raise ValueError(f"invalid low/high rates: {low}, {high}")
    if regime == "step":
        return [("L", low)] * 5 + [("H", high)] * 5
    if regime == "burst":
        labels = ["L", "L", "H", "L", "L", "H", "L", "L", "H", "L"]
        return [(x, high if x == "H" else low) for x in labels]
    if regime == "ramp":
        vals = np.rint(np.linspace(low, high, 10)).astype(int).tolist()
        return [(f"R{i}", max(1, int(v))) for i, v in enumerate(vals)]
    raise ValueError(regime)


def p95(values: Iterable[float]) -> float:
    x = np.asarray(list(values), dtype=float)
    if x.size == 0:
        raise ValueError("empty p95 input")
    return float(np.quantile(x, 0.95, method="linear"))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare-script")
    p.add_argument("--src", required=True); p.add_argument("--dst", required=True); p.add_argument("--app", required=True)
    q = sub.add_parser("parse-wrk")
    q.add_argument("--log", required=True); q.add_argument("--requested-rps", required=True, type=float)
    s = sub.add_parser("schedule")
    s.add_argument("--regime", required=True); s.add_argument("--low", type=int, required=True); s.add_argument("--high", type=int, required=True)
    args = ap.parse_args()
    if args.cmd == "prepare-script":
        print(json.dumps(transform_workload_script(Path(args.src), Path(args.dst), args.app), indent=2))
    elif args.cmd == "parse-wrk":
        print(json.dumps(parse_wrk_output(Path(args.log).read_text(errors="replace"), args.requested_rps), indent=2))
    else:
        print(json.dumps(profile_schedule(args.regime, args.low, args.high), indent=2))


if __name__ == "__main__":
    main()
