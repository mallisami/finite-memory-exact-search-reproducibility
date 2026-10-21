"""Phase 9: Graph Capacity Characterization.

Follows Protocol V4 Section 11 strictly:
- Untimed keep-all execution for all 60 confirmatory Graph cases across all 4 opportunity levels (L1, L2, L3, L4).
- Records peak scientific bytes P_{c, l} and largest single checkpoint m_{c, l}^{max}.
- Calculates frozen scientific byte limit:
    M_{c, l} = max(m_{c, l}^{max}, round(0.25 * P_{c, l}))
- Saves frozen capacity matrix to 09_capacity_characterization/GRAPH_CAPACITY_LIMITS.json.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_EXT = _ROOT / "pcr_tx_extension"
if str(_EXT) not in sys.path:
    sys.path.insert(0, str(_EXT))

from pcr_tx_extension.certified_assignment.domain_instances import make_domain_case
from pcr_tx_extension.certified_assignment.paper2_online_pilot import generate_replay_trace
from pcr_tx_extension.certified_assignment.pcr_graph_engine import run_graph_campaign_case


def main():
    parser = argparse.ArgumentParser(description="Graph Capacity Characterization")
    parser.add_argument("--cases-manifest", default="07_confirmatory_cases/confirmatory_cases.csv")
    parser.add_argument("--levels-file", default="05_opportunity_level_freeze/OPPORTUNITY_LEVEL_FREEZE.json")
    parser.add_argument("--out-dir", default="09_capacity_characterization")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(args.levels_file) as f:
        levels_data = json.load(f)
    frozen_levels = levels_data["frozen_levels"]  # {"L1": 8, "L2": 16, "L3": 32, "L4": 64}

    with open(args.cases_manifest, newline="", encoding="utf-8") as f:
        all_cases = list(csv.DictReader(f))

    graph_cases = [r for r in all_cases if r["domain"].lower() == "graph"]
    print(f"Characterizing capacity for {len(graph_cases)} Graph cases across {len(frozen_levels)} levels...")

    capacity_matrix = {}
    rows = []

    for idx, case_row in enumerate(graph_cases, 1):
        case_id = case_row["case_id"]
        fam = case_row["family"]
        seed = int(case_row["seed"])
        domain = fam.lower()
        trace = generate_replay_trace(domain, seed, iterations=200, destroy_size=12)

        capacity_matrix[case_id] = {}

        for lvl_name, slice_pops in frozen_levels.items():
            # Run untimed keep_all characterization
            res = run_graph_campaign_case(
                domain=domain,
                seed=seed,
                trace=trace,
                policy_name="keep_all",
                slice_pops=slice_pops,
                budget_bytes=None,
            )

            P_cl = int(res.peak_bytes)
            m_max = int(res.max_checkpoint_size_bytes)
            M_cl = max(m_max, int(round(0.25 * P_cl)))

            capacity_matrix[case_id][lvl_name] = {
                "peak_bytes_keep_all": P_cl,
                "max_checkpoint_bytes": m_max,
                "frozen_budget_bytes": M_cl,
                "slice_pops": slice_pops,
            }

            rows.append({
                "case_id": case_id,
                "family": fam,
                "seed": seed,
                "level": lvl_name,
                "slice_pops": slice_pops,
                "peak_bytes_keep_all": P_cl,
                "max_checkpoint_bytes": m_max,
                "frozen_budget_bytes": M_cl,
            })

        if idx % 10 == 0 or idx == len(graph_cases):
            print(f"  [{idx}/{len(graph_cases)}] Characterized {case_id}")

    payload = {
        "status": "GRAPH_CAPACITY_CHARACTERIZED",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule": "M = max(m_max, round(0.25 * P_keep_all))",
        "frozen_levels": frozen_levels,
        "capacity_matrix": capacity_matrix,
    }

    out_json = out_dir / "GRAPH_CAPACITY_LIMITS.json"
    with open(out_json, "w") as f:
        json.dump(payload, f, indent=2)

    out_csv = out_dir / "graph_capacity_limits.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "family",
                "seed",
                "level",
                "slice_pops",
                "peak_bytes_keep_all",
                "max_checkpoint_bytes",
                "frozen_budget_bytes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved capacity limits to {out_json} and {out_csv}")


if __name__ == "__main__":
    main()
