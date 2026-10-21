#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'03_SCHEDULES'
POL={'restart','empirical_pW','learned_pW','empirical_pC','learned_pC'}
errors=[]
origA=pd.read_csv(S/'primary_a_graph_schedule.csv'); origB=pd.read_csv(S/'primary_b_graph_schedule.csv'); origC=pd.read_csv(S/'secondary_c_graph_schedule.csv')

def same_rows(a,b,cols):
    aa=a[cols].sort_values(cols).reset_index(drop=True)
    bb=b[cols].sort_values(cols).reset_index(drop=True)
    return aa.equals(bb)

def same_order(a,b,cols):
    return a[cols].reset_index(drop=True).equals(b[cols].reset_index(drop=True))

def check_orig(d,label):
    if len(d)!=3000: errors.append(f'{label}: expected 3000 rows')
    if d.case_id.nunique()!=30: errors.append(f'{label}: expected 30 cases')
    if set(d.policy)!=POL: errors.append(f'{label}: policy set mismatch')
    if set(d.level)!={'L1','L2','L3','L4'}: errors.append(f'{label}: level set mismatch')
    if d.run_id.duplicated().any(): errors.append(f'{label}: duplicate run_id')
    for key,g in d.groupby(['case_id','level','policy']):
        if len(g)!=5 or set(g.position)!=set(range(5)): errors.append(f'{label}: bad counterbalance {key}')
check_orig(origA,'original A'); check_orig(origB,'original B')

cols=list(origA.columns)
for host,orig in [('A',origA),('B',origB)]:
    lanes=[]; case_seen=set()
    for lane in range(3):
        p=S/'phaseA_7core'/f'vm{host.lower()}_lane{lane}_cpu{lane}.csv'; d=pd.read_csv(p); lanes.append(d)
        if len(d)!=1000 or d.case_id.nunique()!=10: errors.append(f'{host} lane{lane}: expected 1000 rows/10 cases')
        if set(d.policy)!=POL or set(d.level)!={'L1','L2','L3','L4'}: errors.append(f'{host} lane{lane}: policy/level mismatch')
        cs=set(d.case_id)
        if case_seen & cs: errors.append(f'{host}: lane case overlap')
        case_seen |= cs
        for c,g in d.groupby('case_id'):
            if len(g)!=100: errors.append(f'{host} lane{lane}: case {c} has {len(g)} rows, expected 100')
        fam=d[['case_id','family']].drop_duplicates().family.value_counts().to_dict()
        expected=[{'Generic':4,'Workflow':3,'Microservice':3},{'Generic':3,'Workflow':4,'Microservice':3},{'Generic':3,'Workflow':3,'Microservice':4}][lane]
        if fam!=expected: errors.append(f'{host} lane{lane}: family counts {fam}, expected {expected}')
    union=pd.concat(lanes,ignore_index=True)
    if len(union)!=3000 or union.run_id.nunique()!=3000: errors.append(f'{host}: lane union not 3000 unique rows')
    if not same_rows(union,orig,cols): errors.append(f'{host}: lane union differs from original schedule')

    iso=pd.read_csv(S/'phaseB_isolated_full'/f'vm{host.lower()}_full_isolated_cpu0.csv')
    if len(iso)!=3000 or iso.case_id.nunique()!=30: errors.append(f'{host}: Phase B expected 3000 rows/30 cases')
    if set(iso.policy)!=POL or set(iso.level)!={'L1','L2','L3','L4'}: errors.append(f'{host}: Phase B policy/level mismatch')
    if not same_rows(iso,orig,cols): errors.append(f'{host}: Phase B does not contain exactly the original schedule')
    if not same_order(iso,orig,cols): errors.append(f'{host}: Phase B row order differs from original schedule')

C=pd.read_csv(S/'phaseA_7core'/'vmc_lane0_cpu0.csv')
if len(C)!=500 or C.case_id.nunique()!=20 or set(C.level)!={'L4'} or set(C.policy)!=POL: errors.append('C phaseA schedule mismatch')
if not same_rows(C,origC,list(origC.columns)): errors.append('C phaseA schedule differs from frozen secondary schedule')
if set(origA.case_id)&set(origB.case_id): errors.append('original A/B case overlap')

res={'status':'PASS' if not errors else 'FAIL','phaseA_primary_rows':6000,'phaseA_active_cores':7,'phaseB_isolated_rows':6000,'phaseB_levels':['L1','L2','L3','L4'],'primary_cases':60,'secondary_rows':500,'errors':errors}
print(json.dumps(res,indent=2,sort_keys=True)); raise SystemExit(0 if not errors else 2)
