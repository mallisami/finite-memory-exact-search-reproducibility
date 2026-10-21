"""Graph Search-Opportunity Level Selection and Freeze.

Follows Protocol V4 Section 11 strictly:
- Candidate budgets: B in {8, 16, 32, 64, 128, 256, 384}.
- Uses restart-only exposed development cases (e.g. 15 prior graph cases across generic, workflow, microservice).
- Calculates the exact fraction of repair calls unfinished (cert.exact == False) at each candidate budget.
- Rule:
  * L1 = 8
  * L2 = unused candidate nearest 75% unfinished
  * L3 = larger unused candidate nearest 50% unfinished
  * L4 = larger unused candidate nearest 25% unfinished
  * Ties choose the smaller eligible candidate.
- Output: 05_opportunity_level_freeze/OPPORTUNITY_LEVEL_FREEZE.json and .md.
"""
from __future__ import annotations

import argparse
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

import numpy as np
import pandas as pd

from pcr_tx_extension.certified_assignment.alns_baseline import _repair_greedy
from pcr_tx_extension.certified_assignment.anytime_gap_certified_repair import initialize_anytime_repair
from pcr_tx_extension.certified_assignment.destroy_repair_analysis import build_destroy_repair_cache
from pcr_tx_extension.certified_assignment.domain_instances import make_domain_case
from pcr_tx_extension.certified_assignment.paper2_online_pilot import generate_replay_trace
from pcr_tx_extension.certified_assignment.step_resumption import advance_anytime_repair_steps

CANDIDATES = [8, 16, 32, 64, 128, 256, 384]


def characterize_opportunity_levels(
    seeds: list[int],
    domains: list[str] = ["generic", "workflow", "microservice"],
    iterations: int = 40,
    destroy_size: int = 8,
) -> pd.DataFrame:
    """Run restart-only repair searches on exposed development cases across candidate budgets."""
    records = []
    
    for seed in seeds:
        for domain in domains:
            case = make_domain_case(domain, 24, 6, seed=int(seed))
            instance = case.instance
            placement = case.placement.copy()
            trace = generate_replay_trace(domain, seed, iterations=iterations, destroy_size=destroy_size)
            
            for step_idx, entry in enumerate(trace):
                nodes = entry.nodes
                cache = build_destroy_repair_cache(instance, placement, nodes)
                target, _ = _repair_greedy(instance, placement, nodes, np.random.default_rng(999 + step_idx))
                
                for b in CANDIDATES:
                    cp = initialize_anytime_repair(
                        instance, placement, nodes, initial_target_hosts=target, prebuilt_cache=cache
                    )
                    move, cert, pops = advance_anytime_repair_steps(instance, cp, max_branch_pops=b)
                    
                    records.append({
                        "case_id": f"{domain}_{seed}",
                        "domain": domain,
                        "seed": int(seed),
                        "step_idx": step_idx,
                        "budget": int(b),
                        "pops": int(pops),
                        "exact": bool(cert.exact),
                        "unfinished": int(not cert.exact),
                    })
                    
    return pd.DataFrame(records)


