#!/usr/bin/env python3
import argparse,csv,json
ap=argparse.ArgumentParser();ap.add_argument("--schedule",required=True);ap.add_argument("--wal",required=True);a=ap.parse_args()
sched=list(csv.DictReader(open(a.schedule,newline="",encoding="utf-8")))
wal=list(csv.DictReader(open(a.wal,newline="",encoding="utf-8")))
need={r["run_id"] for r in sched}
valid={}
for r in wal:
    if r.get("technical_valid","").lower() in ("1","true","yes") and r.get("status","").upper()=="SUCCESS":
        valid.setdefault(r["run_id"],[]).append(r)
missing=sorted(need-set(valid))
dups=sorted(k for k,v in valid.items() if len(v)>1)
extra=sorted(set(valid)-need)
out={"scheduled":len(need),"valid_completed":len(set(valid)&need),"missing":missing,"duplicate_valid":dups,"extra_valid":extra,"pass":not missing and not dups and not extra}
print(json.dumps(out,indent=2))
raise SystemExit(0 if out["pass"] else 2)
