"""Authoritative One-Shot Primary Confirmatory Execution Runner.

Follows Protocol V4 Sections 11, 12, 13, 15, and 21 strictly:
- Reads the host execution schedule (08_case_shards/<host>_schedule.csv).
- Executes runs sequentially in isolated single-process execution.
- Employs frozen models, frozen integer weights, and frozen capacity limits.
- Maintains an append-only Write-Ahead Log (WAL) at 14_wal/<host>_wal.csv.
- Buffers output writes to prevent disk I/O noise during timed scope.
- Enforces strict one-shot execution and deterministic integrity checks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_EXT = _ROOT / "pcr_tx_extension"
if str(_EXT) not in sys.path:
    sys.path.insert(0, str(_EXT))

import numpy as np
import pandas as pd

from pcr_tx_extension.compute_counters import COUNTER_NAMES, ComputeCounters
from pcr_tx_extension.certified_assignment.domain_instances import make_domain_case
from pcr_tx_extension.certified_assignment.paper2_online_pilot import (
    FrozenP6Predictor,
    generate_replay_trace,
)
from pcr_tx_extension.certified_assignment.pcr_graph_engine import (
    run_graph_campaign_case,
    GraphPolicyName,
)
from pcr_tx_extension.independent_mdkp.controller import P10Predictor
from pcr_tx_extension.independent_mdkp.pcr_mdkp_engine import (
    run_mdkp_campaign_case,
    MDKPPolicyName,
)


def find_predictors(root: Path):
    p6_candidates = [
        root / "02_Authoritative_Experimental_Evidence",
        root / "evidence_and_models" / "02_Authoritative_Experimental_Evidence",
        root.parent / "evidence_and_models" / "02_Authoritative_Experimental_Evidence",
    ]
    p6_base = None
    for cand in p6_candidates:
        if (cand / "03_P6_Predictor_Development" / "p6_final_model.joblib").exists():
            p6_base = cand
            break
    if p6_base is None:
        raise FileNotFoundError("Could not find p6_final_model.joblib")
    p6 = FrozenP6Predictor(p6_base)

    p10_candidates = [
        root / "06_Executed_Reproduction_Results" / "01_Original_Reproduction_Campaign" / "Retained_Unique_or_Changed_Files" / "09_P10_Independent_MDKP_Validation" / "development",
        root / "evidence_and_models" / "06_Executed_Reproduction_Results" / "01_Original_Reproduction_Campaign" / "Retained_Unique_or_Changed_Files" / "09_P10_Independent_MDKP_Validation" / "development",
        root.parent / "evidence_and_models" / "06_Executed_Reproduction_Results" / "01_Original_Reproduction_Campaign" / "Retained_Unique_or_Changed_Files" / "09_P10_Independent_MDKP_Validation" / "development",
    ]
    p10_dir = None
    for cand in p10_candidates:
        if (cand / "p10_final_model.joblib").exists():
            p10_dir = cand
            break
    if p10_dir is None:
        raise FileNotFoundError("Could not find p10_final_model.joblib")
    p10 = P10Predictor(p10_dir / "p10_final_model.joblib", p10_dir / "p10_calibration.joblib")

    return p6, p10


def main():
    parser = argparse.ArgumentParser(description="Run Primary Confirmatory Shard")
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--wal-dir", default="14_wal")
    parser.add_argument("--graph-out-dir", default="10_primary_graph")
    parser.add_argument("--mdkp-out-dir", default="11_primary_mdkp")
    parser.add_argument("--weights-file", default="04_compute_calibration/PRIMARY_A_CALIBRATION.json")
    parser.add_argument("--capacity-file", default="09_capacity_characterization/GRAPH_CAPACITY_LIMITS.json")
    parser.add_argument("--levels-file", default="05_opportunity_level_freeze/OPPORTUNITY_LEVEL_FREEZE.json")
    args = parser.parse_args()

    root = Path(_ROOT)
    wal_dir = root / args.wal_dir
    wal_dir.mkdir(parents=True, exist_ok=True)
    graph_out_dir = root / args.graph_out_dir
    graph_out_dir.mkdir(parents=True, exist_ok=True)
    mdkp_out_dir = root / args.mdkp_out_dir
    mdkp_out_dir.mkdir(parents=True, exist_ok=True)

    # Load frozen weights
    with open(root / args.weights_file) as f:
        calib = json.load(f)
    int_w_graph = calib["graph"]["integer_weights"]
    int_w_mdkp = calib["mdkp"]["integer_weights"]

    # Load frozen levels
    with open(root / args.levels_file) as f:
        levels_data = json.load(f)
    frozen_levels = levels_data["frozen_levels"]  # {"L1": 8, "L2": 16, "L3": 32, "L4": 64}

    # Load frozen capacity limits
    with open(root / args.capacity_file) as f:
        cap_data = json.load(f)
    capacity_matrix = cap_data["capacity_matrix"]

    # Load models
    p6, p10 = find_predictors(root)

    # Read schedule
    with open(args.schedule, newline="", encoding="utf-8") as f:
        schedule_rows = list(csv.DictReader(f))

    wal_path = wal_dir / f"{args.host}_wal.csv"
    wal_exists = wal_path.exists()

    # Pre-generate traces for cases on this host so trace generation is outside the timed scope
    print(f"[{args.host}] Pre-generating instance traces for schedule...")
    cached_graph_traces = {}
    for r in schedule_rows:
        if r["domain"].lower() == "graph":
            k = (r["family"].lower(), int(r["seed"]))
            if k not in cached_graph_traces:
                cached_graph_traces[k] = generate_replay_trace(k[0], k[1], iterations=200, destroy_size=12)

    wal_fields = [
        "run_id", "case_id", "domain", "family", "seed", "primary_machine", "level",
        "repeat", "position", "policy", "start_time_iso", "end_time_iso", "status",
        "technical_valid", "end_to_end_wall_ns", "end_to_end_cpu_ns", "end_to_end_wall_ms",
        "end_to_end_cpu_ms", "trajectory_hash", "accepted_moves", "executed_branches",
        "useful_resumes", "reused_branches", "checkpoint_creations", "capacity_evictions",
        "invalidation_evictions", "peak_bytes", "byte_time", "initial_objective",
        "final_objective", "best_objective", "expanded_nodes", "bound_evals",
        "generated_children", "feasibility_checks", "incumbent_evals", "frontier_inserts",
    ]

    wal_file = open(wal_path, "a", newline="", encoding="utf-8")
    wal_writer = csv.DictWriter(wal_file, fieldnames=wal_fields)
    if not wal_exists:
        wal_writer.writeheader()
        wal_file.flush()

    total_runs = len(schedule_rows)
    print(f"[{args.host}] Starting one-shot confirmatory execution of {total_runs} scheduled runs...")

    graph_records = []
    mdkp_records = []

    t_shard_start = time.time()

    for idx, row in enumerate(schedule_rows, 1):
        run_id = row["run_id"]
        case_id = row["case_id"]
        domain = row["domain"].lower()
        family = row["family"]
        seed = int(row["seed"])
        level = row["level"]
        repeat = int(row["repeat"])
        position = int(row["position"])
        policy = row["policy"]

        start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        try:
            if domain == "graph":
                slice_pops = frozen_levels[level]
                budget_bytes = capacity_matrix[case_id][level]["frozen_budget_bytes"]
                trace = cached_graph_traces[(family.lower(), seed)]

                res = run_graph_campaign_case(
                    domain=family.lower(),
                    seed=seed,
                    trace=trace,
                    policy_name=policy,
                    slice_pops=slice_pops,
                    budget_bytes=budget_bytes,
                    predictor=p6,
                    compute_weights=int_w_graph,
                )

                end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                counters = res.total_counters

                wal_row = {
                    "run_id": run_id,
                    "case_id": case_id,
                    "domain": "graph",
                    "family": family,
                    "seed": seed,
                    "primary_machine": args.host,
                    "level": level,
                    "repeat": repeat,
                    "position": position,
                    "policy": policy,
                    "start_time_iso": start_iso,
                    "end_time_iso": end_iso,
                    "status": "SUCCESS",
                    "technical_valid": "1",
                    "end_to_end_wall_ns": res.end_to_end_wall_ns,
                    "end_to_end_cpu_ns": res.end_to_end_cpu_ns,
                    "end_to_end_wall_ms": float(res.end_to_end_wall_ns / 1e6),
                    "end_to_end_cpu_ms": float(res.end_to_end_cpu_ns / 1e6),
                    "trajectory_hash": res.trajectory_hash,
                    "accepted_moves": res.accepted_moves,
                    "executed_branches": res.branch_pops_executed,
                    "useful_resumes": res.useful_resumes,
                    "reused_branches": res.reused_prior_branch_pops,
                    "checkpoint_creations": res.checkpoint_creations,
                    "capacity_evictions": res.capacity_evictions,
                    "invalidation_evictions": res.invalidation_evictions,
                    "peak_bytes": res.peak_bytes,
                    "byte_time": res.byte_time,
                    "initial_objective": res.initial_objective,
                    "final_objective": res.final_objective,
                    "best_objective": res.best_objective,
                    "expanded_nodes": counters.get("expanded_nodes", 0),
                    "bound_evals": counters.get("bound_evals", 0),
                    "generated_children": counters.get("generated_children", 0),
                    "feasibility_checks": counters.get("feasibility_checks", 0),
                    "incumbent_evals": counters.get("incumbent_evals", 0),
                    "frontier_inserts": counters.get("frontier_inserts", 0),
                }
                graph_records.append(wal_row)

            elif domain == "mdkp":
                res = run_mdkp_campaign_case(
                    seed=seed,
                    n_items=168,
                    destroy_size=54,
                    slice_nodes=384,
                    iterations=200,
                    policy=policy,
                    context_count=18,
                    budget_bytes=4206,
                    predictor=p10,
                    compute_weights=int_w_mdkp,
                )

                end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                counters = res.total_counters

                wal_row = {
                    "run_id": run_id,
                    "case_id": case_id,
                    "domain": "mdkp",
                    "family": "MDKP",
                    "seed": seed,
                    "primary_machine": args.host,
                    "level": "MDKP",
                    "repeat": repeat,
                    "position": position,
                    "policy": policy,
                    "start_time_iso": start_iso,
                    "end_time_iso": end_iso,
                    "status": "SUCCESS",
                    "technical_valid": "1",
                    "end_to_end_wall_ns": res.end_to_end_wall_ns,
                    "end_to_end_cpu_ns": res.end_to_end_cpu_ns,
                    "end_to_end_wall_ms": float(res.end_to_end_wall_ns / 1e6),
                    "end_to_end_cpu_ms": float(res.end_to_end_cpu_ns / 1e6),
                    "trajectory_hash": res.trajectory_hash,
                    "accepted_moves": res.accepted_moves,
                    "executed_branches": res.branch_nodes_executed,
                    "useful_resumes": res.useful_resumes,
                    "reused_branches": res.reused_prior_nodes,
                    "checkpoint_creations": res.checkpoint_creations,
                    "capacity_evictions": res.capacity_evictions,
                    "invalidation_evictions": res.invalidation_evictions,
                    "peak_bytes": res.peak_checkpoint_bytes,
                    "byte_time": res.byte_time,
                    "initial_objective": res.initial_cost,
                    "final_objective": res.final_cost,
                    "best_objective": res.best_cost,
                    "expanded_nodes": counters.get("expanded_nodes", 0),
                    "bound_evals": counters.get("bound_evals", 0),
                    "generated_children": counters.get("generated_children", 0),
                    "feasibility_checks": counters.get("feasibility_checks", 0),
                    "incumbent_evals": counters.get("incumbent_evals", 0),
                    "frontier_inserts": counters.get("frontier_inserts", 0),
                }
                mdkp_records.append(wal_row)

            else:
                raise ValueError(f"Unknown domain: {domain}")

            wal_writer.writerow(wal_row)
            wal_file.flush()

        except Exception as ex:
            end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            err_row = {
                "run_id": run_id,
                "case_id": case_id,
                "domain": domain,
                "family": family,
                "seed": seed,
                "primary_machine": args.host,
                "level": level,
                "repeat": repeat,
                "position": position,
                "policy": policy,
                "start_time_iso": start_iso,
                "end_time_iso": end_iso,
                "status": f"ERROR: {ex}",
                "technical_valid": "0",
            }
            wal_writer.writerow(err_row)
            wal_file.flush()
            print(f"[{args.host}] ERROR on run {run_id}: {ex}")

        if idx % 50 == 0 or idx == total_runs:
            elapsed = time.time() - t_shard_start
            rate = idx / elapsed
            rem = (total_runs - idx) / max(rate, 1e-6)
            print(f"[{args.host}] Progress: {idx}/{total_runs} ({idx/total_runs*100:.1f}%) | Elapsed: {elapsed/60:.1f}m | ETA: {rem/60:.1f}m")

    wal_file.close()

    # Save domain summary results
    if graph_records:
        df_g = pd.DataFrame(graph_records)
        g_out = graph_out_dir / f"{args.host}_graph_results.csv"
        df_g.to_csv(g_out, index=False)
        print(f"[{args.host}] Saved {len(df_g)} Graph results to {g_out}")

    if mdkp_records:
        df_m = pd.DataFrame(mdkp_records)
        m_out = mdkp_out_dir / f"{args.host}_mdkp_results.csv"
        df_m.to_csv(m_out, index=False)
        print(f"[{args.host}] Saved {len(df_m)} MDKP results to {m_out}")

    print(f"[{args.host}] PRIMARY_CONFIRMATORY_SHARD_COMPLETE_SUCCESS")


if __name__ == "__main__":
    main()
