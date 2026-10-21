#!/usr/bin/env python3
import importlib.metadata as md, json, platform
wanted=["numpy","scipy","scikit-learn","pandas","matplotlib","joblib","threadpoolctl","aiohttp","pytest","psutil","pyyaml","jsonschema"]
pk={}
for n in wanted:
    try: pk[n]=md.version(n)
    except Exception: pk[n]=None
print(json.dumps({"python":platform.python_version(),"implementation":platform.python_implementation(),"packages":pk},indent=2,sort_keys=True))
