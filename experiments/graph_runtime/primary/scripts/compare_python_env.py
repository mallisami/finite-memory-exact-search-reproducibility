#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
if len(sys.argv)!=2: raise SystemExit("usage: compare_python_env.py expected.json")
exp=json.loads(Path(sys.argv[1]).read_text())
act=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).with_name("capture_python_env.py"))],text=True))
diff=[]
if exp["python"]!=act["python"]: diff.append(["python",exp["python"],act["python"]])
for k,v in exp["packages"].items():
    if act["packages"].get(k)!=v: diff.append([k,v,act["packages"].get(k)])
print(json.dumps({"status":"PASS" if not diff else "FAIL","differences":diff,"actual":act},indent=2))
raise SystemExit(0 if not diff else 2)
