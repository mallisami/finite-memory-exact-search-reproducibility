#!/usr/bin/env python3
import hashlib,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ledger=root/"SHA256SUMS.txt"
bad=[]
for line in ledger.read_text().splitlines():
    if not line.strip(): continue
    h,rel=line.split("  ",1); p=root/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(rel)
print(f"checked={len(ledger.read_text().splitlines())} bad={len(bad)}")
if bad:
    print("\n".join(bad));raise SystemExit(2)
print("PACKAGE_INTEGRITY_PASS")
