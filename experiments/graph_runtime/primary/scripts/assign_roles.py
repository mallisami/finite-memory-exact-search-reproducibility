#!/usr/bin/env python3
import json, sys, re
from pathlib import Path
if len(sys.argv)!=3:
    raise SystemExit("usage: assign_roles.py <inventory_dir> <output.json>")
indir=Path(sys.argv[1]); out=Path(sys.argv[2])
nodes=[]
for alias in ("rack-a","rack-b","rack-c"):
    p=indir/f"{alias}.json"
    if not p.exists(): raise SystemExit(f"missing {p}")
    d=json.loads(p.read_text()); d["alias"]=alias; nodes.append(d)
prim=[n for n in nodes if n.get("vcpu")==4 and n.get("mem_total_gib") and 13.5<=n["mem_total_gib"]<=18.5]
sec=[n for n in nodes if n.get("vcpu")==2 and n.get("mem_total_gib") and 6.0<=n["mem_total_gib"]<=10.5]
if len(prim)!=2 or len(sec)!=1:
    raise SystemExit(f"unexpected hardware classes: {[(n['alias'],n.get('vcpu'),n.get('mem_total_gib')) for n in nodes]}")
prim=sorted(prim,key=lambda x:x["alias"])
def burstable(n):
    size=(n.get("azure") or {}).get("vmSize") or ""
    return bool(re.search(r"(^|_)B\\d|Standard_B", size, re.I))
blocked=[n["alias"] for n in prim if burstable(n)]
role={
    "PRIMARY_A":prim[0]["alias"],"PRIMARY_B":prim[1]["alias"],"CONTROL_SECONDARY":sec[0]["alias"],
    "primary_timing_blocked":bool(blocked),
    "block_reason":f"burstable Azure primary VM(s): {blocked}" if blocked else None,
    "hardware":{n["alias"]:{
        "vcpu":n["vcpu"],"mem_total_gib":n["mem_total_gib"],"os_release":n.get("os_release"),
        "kernel":n.get("kernel"),"cpu_model":n.get("cpu_model"),"clocksource":n.get("clocksource"),
        "boot_id":n.get("boot_id"),"azure_vm_size":(n.get("azure") or {}).get("vmSize")
    } for n in nodes},
    "rule":"two 4-vCPU/~16-GiB nodes primary; one 2-vCPU/~8-GiB control; primary A/B lexical by alias"
}
out.write_text(json.dumps(role,indent=2,sort_keys=True)+"\n")
print(json.dumps(role,indent=2,sort_keys=True))
if blocked:
    raise SystemExit(3)
