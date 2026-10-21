from __future__ import annotations
import argparse, json, os, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
sys.path.insert(0,'/mnt/data')
import pcr2_external_execution_orchestrator as o

def done_ids():
    out=set()
    if o.JOURNAL.exists():
        with o.JOURNAL.open() as f:
            for line in f:
                if line.strip(): out.add(json.loads(line)['task_id'])
    return out

def run_case(case_key, tasks):
    import sys
    sys.path.insert(0,'/mnt/data')
    import pcr2_fast_bound, pcr2_fast_cache
    pcr2_fast_bound.install(); pcr2_fast_cache.install()
    from certified_assignment.paper2_online_pilot import generate_replay_trace
    from certified_assignment.paper2_external_eviction import run_external_online_replay
    import scripts.paper2_p7_external_comparators as frozen
    d,s=case_key
    tr=generate_replay_trace(d,int(s),iterations=frozen.ITERATIONS,destroy_size=frozen.DESTROY_SIZE)
    rows=[]
    for t in tasks:
        r=run_external_online_replay(
            d,int(s),tr,policy_name=t['policy'],slice_pops=frozen.SLICE_POPS,
            budget_bytes=int(t['budget_bytes']),budget_fraction=float(t['budget_fraction']),
            eviction_seed=t['eviction_seed'])
        x=r.to_dict(); x['task_id']=t['task_id']; x['random_repetition']=(None if t['random_repetition']==0 else int(t['random_repetition'])); x['eviction_seed']=t['eviction_seed']; x['execution_backend']='numba_exact_bound_equivalent'
        rows.append(x)
    return rows

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--workers',type=int,default=2); ap.add_argument('--max-cases',type=int,default=2); a=ap.parse_args()
    tasks=o.make_tasks(); done=done_ids()
    by={}
    for t in tasks:
        if t['task_id'] in done: continue
        key=(t['domain'],int(t['instance_seed']))
        by.setdefault(key,[]).append(t)
    keys=list(by)
    if a.max_cases>0: keys=keys[:a.max_cases]
    print(f'completed_before={len(done)} cases_submit={len(keys)} remaining_tasks={sum(len(v) for v in by.values())}',flush=True)
    if not keys: return
    with ProcessPoolExecutor(max_workers=min(int(a.workers),len(keys))) as ex:
        fut={ex.submit(run_case,k,by[k]):k for k in keys}
        with o.JOURNAL.open('a',buffering=1) as f:
            for q in as_completed(fut):
                k=fut[q]; rows=q.result()
                for x in rows:
                    f.write(json.dumps(x,sort_keys=True,default=lambda z:z.item() if hasattr(z,'item') else z)+'\n')
                    f.flush(); os.fsync(f.fileno())
                print(f'persisted_case={k[0]}:{k[1]} rows={len(rows)}',flush=True)

if __name__=='__main__': main()