def select_frozen_levels(df: pd.DataFrame) -> dict[str, object]:
    """Apply the deterministic frozen level selection rule."""
    grouped = df.groupby("budget")["unfinished"].agg(["count", "mean"]).reset_index()
    grouped.columns = ["budget", "total_calls", "unfinished_rate"]
    
    stats_by_budget = {}
    for _, row in grouped.iterrows():
        b = int(row["budget"])
        rate = float(row["unfinished_rate"])
        calls = int(row["total_calls"])
        stats_by_budget[b] = {"unfinished_rate": rate, "total_calls": calls}
        
    print("\n--- Candidate Budget Unfinished Rates ---")
    for b in CANDIDATES:
        print(f"  B = {b:3d}: unfinished_rate = {stats_by_budget[b]['unfinished_rate']:.4f} ({stats_by_budget[b]['unfinished_rate']*100:.2f}%)")
        
    # Selection rule:
    # L1 = 8
    # L2 = unused candidate nearest 75% (0.75)
    # L3 = larger unused candidate nearest 50% (0.50)
    # L4 = larger unused candidate nearest 25% (0.25)
    
    L1 = 8
    used = {L1}
    
    # L2: unused nearest 0.75
    cand_l2 = [b for b in CANDIDATES if b not in used and b > L1]
    L2 = min(cand_l2, key=lambda b: (abs(stats_by_budget[b]["unfinished_rate"] - 0.75), b))
    used.add(L2)
    
    # L3: larger unused nearest 0.50
    cand_l3 = [b for b in CANDIDATES if b not in used and b > L2]
    if not cand_l3:
        cand_l3 = [b for b in CANDIDATES if b > L2]
    L3 = min(cand_l3, key=lambda b: (abs(stats_by_budget[b]["unfinished_rate"] - 0.50), b))
    used.add(L3)
    
    # L4: larger unused nearest 0.25
    cand_l4 = [b for b in CANDIDATES if b not in used and b > L3]
    if not cand_l4:
        cand_l4 = [b for b in CANDIDATES if b > L3]
    L4 = min(cand_l4, key=lambda b: (abs(stats_by_budget[b]["unfinished_rate"] - 0.25), b))
    used.add(L4)
    
    frozen_levels = {
        "L1": int(L1),
        "L2": int(L2),
        "L3": int(L3),
        "L4": int(L4),
    }
    
    return {
        "frozen_levels": frozen_levels,
        "candidate_stats": stats_by_budget,
        "targets": {"L1": "frozen baseline (8)", "L2": "nearest 75% unfinished", "L3": "nearest 50% unfinished", "L4": "nearest 25% unfinished"},
    }


def main():
    parser = argparse.ArgumentParser(description="Freeze Graph Opportunity Levels")
    parser.add_argument("--out-dir", default="05_opportunity_level_freeze")
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Exposed development seeds from PRIOR_SEED_REGISTRY
    dev_seeds = [3301, 3302, 3303, 3304, 3305, 3306, 3307, 3308, 3309, 3310, 3311, 3312, 3313, 3314, 3315]
    
    print(f"Characterizing search-opportunity candidates across {len(dev_seeds)} exposed development cases...")
    df = characterize_opportunity_levels(dev_seeds, iterations=40)
    print(f"Collected {len(df)} restart repair search characterizations.")
    
    results = select_frozen_levels(df)
    
    payload = {
        "status": "OPPORTUNITY_LEVELS_FROZEN",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule": "Protocol V4 Section 11: L1=8, L2~75%, L3~50%, L4~25% unfinished rate on restart-only exposed development cases",
        "dev_seeds": dev_seeds,
        "candidates": CANDIDATES,
        **results,
    }
    
    out_json = out_dir / "OPPORTUNITY_LEVEL_FREEZE.json"
    with open(out_json, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved frozen levels to {out_json}")
    
    # Write Markdown report
    out_md = out_dir / "OPPORTUNITY_LEVEL_FREEZE.md"
    with open(out_md, "w") as f:
        f.write("# Graph Search-Opportunity Level Selection Report\n\n")
        f.write(f"**Generated:** {payload['timestamp_utc']}  \n")
        f.write(f"**Rule:** {payload['rule']}  \n\n")
        f.write("## Candidate Budget Characterization\n\n")
        f.write("| Budget ($B$) | Total Repair Calls | Unfinished Count | Unfinished Rate | Target Milestone |\n")
        f.write("|:---:|:---:|:---:|:---:|:---:|\n")
        for b in CANDIDATES:
            stat = payload["candidate_stats"][b]
            rate = stat["unfinished_rate"]
            calls = stat["total_calls"]
            unf = int(round(rate * calls))
            note = ""
            for lvl, val in payload["frozen_levels"].items():
                if val == b:
                    note = f"**{lvl}** ({payload['targets'][lvl]})"
            f.write(f"| {b} | {calls} | {unf} | {rate:.4f} ({rate*100:.1f}%) | {note} |\n")
            
        f.write("\n## Frozen Operational Levels\n\n")
        for lvl in ["L1", "L2", "L3", "L4"]:
            val = payload["frozen_levels"][lvl]
            rate = payload["candidate_stats"][val]["unfinished_rate"]
            f.write(f"- **{lvl}**: `{val}` branch pops (unfinished rate = {rate*100:.2f}%, {payload['targets'][lvl]})\n")
            
    print(f"Saved report to {out_md}")


if __name__ == "__main__":
    main()
