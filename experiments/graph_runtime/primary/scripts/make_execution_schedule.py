#!/usr/bin/env python3
import argparse,csv,hashlib
from pathlib import Path
POL=["restart","empirical_pW","learned_pW","empirical_pC","learned_pC"]
ap=argparse.ArgumentParser();ap.add_argument("--shard",required=True);ap.add_argument("--levels",default="L1,L2,L3,L4");ap.add_argument("--out",required=True);a=ap.parse_args()
rows=list(csv.DictReader(open(a.shard,newline="",encoding="utf-8")))
levels=a.levels.split(",")
out=[]
for r in rows:
    levs=levels if r["domain"].lower()=="graph" else ["MDKP"]
    for lev in levs:
        key=f"{r['case_id']}|{lev}"
        off=int.from_bytes(hashlib.sha256(key.encode()).digest()[:4],"big")%5
        for rep in range(5):
            rot=(off+rep)%5
            order=POL[rot:]+POL[:rot]
            for pos,p in enumerate(order):
                run_id=f"{r['case_id']}__{lev}__r{rep}__p{pos}__{p}"
                out.append({**r,"level":lev,"repeat":rep,"position":pos,"policy":p,"run_id":run_id})
fields=sorted(set().union(*(x.keys() for x in out)))
with open(a.out,"w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
print(f"{a.out}: {len(out)} scheduled timed executions")
