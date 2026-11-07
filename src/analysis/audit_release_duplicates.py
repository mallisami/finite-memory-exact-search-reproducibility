#!/usr/bin/env python3
"""Read-only exact-file duplication report; never deletes frozen evidence."""
from pathlib import Path
from collections import defaultdict
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
m=defaultdict(list)
for p in ROOT.rglob("*"):
    if not p.is_file() or {".git","__pycache__",".pytest_cache"}&set(p.parts):
        continue
    rel=p.relative_to(ROOT).as_posix()
    if rel.startswith("results/reproduced/"):continue
    m[hashlib.sha256(p.read_bytes()).hexdigest()].append((rel,p.stat().st_size))
dups=[v for v in m.values() if len(v)>1]
print(json.dumps({"groups":len(dups),
    "additional_paths":sum(len(v)-1 for v in dups),
    "repeated_uncompressed_bytes":sum(v[0][1]*(len(v)-1) for v in dups),
    "groups_detail":[{"paths":[p for p,_ in v],"bytes_each":v[0][1]} for v in dups]},
    indent=2))
print("Exact blobs are deduplicated by Git; do not delete distinct scientific paths by hash alone.")
