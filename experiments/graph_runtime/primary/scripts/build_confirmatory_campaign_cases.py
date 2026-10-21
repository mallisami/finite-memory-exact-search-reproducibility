"""Phase 7: Deterministic Confirmatory Case Generation and Sharding.

1. Calculates SHA-256 digest of docs/02_MASTER_ONE_SHOT_PROTOCOL_V4.md.
2. Runs generate_confirmatory_seeds.py to produce 60 Graph + 80 MDKP untouched seeds.
3. Constructs the instance objects and calculates SHA-256 fingerprints for each case.
4. Writes 07_confirmatory_cases/confirmatory_cases.csv.
5. Runs make_case_shards.py to produce deterministic primary shards and profiling/secondary subsets.
6. Generates execution schedules for PRIMARY_A and PRIMARY_B with counterbalanced 5-repeat rotations.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_EXT = _ROOT / "pcr_tx_extension"
if str(_EXT) not in sys.path:
    sys.path.insert(0, str(_EXT))

from pcr_tx_extension.certified_assignment.domain_instances import make_domain_case
from pcr_tx_extension.certified_assignment.paper2_online_pilot import generate_replay_trace
from pcr_tx_extension.independent_mdkp.core import make_instance, make_context_library, make_context_trace


def main():
    root = Path(_ROOT)
    protocol_file = root / "docs" / "02_MASTER_ONE_SHOT_PROTOCOL_V4.md"
    protocol_hash = hashlib.sha256(protocol_file.read_bytes()).hexdigest()
    print(f"Authoritative Protocol V4 SHA-256: {protocol_hash}")
    
    cases_dir = root / "07_confirmatory_cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    seeds_file = cases_dir / "CONFIRMATORY_SEEDS.json"
    
    # 1. Deterministically derive untouched seeds
    cmd_seeds = [
        sys.executable,
        str(root / "scripts" / "generate_confirmatory_seeds.py"),
        "--protocol-hash", protocol_hash,
        "--prior", str(root / "config" / "PRIOR_SEED_REGISTRY.json"),
        "--out", str(seeds_file),
    ]
    subprocess.run(cmd_seeds, check=True)
    
    with open(seeds_file) as f:
        seeds_data = json.load(f)
        
    rows = []
    
    # 2. Build 60 Graph cases (20 Generic, 20 Workflow, 20 Microservice)
    for fam in ("Generic", "Workflow", "Microservice"):
        fam_seeds = seeds_data["graph"][fam]
        for idx, seed in enumerate(fam_seeds):
            case_id = f"graph_{fam.lower()}_{idx:02d}_{seed}"
            domain_name = fam.lower()
            case_obj = make_domain_case(domain_name, 24, 6, seed=int(seed))
            trace = generate_replay_trace(domain_name, seed, iterations=200, destroy_size=12)
            
            # Case fingerprint covering interaction matrix, capacities, demands, and trace
            hasher = hashlib.sha256()
            hasher.update(case_obj.instance.interaction.tobytes())
            hasher.update(case_obj.instance.capacities.tobytes())
            hasher.update(case_obj.instance.demands.tobytes())
            hasher.update(case_obj.placement.tobytes())
            for t in trace:
                hasher.update(f"{t.nodes}:{t.destroy_op_index}:".encode())
            case_sha256 = hasher.hexdigest()
            
            rows.append({
                "case_id": case_id,
                "domain": "graph",
                "family": fam,
                "seed": int(seed),
                "sha256": case_sha256,
            })
            
    # 3. Build 80 MDKP cases
    for idx, seed in enumerate(seeds_data["mdkp"]):
        case_id = f"mdkp_{idx:02d}_{seed}"
        inst = make_instance(168, seed, n_dims=3)
        contexts = make_context_library(168, 54, seed, count=18)
        trace = make_context_trace(contexts, 200, seed)
        
        hasher = hashlib.sha256()
        hasher.update(inst.profits.tobytes())
        hasher.update(inst.weights.tobytes())
        hasher.update(inst.capacities.tobytes())
        for c in contexts:
            hasher.update(str(c).encode())
        for t in trace:
            hasher.update(f"{t[0]}:{t[1]}:{t[2]:.6f}:".encode())
        case_sha256 = hasher.hexdigest()
        
        rows.append({
            "case_id": case_id,
            "domain": "mdkp",
            "family": "MDKP",
            "seed": int(seed),
            "sha256": case_sha256,
        })
        
    manifest_csv = cases_dir / "confirmatory_cases.csv"
    with open(manifest_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "domain", "family", "seed", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} confirmatory cases manifest to {manifest_csv}")
    
    # 4. Run make_case_shards.py
    shards_dir = root / "08_case_shards"
    shards_dir.mkdir(parents=True, exist_ok=True)
    cmd_shards = [
        sys.executable,
        str(root / "scripts" / "make_case_shards.py"),
        "--manifest", str(manifest_csv),
        "--roles", str(root / "ROLE_ASSIGNMENT.json"),
        "--out", str(shards_dir),
    ]
    subprocess.run(cmd_shards, check=True)
    
    # 5. Read roles and generate execution schedules
    with open(root / "ROLE_ASSIGNMENT.json") as f:
        roles = json.load(f)
    host_a = roles["PRIMARY_A"]
    host_b = roles["PRIMARY_B"]
    
    cmd_sched_a = [
        sys.executable,
        str(root / "scripts" / "make_execution_schedule.py"),
        "--shard", str(shards_dir / f"{host_a}.csv"),
        "--levels", "L1,L2,L3,L4",
        "--out", str(shards_dir / f"{host_a}_schedule.csv"),
    ]
    subprocess.run(cmd_sched_a, check=True)
    
    cmd_sched_b = [
        sys.executable,
        str(root / "scripts" / "make_execution_schedule.py"),
        "--shard", str(shards_dir / f"{host_b}.csv"),
        "--levels", "L1,L2,L3,L4",
        "--out", str(shards_dir / f"{host_b}_schedule.csv"),
    ]
    subprocess.run(cmd_sched_b, check=True)
    
    print("\nCONFIRMATORY_CASES_AND_SCHEDULES_INITIALIZED_SUCCESS")


if __name__ == "__main__":
    main()
