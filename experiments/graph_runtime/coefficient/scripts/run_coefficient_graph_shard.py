#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,platform,sys,time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'04_SOURCE'; EXT=SRC/'pcr_tx_extension'
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
if str(EXT) not in sys.path: sys.path.insert(0,str(EXT))
from fast_p6_predictor import FrozenP6CoefficientPredictor
from pcr_tx_extension.certified_assignment.paper2_online_pilot import generate_replay_trace
from pcr_tx_extension.certified_assignment.pcr_graph_engine import run_graph_campaign_case
POLICIES={'restart','empirical_pW','learned_pW','empirical_pC','learned_pC'}

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def env_snapshot():
    aff=sorted(int(x) for x in os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None
    mem=None
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'): mem=round(int(line.split()[1])/1024/1024,3)
    except Exception: pass
    return {
      'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'hostname':platform.node(),'python':sys.version,'kernel':platform.release(),
      'logical_cpus':os.cpu_count(),'mem_total_gib':mem,'affinity':aff,
      'loadavg':list(os.getloadavg()) if hasattr(os,'getloadavg') else None,
      'threads':{k:os.getenv(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED']}
    }

def load_successes(wal:Path):
    if not wal.exists(): return set()
    d=pd.read_csv(wal,dtype=str).fillna(''); return set(d.loc[d.status.eq('SUCCESS'),'run_id'])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--schedule',type=Path,required=True)
    ap.add_argument('--host-label',required=True)
    ap.add_argument('--physical-vm',required=True,choices=['A','B','C'])
    ap.add_argument('--phase',required=True,choices=['phaseA_7core','phaseB_isolated_full'])
    ap.add_argument('--lane-id',required=True)
    ap.add_argument('--cpu-id',type=int,required=True)
    ap.add_argument('--concurrency-width',type=int,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--max-runs',type=int)
    a=ap.parse_args(); out=a.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)

    sched=pd.read_csv(a.schedule)
    if set(sched.domain.str.lower())!={'graph'}: raise RuntimeError('P0 runner accepts graph-only schedules')
    if not set(sched.policy).issubset(POLICIES): raise RuntimeError('Unexpected policy in schedule')
    if sched.run_id.duplicated().any(): raise RuntimeError('Duplicate run_id in schedule')
    if hasattr(os,'sched_getaffinity'):
        aff=sorted(os.sched_getaffinity(0))
        if aff != [a.cpu_id]: raise RuntimeError(f'Process must be taskset-pinned to CPU {a.cpu_id}; observed affinity={aff}')

    levels=json.load(open(ROOT/'06_FROZEN_INPUTS'/'OPPORTUNITY_LEVEL_FREEZE.json'))['frozen_levels']
    caps=json.load(open(ROOT/'06_FROZEN_INPUTS'/'GRAPH_CAPACITY_LIMITS.json'))['capacity_matrix']
    weights=json.load(open(ROOT/'06_FROZEN_INPUTS'/'PRIMARY_A_CALIBRATION.json'))['graph']['integer_weights']
    pred=FrozenP6CoefficientPredictor(ROOT/'05_MODELS'/'p6_final_model.joblib',ROOT/'05_MODELS'/'p6_calibration.joblib')

    snap=env_snapshot(); snap.update({
      'host_label':a.host_label,'physical_vm':a.physical_vm,'phase':a.phase,'lane_id':a.lane_id,
      'declared_cpu_id':a.cpu_id,'concurrency_width':a.concurrency_width,
      'schedule':str(a.schedule),'schedule_sha256':sha256(a.schedule),
      'scorer_implementation':pred.implementation_name,
      'model_sha256':sha256(ROOT/'05_MODELS'/'p6_final_model.joblib'),
      'calibration_sha256':sha256(ROOT/'05_MODELS'/'p6_calibration.joblib')
    })
    (out/'environment_at_start.json').write_text(json.dumps(snap,indent=2,sort_keys=True)+'\n')

    wal=out/'wal.csv'; done=load_successes(wal) if a.resume else set()
    if wal.exists() and not a.resume: raise RuntimeError(f'{wal} already exists; use --resume only for interruption recovery')
    todo=sched[~sched.run_id.isin(done)].copy()
    if a.max_runs is not None: todo=todo.iloc[:a.max_runs]
    traces={}
    for r in todo.itertuples(index=False):
        k=(str(r.family).lower(),int(r.seed))
        if k not in traces: traces[k]=generate_replay_trace(k[0],k[1],iterations=200,destroy_size=12)

    fields=['attempt','run_id','case_id','domain','family','seed','physical_vm','host_label','phase','lane_id','cpu_id','concurrency_width','level','repeat','position','policy','scorer_impl','start_time_iso','end_time_iso','status','technical_valid','end_to_end_wall_ns','end_to_end_cpu_ns','end_to_end_wall_ms','end_to_end_cpu_ms','trajectory_hash','accepted_moves','executed_branches','useful_resumes','reused_branches','checkpoint_creations','exact_retirements','capacity_evictions','invalidation_evictions','not_retained','peak_bytes','byte_time','initial_objective','final_objective','best_objective','serialization_ms','restoration_ms','selection_ms','model_scoring_ms','expanded_nodes','bound_evals','generated_children','feasibility_checks','incumbent_evals','frontier_inserts']
    new_file=not wal.exists(); wf=wal.open('a',newline='',encoding='utf-8'); w=csv.DictWriter(wf,fieldnames=fields)
    if new_file: w.writeheader(); wf.flush()
    existing_attempts={}
    if wal.exists() and not new_file:
        try: existing_attempts=pd.read_csv(wal).groupby('run_id').size().to_dict()
        except Exception: pass

    print(f'[{a.host_label}] phase={a.phase} lane={a.lane_id} cpu={a.cpu_id} schedule={len(sched)} already_success={len(done)} to_run={len(todo)} scorer={pred.implementation_name}',flush=True)
    errors=0; t0=time.time()
    for n,r in enumerate(todo.itertuples(index=False),1):
        start=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); attempt=int(existing_attempts.get(r.run_id,0))+1
        base={'attempt':attempt,'run_id':r.run_id,'case_id':r.case_id,'domain':'graph','family':r.family,'seed':int(r.seed),'physical_vm':a.physical_vm,'host_label':a.host_label,'phase':a.phase,'lane_id':a.lane_id,'cpu_id':a.cpu_id,'concurrency_width':a.concurrency_width,'level':r.level,'repeat':int(r.repeat),'position':int(r.position),'policy':r.policy,'scorer_impl':pred.implementation_name,'start_time_iso':start}
        try:
            res=run_graph_campaign_case(domain=str(r.family).lower(),seed=int(r.seed),trace=traces[(str(r.family).lower(),int(r.seed))],policy_name=r.policy,slice_pops=int(levels[r.level]),budget_bytes=int(caps[r.case_id][r.level]['frozen_budget_bytes']),predictor=pred,compute_weights=weights)
            c=res.total_counters
            row={**base,'end_time_iso':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'SUCCESS','technical_valid':1,'end_to_end_wall_ns':res.end_to_end_wall_ns,'end_to_end_cpu_ns':res.end_to_end_cpu_ns,'end_to_end_wall_ms':res.end_to_end_wall_ns/1e6,'end_to_end_cpu_ms':res.end_to_end_cpu_ns/1e6,'trajectory_hash':res.trajectory_hash,'accepted_moves':res.accepted_moves,'executed_branches':res.branch_pops_executed,'useful_resumes':res.useful_resumes,'reused_branches':res.reused_prior_branch_pops,'checkpoint_creations':res.checkpoint_creations,'exact_retirements':res.exact_retirements,'capacity_evictions':res.capacity_evictions,'invalidation_evictions':res.invalidation_evictions,'not_retained':res.not_retained,'peak_bytes':res.peak_bytes,'byte_time':res.byte_time,'initial_objective':res.initial_objective,'final_objective':res.final_objective,'best_objective':res.best_objective,'serialization_ms':res.serialization_ms,'restoration_ms':res.restoration_ms,'selection_ms':res.selection_ms,'model_scoring_ms':res.model_scoring_ms,'expanded_nodes':c.get('expanded_nodes',0),'bound_evals':c.get('bound_evals',0),'generated_children':c.get('generated_children',0),'feasibility_checks':c.get('feasibility_checks',0),'incumbent_evals':c.get('incumbent_evals',0),'frontier_inserts':c.get('frontier_inserts',0)}
        except Exception as e:
            errors+=1; row={**base,'end_time_iso':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'ERROR:'+repr(e),'technical_valid':0}
        w.writerow(row); wf.flush(); os.fsync(wf.fileno())
        if n%25==0 or n==len(todo):
            elapsed=time.time()-t0; rate=n/max(elapsed,1e-9); eta=(len(todo)-n)/max(rate,1e-9)
            print(f'[{a.host_label}] {n}/{len(todo)} elapsed={elapsed/3600:.2f}h ETA={eta/3600:.2f}h errors={errors}',flush=True)
    wf.close()
    allw=pd.read_csv(wal); succ=allw[allw.status.eq('SUCCESS')].drop_duplicates('run_id',keep='last'); succ.to_csv(out/'results_success_latest.csv',index=False)
    summary={'phase':a.phase,'physical_vm':a.physical_vm,'lane_id':a.lane_id,'cpu_id':a.cpu_id,'concurrency_width':a.concurrency_width,'schedule_rows':len(sched),'unique_success':int(succ.run_id.nunique()),'expected_rows':len(sched),'errors_recorded':int((~allw.status.eq('SUCCESS')).sum()),'complete':bool(succ.run_id.nunique()==len(sched))}
    (out/'completion.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,indent=2),flush=True)
    raise SystemExit(0 if summary['complete'] and errors==0 else (4 if errors else 3))
if __name__=='__main__': main()
