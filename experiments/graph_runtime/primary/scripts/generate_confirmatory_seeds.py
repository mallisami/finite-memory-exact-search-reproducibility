#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument("--protocol-hash",required=True)
ap.add_argument("--prior",required=True)
ap.add_argument("--out",required=True)
a=ap.parse_args()
prior=json.loads(Path(a.prior).read_text())
used=set()
def walk(x):
    if isinstance(x,list):
        for v in x:
            if isinstance(v,int): used.add(v)
    elif isinstance(x,dict):
        for v in x.values(): walk(v)
walk(prior)
def derive(tag,i):
    nonce=0
    while True:
        s=f"PCR-TX-V4|{a.protocol_hash}|{tag}|{i}|{nonce}".encode()
        x=int.from_bytes(hashlib.sha256(s).digest()[:4],"big") & 0x7fffffff
        if x not in used and x!=0:
            used.add(x); return x
        nonce+=1
graph={}
for fam in ("Generic","Workflow","Microservice"):
    graph[fam]=[derive(f"graph:{fam}",i) for i in range(20)]
mdkp=[derive("mdkp",i) for i in range(80)]
out={"protocol_hash":a.protocol_hash,"graph":graph,"mdkp":mdkp}
Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(a.out)
