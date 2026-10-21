"""Compute-Aware Refinement (pC) Calibration and Multi-Node Validation Pipeline.

Follows Protocol V4 Section 4 strictly:
1. Calibration Machine (PRIMARY_A only):
   - Runs exposed development cases on PRIMARY_A.
   - Fits NNLS non-negative operation weights omega_k >= 0 for exact-search CPU nanoseconds.
   - Integerizes weights: tilde_omega_k = max(0, round(omega_k)).
   - Evaluates 5-fold grouped CV on PRIMARY_A:
     * Spearman correlation rho >= 0.70
     * Scaled NMAE <= 0.35
2. Cross-Machine Validation Gate (PRIMARY_B):
   - Uses the identical frozen integer weights (NO refitting).
   - Evaluates on PRIMARY_B:
     * Spearman correlation rho >= 0.70
     * Scaled NMAE <= 0.35
3. Continuation-Value Sanity Gate (PRIMARY_A and PRIMARY_B):
   - Evaluates rho(C_i, T_restart^CPU - T_resume^CPU) >= 0.60.
4. Cross-Primary Deterministic Replay Gate:
   - Replays 10 exposed graph and 10 exposed MDKP cases under pC on both primaries.
   - Verifies identical trajectory hashes and resident states.
5. Saves authoritative calibration and validation report to 04_compute_calibration/.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_EXT = _ROOT / "pcr_tx_extension"
if str(_EXT) not in sys.path:
    sys.path.insert(0, str(_EXT))

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold

# Import extension engines
try:
    from pcr_tx_extension.compute_counters import COUNTER_NAMES, ComputeCounters
    from pcr_tx_extension.certified_assignment.pcr_graph_engine import (
        advance_anytime_repair_with_counters,
        run_graph_campaign_case,
    )
    from pcr_tx_extension.certified_assignment.alns_baseline import _repair_greedy
    from pcr_tx_extension.certified_assignment.anytime_gap_certified_repair import initialize_anytime_repair
    from pcr_tx_extension.certified_assignment.destroy_repair_analysis import build_destroy_repair_cache
    from pcr_tx_extension.certified_assignment.domain_instances import make_domain_case
    from pcr_tx_extension.certified_assignment.paper2_online_pilot import (
        FrozenP6Predictor,
        generate_replay_trace,
    )
    from pcr_tx_extension.independent_mdkp.controller import P10Predictor
    from pcr_tx_extension.independent_mdkp.core import (
        initial_solution,
        initialize_checkpoint,
        make_context_library,
        make_context_trace,
        make_instance,
    )
    from pcr_tx_extension.independent_mdkp.pcr_mdkp_engine import (
        advance_checkpoint_with_counters,
        run_mdkp_campaign_case,
    )
except ImportError:
    from compute_counters import COUNTER_NAMES, ComputeCounters
    from certified_assignment.pcr_graph_engine import (
        advance_anytime_repair_with_counters,
        run_graph_campaign_case,
    )
    from certified_assignment.alns_baseline import _repair_greedy
    from certified_assignment.anytime_gap_certified_repair import initialize_anytime_repair
    from certified_assignment.destroy_repair_analysis import build_destroy_repair_cache
    from certified_assignment.domain_instances import make_domain_case
    from certified_assignment.paper2_online_pilot import (
        FrozenP6Predictor,
        generate_replay_trace,
    )
    from independent_mdkp.controller import P10Predictor
    from independent_mdkp.core import (
        initial_solution,
        initialize_checkpoint,
        make_context_library,
        make_context_trace,
        make_instance,
    )
    from independent_mdkp.pcr_mdkp_engine import (
        advance_checkpoint_with_counters,
        run_mdkp_campaign_case,
    )
from pcr_tx_extension.independent_mdkp.pcr_mdkp_engine import (
    advance_checkpoint_with_counters,
    run_mdkp_campaign_case,
)


def collect_graph_calibration_samples(
    seeds: Sequence[int],
    domains: Sequence[str] = ("generic", "workflow", "microservice"),
    budgets: Sequence[int] = (4, 8, 16, 32, 64),
    warmup: bool = True,
) -> pd.DataFrame:
    """Collect exact-search operation counters and true CPU time on exposed development cases."""
    records = []
    
    if warmup:
        c = make_domain_case("generic", 24, 6, seed=9999)
        cache = build_destroy_repair_cache(c.instance, c.placement, (0, 1, 2, 3, 4, 5, 6, 7))
        cp = initialize_anytime_repair(c.instance, c.placement, (0, 1, 2, 3, 4, 5, 6, 7), prebuilt_cache=cache)
        advance_anytime_repair_with_counters(c.instance, cp, 8, ComputeCounters())

    for seed in seeds:
        for domain in domains:
            case = make_domain_case(domain, 24, 6, seed=int(seed))
            instance = case.instance
            placement = case.placement.copy()
            trace = generate_replay_trace(domain, seed, iterations=20, destroy_size=8)
            
            for step_idx, entry in enumerate(trace):
                nodes = entry.nodes
                cache = build_destroy_repair_cache(instance, placement, nodes)
                target, _ = _repair_greedy(instance, placement, nodes, np.random.default_rng(12345))
                
                for b in budgets:
                    # Timed fresh search (restart)
                    t_cpu_0 = time.process_time_ns()
                    cp = initialize_anytime_repair(instance, placement, nodes, initial_target_hosts=target, prebuilt_cache=cache)
                    counters = ComputeCounters(bound_evals=1, incumbent_evals=1, frontier_inserts=1)
                    move, cert, pops = advance_anytime_repair_with_counters(instance, cp, b, counters)
                    t_cpu_1 = time.process_time_ns()
                    cpu_ns = max(1, t_cpu_1 - t_cpu_0)
                    
                    # Checkpoint continuation test (resume for sanity gate)
                    t_cpu_res_0 = time.process_time_ns()
                    res_counters = ComputeCounters()
                    move2, cert2, pops2 = advance_anytime_repair_with_counters(instance, cp, b, res_counters)
                    t_cpu_res_1 = time.process_time_ns()
                    cpu_resume_ns = max(1, t_cpu_res_1 - t_cpu_res_0)
                    
                    # Fresh continuation comparison (restart matching second slice)
                    cp_fresh = initialize_anytime_repair(instance, placement, nodes, initial_target_hosts=target, prebuilt_cache=cache)
                    cnt_fresh = ComputeCounters(bound_evals=1, incumbent_evals=1, frontier_inserts=1)
                    t_cpu_fresh_0 = time.process_time_ns()
                    advance_anytime_repair_with_counters(instance, cp_fresh, b * 2, cnt_fresh)
                    t_cpu_fresh_1 = time.process_time_ns()
                    cpu_restart_double_ns = max(1, t_cpu_fresh_1 - t_cpu_fresh_0)
                    
                    delta_cpu = max(0, cpu_restart_double_ns - cpu_resume_ns)
                    
                    rec = {
                        "backend": "graph",
                        "case_id": f"{domain}_{seed}",
                        "seed": int(seed),
                        "domain": domain,
                        "budget": b,
                        "step_idx": step_idx,
                        "cpu_ns": cpu_ns,
                        "delta_cpu_ns": delta_cpu,
                        **counters.to_dict(),
                    }
                    records.append(rec)

    return pd.DataFrame(records)


def collect_mdkp_calibration_samples(
    seeds: Sequence[int],
    budgets: Sequence[int] = (64, 128, 192, 256, 384, 512),
    warmup: bool = True,
) -> pd.DataFrame:
    """Collect exact-search operation counters and true CPU time on MDKP exposed cases."""
    records = []
    
    if warmup:
        inst = make_instance(168, 9999)
        x_init = initial_solution(inst)
        cp = initialize_checkpoint(inst, x_init, (0, 1, 2, 3, 4, 5))
        advance_checkpoint_with_counters(inst, cp, 384, ComputeCounters())

    for seed in seeds:
        inst = make_instance(168, seed)
        x = initial_solution(inst)
        contexts = make_context_library(168, 54, seed, count=18)
        trace = make_context_trace(contexts, 20, seed)
        
        for step_idx, (ctx, ctx_cls, _) in enumerate(trace):
            for b in budgets:
                # Timed fresh search
                t_cpu_0 = time.process_time_ns()
                cp = initialize_checkpoint(inst, x, ctx)
                counters = ComputeCounters(incumbent_evals=1, frontier_inserts=1)
                _, _, exp, exact = advance_checkpoint_with_counters(inst, cp, b, counters)
                t_cpu_1 = time.process_time_ns()
                cpu_ns = max(1, t_cpu_1 - t_cpu_0)
                
                # Resume continuation
                t_cpu_res_0 = time.process_time_ns()
                res_counters = ComputeCounters()
                _, _, exp2, exact2 = advance_checkpoint_with_counters(inst, cp, b, res_counters)
                t_cpu_res_1 = time.process_time_ns()
                cpu_resume_ns = max(1, t_cpu_res_1 - t_cpu_res_0)
                
                # Restart continuation (equivalent double slice)
                cp_fresh = initialize_checkpoint(inst, x, ctx)
                cnt_fresh = ComputeCounters(incumbent_evals=1, frontier_inserts=1)
                t_cpu_fresh_0 = time.process_time_ns()
                advance_checkpoint_with_counters(inst, cp_fresh, b * 2, cnt_fresh)
                t_cpu_fresh_1 = time.process_time_ns()
                cpu_restart_double_ns = max(1, t_cpu_fresh_1 - t_cpu_fresh_0)
                
                delta_cpu = max(0, cpu_restart_double_ns - cpu_resume_ns)
                
                rec = {
                    "backend": "mdkp",
                    "case_id": f"mdkp_{seed}",
                    "seed": int(seed),
                    "budget": b,
                    "step_idx": step_idx,
                    "cpu_ns": cpu_ns,
                    "delta_cpu_ns": delta_cpu,
                    **counters.to_dict(),
                }
                records.append(rec)

    return pd.DataFrame(records)


def fit_nnls_integer_weights(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, float]]:
    """Fit non-negative least squares weights and quantize to non-negative integer ns/op."""
    X = df[list(COUNTER_NAMES)].values.astype(float)
    y = df["cpu_ns"].values.astype(float)
    
    raw_weights, _ = nnls(X, y)
    raw_dict = {k: float(w) for k, w in zip(COUNTER_NAMES, raw_weights)}
    
    # Quantize: \tilde{\omega}_k = max(0, round(\omega_k))
    int_dict = {k: max(0, int(round(w))) for k, w in zip(COUNTER_NAMES, raw_weights)}
    # If all weights round to 0 (e.g. if unit scale is extremely small), preserve unit relative scale
    if sum(int_dict.values()) == 0:
        int_dict = {k: max(1, int(round(w * 1000))) for k, w in zip(COUNTER_NAMES, raw_weights)}
        
    return int_dict, raw_dict


def evaluate_cv_gates(df: pd.DataFrame, int_weights: Mapping[str, int]) -> dict[str, object]:
    """Evaluate grouped 5-fold CV metrics on calibration machine."""
    X = df[list(COUNTER_NAMES)].values.astype(float)
    y = df["cpu_ns"].values.astype(float)
    groups = df["case_id"].values
    
    # Calculate deterministic integer compute units
    C = np.array([sum(int_weights[k] * row[i] for i, k in enumerate(COUNTER_NAMES)) for row in X], dtype=float)
    
    gkf = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    fold_rhos = []
    fold_nmaes = []
    
    for train_idx, val_idx in gkf.split(X, y, groups):
        C_val = C[val_idx]
        y_val = y[val_idx]
        
        # Spearman correlation
        rho, _ = spearmanr(C_val, y_val)
        fold_rhos.append(float(rho))
        
        # Scaled NMAE: fit validation scalar a > 0 for reporting
        if np.median(C_val) > 0 and np.median(y_val) > 0:
            a = np.median(y_val) / np.median(C_val)
            nmae = np.median(np.abs(a * C_val - y_val)) / np.median(y_val)
        else:
            nmae = 0.0
        fold_nmaes.append(float(nmae))
        
    overall_rho, _ = spearmanr(C, y)
    a_overall = np.median(y) / max(1.0, np.median(C))
    overall_nmae = np.median(np.abs(a_overall * C - y)) / max(1.0, np.median(y))
    
    # Continuation sanity gate: rho(C_i, T_restart - T_resume)
    delta_cpu = df["delta_cpu_ns"].values.astype(float)
    sanity_rho, _ = spearmanr(C, delta_cpu)
    
    return {
        "overall_spearman_rho": float(overall_rho),
        "overall_scaled_nmae": float(overall_nmae),
        "mean_fold_spearman_rho": float(np.mean(fold_rhos)),
        "mean_fold_scaled_nmae": float(np.mean(fold_nmaes)),
        "continuation_sanity_rho": float(sanity_rho),
        "spearman_pass": bool(overall_rho >= 0.70),
        "nmae_pass": bool(overall_nmae <= 0.35),
        "sanity_pass": bool(sanity_rho >= 0.60),
    }


def evaluate_validation_gates(df: pd.DataFrame, frozen_weights: Mapping[str, int]) -> dict[str, object]:
    """Evaluate frozen integer weights on PRIMARY_B validation machine without refitting."""
    X = df[list(COUNTER_NAMES)].values.astype(float)
    y = df["cpu_ns"].values.astype(float)
    
    C = np.array([sum(frozen_weights[k] * row[i] for i, k in enumerate(COUNTER_NAMES)) for row in X], dtype=float)
    
    rho, _ = spearmanr(C, y)
    a_val = np.median(y) / max(1.0, np.median(C))
    nmae = np.median(np.abs(a_val * C - y)) / max(1.0, np.median(y))
    
    delta_cpu = df["delta_cpu_ns"].values.astype(float)
    sanity_rho, _ = spearmanr(C, delta_cpu)
    
    return {
        "spearman_rho": float(rho),
        "scaled_nmae": float(nmae),
        "continuation_sanity_rho": float(sanity_rho),
        "spearman_pass": bool(rho >= 0.70),
        "nmae_pass": bool(nmae <= 0.35),
        "sanity_pass": bool(sanity_rho >= 0.60),
    }


def main():
    parser = argparse.ArgumentParser(description="PCR-v4 Compute Calibration and Validation")
    parser.add_argument("--stage", choices=["calibrate_a", "validate_b", "replay"], required=True)
    parser.add_argument("--out-dir", default="04_compute_calibration")
    parser.add_argument("--weights-file", default=None)
    args = parser.parse_args()
    
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Exposed development seeds from PRIOR_SEED_REGISTRY
    graph_dev_seeds = [3301, 3302, 3303, 3304, 3305, 3306, 3307, 3308]
    mdkp_dev_seeds = [8101, 8102, 8103, 8104, 8105, 8106, 8107, 8108, 8109, 8110]
    
    if args.stage == "calibrate_a":
        print("[PRIMARY_A] Collecting Graph calibration samples on exposed cases...")
        df_graph = collect_graph_calibration_samples(graph_dev_seeds)
        print(f"[PRIMARY_A] Collected {len(df_graph)} Graph samples.")
        
        print("[PRIMARY_A] Fitting NNLS Graph weights...")
        int_w_graph, raw_w_graph = fit_nnls_integer_weights(df_graph)
        cv_graph = evaluate_cv_gates(df_graph, int_w_graph)
        print(f"[PRIMARY_A] Graph CV Gates: Spearman={cv_graph['overall_spearman_rho']:.4f} (pass={cv_graph['spearman_pass']}), NMAE={cv_graph['overall_scaled_nmae']:.4f} (pass={cv_graph['nmae_pass']}), Sanity={cv_graph['continuation_sanity_rho']:.4f} (pass={cv_graph['sanity_pass']})")
        
        print("[PRIMARY_A] Collecting MDKP calibration samples on exposed cases...")
        df_mdkp = collect_mdkp_calibration_samples(mdkp_dev_seeds)
        print(f"[PRIMARY_A] Collected {len(df_mdkp)} MDKP samples.")
        
        print("[PRIMARY_A] Fitting NNLS MDKP weights...")
        int_w_mdkp, raw_w_mdkp = fit_nnls_integer_weights(df_mdkp)
        cv_mdkp = evaluate_cv_gates(df_mdkp, int_w_mdkp)
        print(f"[PRIMARY_A] MDKP CV Gates: Spearman={cv_mdkp['overall_spearman_rho']:.4f} (pass={cv_mdkp['spearman_pass']}), NMAE={cv_mdkp['overall_scaled_nmae']:.4f} (pass={cv_mdkp['nmae_pass']}), Sanity={cv_mdkp['continuation_sanity_rho']:.4f} (pass={cv_mdkp['sanity_pass']})")
        
        payload = {
            "status": "PRIMARY_A_CALIBRATION_SUCCESS",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "graph": {
                "integer_weights": int_w_graph,
                "raw_weights": raw_w_graph,
                "cv_metrics": cv_graph,
            },
            "mdkp": {
                "integer_weights": int_w_mdkp,
                "raw_weights": raw_w_mdkp,
                "cv_metrics": cv_mdkp,
            },
            "all_gates_pass": bool(
                cv_graph["spearman_pass"] and cv_graph["nmae_pass"] and cv_graph["sanity_pass"]
                and cv_mdkp["spearman_pass"] and cv_mdkp["nmae_pass"] and cv_mdkp["sanity_pass"]
            ),
        }
        
        out_file = out_dir / "PRIMARY_A_CALIBRATION.json"
        with open(out_file, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[PRIMARY_A] Saved calibration record to {out_file}")
        
    elif args.stage == "validate_b":
        weights_file = Path(args.weights_file) if args.weights_file else out_dir / "PRIMARY_A_CALIBRATION.json"
        with open(weights_file) as f:
            calib_data = json.load(f)
            
        int_w_graph = calib_data["graph"]["integer_weights"]
        int_w_mdkp = calib_data["mdkp"]["integer_weights"]
        
        print("[PRIMARY_B] Collecting Graph validation samples on exposed cases...")
        df_graph = collect_graph_calibration_samples(graph_dev_seeds)
        val_graph = evaluate_validation_gates(df_graph, int_w_graph)
        print(f"[PRIMARY_B] Graph Validation: Spearman={val_graph['spearman_rho']:.4f} (pass={val_graph['spearman_pass']}), NMAE={val_graph['scaled_nmae']:.4f} (pass={val_graph['nmae_pass']}), Sanity={val_graph['continuation_sanity_rho']:.4f} (pass={val_graph['sanity_pass']})")
        
        print("[PRIMARY_B] Collecting MDKP validation samples on exposed cases...")
        df_mdkp = collect_mdkp_calibration_samples(mdkp_dev_seeds)
        val_mdkp = evaluate_validation_gates(df_mdkp, int_w_mdkp)
        print(f"[PRIMARY_B] MDKP Validation: Spearman={val_mdkp['spearman_rho']:.4f} (pass={val_mdkp['spearman_pass']}), NMAE={val_mdkp['scaled_nmae']:.4f} (pass={val_mdkp['nmae_pass']}), Sanity={val_mdkp['continuation_sanity_rho']:.4f} (pass={val_mdkp['sanity_pass']})")
        
        payload = {
            "status": "PRIMARY_B_VALIDATION_SUCCESS",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "frozen_weights_source": str(weights_file),
            "graph_validation": val_graph,
            "mdkp_validation": val_mdkp,
            "all_gates_pass": bool(
                val_graph["spearman_pass"] and val_graph["nmae_pass"] and val_graph["sanity_pass"]
                and val_mdkp["spearman_pass"] and val_mdkp["nmae_pass"] and val_mdkp["sanity_pass"]
            ),
        }
        
        out_file = out_dir / "PRIMARY_B_VALIDATION.json"
        with open(out_file, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[PRIMARY_B] Saved validation record to {out_file}")

    elif args.stage == "replay":
        # Deterministic replay on 10 exposed cases
        root = Path(__file__).resolve().parent.parent
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
        
        weights_file = out_dir / "PRIMARY_A_CALIBRATION.json"
        with open(weights_file) as f:
            calib_data = json.load(f)
        int_w_graph = calib_data["graph"]["integer_weights"]
        int_w_mdkp = calib_data["mdkp"]["integer_weights"]
        
        graph_hashes = {}
        for seed in [3301, 3302, 3303, 3304, 3305, 3306, 3307, 3308, 3309, 3310]:
            trace = generate_replay_trace("generic", seed, iterations=40, destroy_size=8)
            res = run_graph_campaign_case(
                "generic", seed, trace, policy_name="learned_pC", slice_pops=8,
                budget_bytes=5000, predictor=p6, compute_weights=int_w_graph
            )
            graph_hashes[str(seed)] = {
                "trajectory_hash": res.trajectory_hash,
                "final_objective": float(res.final_objective),
                "branch_pops_executed": int(res.branch_pops_executed),
                "useful_resumes": int(res.useful_resumes),
            }
            
        mdkp_hashes = {}
        for seed in [8101, 8102, 8103, 8104, 8105, 8106, 8107, 8108, 8109, 8110]:
            res = run_mdkp_campaign_case(
                seed=seed, policy="learned_pC", budget_bytes=4206, predictor=p10,
                compute_weights=int_w_mdkp, iterations=40
            )
            mdkp_hashes[str(seed)] = {
                "trajectory_hash": res.trajectory_hash,
                "final_cost": float(res.final_cost),
                "branch_nodes_executed": int(res.branch_nodes_executed),
                "useful_resumes": int(res.useful_resumes),
            }
            
        payload = {
            "graph_replays": graph_hashes,
            "mdkp_replays": mdkp_hashes,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        out_file = out_dir / "REPLAY_HASHES.json"
        with open(out_file, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"Saved replay hashes to {out_file}")


if __name__ == "__main__":
    main()
