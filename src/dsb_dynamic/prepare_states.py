from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .workload_tools import load_config, p95

APPS=("socialNetwork","hotelReservation","mediaMicroservices")
REGIMES=("step","burst","ramp")


def read_edges(path: Path, nodes: list[str]) -> np.ndarray:
    idx={s:i for i,s in enumerate(nodes)}; m=np.zeros((len(nodes),len(nodes)),dtype=float)
    with path.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            a,b=r["src"],r["dst"]
            if a in idx and b in idx and a!=b: m[idx[a],idx[b]] += float(r["mb_per_s"])
    return m


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--config",required=True);ap.add_argument("--mode",choices=["primary","second-host"],default="primary")
    a=ap.parse_args();root=Path(a.root);cfg=load_config(Path(a.config));m=cfg["measurement"]
    measurement=root/"results/measurement"; prepared=root/"results/prepared"
    if prepared.exists():
        # Prepared inputs are immutable once the gate passes; explicit deletion is required to rebuild.
        if (prepared/"PREPARED_GATE_PASS.json").is_file():
            print((prepared/"PREPARED_GATE_PASS.json").read_text()); return
        import shutil; shutil.rmtree(prepared)
    prepared.mkdir(parents=True)
    state_files=sorted(measurement.glob("*/sequences/*/state_*/STATE.json"))
    reps=10 if a.mode=="primary" else int(cfg["second_environment_subset"]["repetitions_per_application"])
    regimes=list(REGIMES) if a.mode=="primary" else [cfg["second_environment_subset"]["regime"]]
    expected=len(APPS)*len(regimes)*reps*10
    if len(state_files)!=expected:
        raise RuntimeError(f"incomplete measured campaign: expected {expected} states, found {len(state_files)}")

    records=[]; nodes_by_app={}; stats_by_app=defaultdict(lambda:defaultdict(lambda:{"cpu":[],"mem":[]}))
    for sf in state_files:
        meta=json.loads(sf.read_text()); app=meta["app"]
        if meta["regime"] not in regimes or int(meta["repetition"])>reps: continue
        nodes=sorted(meta["included_services"])
        if app in nodes_by_app and nodes_by_app[app]!=nodes: raise RuntimeError(f"component set changed during measurement for {app}")
        nodes_by_app[app]=nodes
        sd=sf.parent; matrix=read_edges(sd/"edges.csv",nodes)
        if float(matrix.sum())<=0: raise RuntimeError(f"zero internal traffic: {sd}")
        records.append({**meta,"state_dir":str(sd),"matrix":matrix})
        with (sd/"stats.csv").open(newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                svc=r["service"]
                if svc not in nodes: continue
                try:
                    c=float(r["cpu_cores"]); mm=float(r["memory_mb"])
                    if np.isfinite(c): stats_by_app[app][svc]["cpu"].append(c)
                    if np.isfinite(mm): stats_by_app[app][svc]["mem"].append(mm)
                except Exception: pass
    if len(records)!=expected: raise RuntimeError(f"filtered state count mismatch: {len(records)} vs {expected}")

    # Construct-validation gate before any solver execution.
    good=[]; val_rows=[]
    for r in records:
        ok=(float(r["achieved_fraction"])>=float(m["construct_state_achieved_fraction_min"]) and
            float(r["non2xx_fraction"])<=float(m["construct_state_non2xx_fraction_max"]) and
            float(r.get("socket_error_fraction",0.0))<=0.02 and float(r["matrix"].sum())>0)
        good.append(ok)
        val_rows.append({"app":r["app"],"sequence":r["sequence"],"regime":r["regime"],"repetition":r["repetition"],
                         "state_index":r["state_index"],"profile":r["profile"],"requested_rps":r["requested_rps"],
                         "achieved_rps":r["achieved_rps"],"achieved_fraction":r["achieved_fraction"],
                         "p99_ms":r["p99_ms"],"non2xx_fraction":r["non2xx_fraction"],
                         "socket_error_fraction":r.get("socket_error_fraction",0.0),"total_internal_mb_per_s":float(r["matrix"].sum()),"state_good":int(ok)})
    overall_good=float(np.mean(good))
    if overall_good<float(m["construct_good_state_fraction_min"]): raise RuntimeError(f"construct gate failed: only {overall_good:.3f} good states")
    app_ratios={}
    if a.mode=="primary":
        for app in APPS:
            x=[r for r in records if r["app"]==app and r["regime"] in ("step","burst")]
            lo=[float(r["matrix"].sum()) for r in x if r["profile"]=="L"]
            hi=[float(r["matrix"].sum()) for r in x if r["profile"]=="H"]
            if not lo or not hi: raise RuntimeError(f"missing low/high construct cells for {app}")
            ratio=float(np.median(hi)/max(np.median(lo),1e-12));app_ratios[app]=ratio
            if ratio<float(m["construct_high_low_internal_byte_ratio_min"]): raise RuntimeError(f"construct gate failed for {app}: high/low internal-byte ratio {ratio:.3f}")

    # Freeze one fixed demand vector per application using the complete pre-outcome measurement campaign.
    demands_by_app={}
    for app,nodes in nodes_by_app.items():
        arr=[]; outrows=[]
        for svc in nodes:
            d=stats_by_app[app][svc]
            if not d["cpu"] or not d["mem"]: raise RuntimeError(f"missing resource samples for {app}/{svc}")
            cpu=max(0.05,p95(d["cpu"])); mem_mb=max(32.0,p95(d["mem"]))
            arr.append([cpu,mem_mb/1024.0])
            outrows.append({"service":svc,"cpu_cores_p95_floor":cpu,"memory_gb_p95_floor":mem_mb/1024.0,"samples":min(len(d["cpu"]),len(d["mem"]))})
        demands_by_app[app]=np.asarray(arr,dtype=float)
        dd=prepared/"demands";dd.mkdir(parents=True,exist_ok=True)
        with (dd/f"{app}.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(outrows[0]));w.writeheader();w.writerows(outrows)

    # Canonicalize repeated commanded profiles within each independently measured sequence.
    grouped=defaultdict(list)
    for r in records: grouped[r["sequence"]].append(r)
    manifest=[]; canonical_errors=[]
    seqdir=prepared/"sequences";seqdir.mkdir(parents=True,exist_ok=True)
    for seq,rs in sorted(grouped.items()):
        rs=sorted(rs,key=lambda z:int(z["state_index"]))
        if len(rs)!=10 or [int(x["state_index"]) for x in rs]!=list(range(10)): raise RuntimeError(f"bad state index set for {seq}")
        app=rs[0]["app"]; regime=rs[0]["regime"]; rep=int(rs[0]["repetition"]);nodes=nodes_by_app[app]
        byprof=defaultdict(list)
        for r in rs: byprof[r["profile"]].append(r["matrix"])
        canon={p:np.mean(np.stack(ms),axis=0) for p,ms in byprof.items()}
        mats=[];raw=[];rates=[];profiles=[]
        for r in rs:
            c=canon[r["profile"]]; mats.append(c);raw.append(r["matrix"]);rates.append(float(r["requested_rps"]));profiles.append(r["profile"])
            denom=max(float(np.linalg.norm(r["matrix"])),1e-12);canonical_errors.append(float(np.linalg.norm(r["matrix"]-c))/denom)
        path=seqdir/f"{seq}.npz"
        np.savez_compressed(path,interaction=np.stack(mats),raw_interaction=np.stack(raw),demands=demands_by_app[app],nodes=np.asarray(nodes),
                            requested_rps=np.asarray(rates),profiles=np.asarray(profiles),state_index=np.arange(10,dtype=int))
        manifest.append({"sequence":seq,"app":app,"regime":regime,"repetition":rep,"path":str(path.relative_to(root)),"n_nodes":len(nodes)})
    manifest_path=prepared/"sequence_manifest.csv"
    with manifest_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    with (prepared/"construct_validation.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(val_rows[0]));w.writeheader();w.writerows(val_rows)
    gate={"mode":a.mode,"expected_states":expected,"observed_states":len(records),"good_state_fraction":overall_good,
          "high_low_internal_byte_ratios":app_ratios,"median_raw_to_canonical_relative_frobenius_error":float(np.median(canonical_errors)),
          "sequence_count":len(manifest),"gate":"PASS"}
    (prepared/"CONSTRUCT_VALIDATION.json").write_text(json.dumps(gate,indent=2),encoding="utf-8")

    # Freeze all solver inputs with hashes before outcomes are allowed.
    hash_rows=[]
    for p in sorted([manifest_path,*seqdir.glob("*.npz"),*(prepared/"demands").glob("*.csv"),prepared/"CONSTRUCT_VALIDATION.json"]):
        hash_rows.append({"path":str(p.relative_to(root)),"sha256":sha256(p),"bytes":p.stat().st_size})
    with (prepared/"FROZEN_INPUTS_SHA256.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(hash_rows[0]));w.writeheader();w.writerows(hash_rows)
    (prepared/"PREPARED_GATE_PASS.json").write_text(json.dumps(gate,indent=2),encoding="utf-8")
    print(json.dumps(gate,indent=2))

if __name__=="__main__": main()
