#!/usr/bin/env python3
import argparse,csv,json,re
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument("--manifest",required=True);ap.add_argument("--roles",required=True);ap.add_argument("--out",required=True)
a=ap.parse_args()
roles=json.loads(Path(a.roles).read_text()); A=roles["PRIMARY_A"];B=roles["PRIMARY_B"]
rows=list(csv.DictReader(open(a.manifest,newline="",encoding="utf-8")))
required={"case_id","domain","family","sha256"}
if not rows or not required.issubset(rows[0]): raise SystemExit(f"manifest requires {sorted(required)}")
if len({r["case_id"] for r in rows})!=len(rows): raise SystemExit("duplicate case_id")
if len({r["sha256"].lower() for r in rows})!=len(rows): raise SystemExit("duplicate case sha256")
for r in rows:
    r["sha256"]=r["sha256"].lower()
    if not re.fullmatch(r"[0-9a-f]{64}",r["sha256"]): raise SystemExit(f"bad sha256: {r['case_id']}")
graph=[r for r in rows if r["domain"].lower()=="graph"]; mdkp=[r for r in rows if r["domain"].lower()=="mdkp"]
if len(graph)!=60 or len(mdkp)!=80: raise SystemExit(f"expected 60 graph + 80 mdkp, got {len(graph)} + {len(mdkp)}")
assign=[]
for fam in ("Generic","Workflow","Microservice"):
    z=sorted([r for r in graph if r["family"]==fam],key=lambda r:r["sha256"])
    if len(z)!=20: raise SystemExit(f"{fam}: expected 20 got {len(z)}")
    for i,r in enumerate(z):
        q=dict(r);q["primary_machine"]=A if i%2==0 else B;assign.append(q)
z=sorted(mdkp,key=lambda r:r["sha256"])
for i,r in enumerate(z):
    q=dict(r);q["primary_machine"]=A if i%2==0 else B;assign.append(q)
out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
fields=sorted(set().union(*(x.keys() for x in assign)))
def write(name,data):
    with open(out/name,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
write("assignment.csv",assign)
for host in (A,B): write(f"{host}.csv",[x for x in assign if x["primary_machine"]==host])
# profiling subset: 10 lowest hash per domain per primary
prof=[]
for host in (A,B):
    for dom in ("graph","mdkp"):
        q=sorted([x for x in assign if x["primary_machine"]==host and x["domain"].lower()==dom],key=lambda x:x["sha256"])[:10]
        for x in q:
            y=dict(x);y["subset"]="profiling";prof.append(y)
# secondary graph family-balanced: A gets 4G/3W/3M; B gets 3G/4W/3M
secondary=[]
targets={A:{"Generic":4,"Workflow":3,"Microservice":3},B:{"Generic":3,"Workflow":4,"Microservice":3}}
for host,t in targets.items():
    for fam,n in t.items():
        q=sorted([x for x in assign if x["primary_machine"]==host and x["domain"].lower()=="graph" and x["family"]==fam],key=lambda x:x["sha256"])[:n]
        for x in q:
            y=dict(x);y["subset"]="secondary_graph";secondary.append(y)
for host in (A,B):
    q=sorted([x for x in assign if x["primary_machine"]==host and x["domain"].lower()=="mdkp"],key=lambda x:x["sha256"])[:10]
    for x in q:
        y=dict(x);y["subset"]="secondary_mdkp";secondary.append(y)
# subset files need union fields
sfields=sorted(set().union(*(x.keys() for x in prof+secondary)))
for name,data in [("profiling_subset.csv",prof),("secondary_subset.csv",secondary)]:
    with open(out/name,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=sfields);w.writeheader();w.writerows(data)
# audits
for host in (A,B):
    g=[x for x in assign if x["primary_machine"]==host and x["domain"].lower()=="graph"]
    m=[x for x in assign if x["primary_machine"]==host and x["domain"].lower()=="mdkp"]
    fam={f:sum(x["family"]==f for x in g) for f in ("Generic","Workflow","Microservice")}
    assert len(g)==30 and len(m)==40 and all(v==10 for v in fam.values())
assert sum(x["subset"]=="secondary_graph" for x in secondary)==20
assert sum(x["subset"]=="secondary_mdkp" for x in secondary)==20
print(json.dumps({"PRIMARY_A":A,"PRIMARY_B":B,"rows":len(assign),"profiling":len(prof),"secondary":len(secondary)},indent=2))
