#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--files",nargs="+",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
root=Path(a.root)
d={}
for rel in a.files:
    p=root/rel
    if not p.is_file(): raise SystemExit(f"missing {p}")
    d[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
payload={"status":"FROZEN_BEFORE_CONFIRMATORY_CASE_GENERATION","root":str(root),"sha256":d}
Path(a.out).write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
print(a.out)
