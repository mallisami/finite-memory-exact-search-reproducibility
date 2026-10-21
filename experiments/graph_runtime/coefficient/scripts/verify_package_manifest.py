#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]; man=json.load(open(ROOT/'10_VERIFICATION'/'IMMUTABLE_MANIFEST_SHA256.json')); bad=[]
for r in man:
 p=ROOT/r['path']
 if not p.exists(): bad.append(f"missing {r['path']}"); continue
 if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']: bad.append(f"hash mismatch {r['path']}")
print(json.dumps({'status':'PASS' if not bad else 'FAIL','checked':len(man),'errors':bad},indent=2)); raise SystemExit(0 if not bad else 2)
