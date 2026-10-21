#!/usr/bin/env python3
import importlib,sys,json
EXPECTED={'numpy':'2.3.5','scipy':'1.17.0','sklearn':'1.8.0','pandas':'2.2.3','matplotlib':'3.10.8','joblib':'1.5.3','threadpoolctl':'3.6.0','aiohttp':'3.13.3','pytest':'9.0.2'}
actual={}; bad=[]
if sys.version_info[:2] != (3,12): bad.append(f'Python 3.12.x required, got {sys.version.split()[0]}')
for mod,want in EXPECTED.items():
    m=importlib.import_module(mod); got=getattr(m,'__version__','unknown'); actual[mod]=got
    if got!=want: bad.append(f'{mod}: expected {want}, got {got}')
print(json.dumps({'python':sys.version,'packages':actual,'status':'PASS' if not bad else 'FAIL','errors':bad},indent=2)); raise SystemExit(0 if not bad else 2)
