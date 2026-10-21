from pathlib import Path
import json
import pandas as pd

from dsb_dynamic.workload_tools import parse_quantity_bytes, parse_wrk_output, profile_schedule
from certified_assignment.paper2_dsb_environment import read_manifest


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_workload_parsers_and_regime_schedules():
    assert abs(parse_quantity_bytes("1MiB / 2GiB") - 1048576) < 1
    s = """  99.000%   12.50ms\n  600 requests in 30.00s, 1.0MB read\nRequests/sec: 20.00\nPCR_NON2XX=3\nSocket errors: connect 0, read 1, write 0, timeout 0\n"""
    d = parse_wrk_output(s, 20)
    assert d["requests"] == 600 and d["p99_ms"] == 12.5
    assert d["non2xx"] == 3 and d["socket_errors"] == 1
    assert len(profile_schedule("step", 5, 20)) == 10
    assert [x[0] for x in profile_schedule("burst", 5, 20)].count("H") == 3
    assert len(profile_schedule("ramp", 5, 20)) == 10


def test_frozen_measured_sequence_manifest_is_complete():
    root = _root()
    rows = read_manifest(root / "data/deathstarbench/prepared/sequence_manifest.csv")
    assert len(rows) == 90
    cells = {(r["app"], r["regime"]) for r in rows}
    assert len(cells) == 9
    assert all(sum(1 for r in rows if (r["app"], r["regime"]) == c) == 10 for c in cells)
    idx = pd.read_csv(root / "data/deathstarbench/measurement/MEASUREMENT_INDEX.csv")
    assert len(idx) == 900
    assert idx["seed"].nunique() == 900
    assert idx["pcap_sha256"].nunique() == 900


def test_dsb_commit_pin_matches_config_and_environment_record():
    root = _root()
    cfg = json.loads((root / "data/core/config/dsb_dynamic.json").read_text())
    recorded = (root / "data/deathstarbench/environment/DEATHSTARBENCH_COMMIT.txt").read_text().strip()
    assert cfg["deathstarbench"]["commit"] == recorded
