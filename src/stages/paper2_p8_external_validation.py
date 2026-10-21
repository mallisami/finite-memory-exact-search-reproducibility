from __future__ import annotations
import argparse, csv, json, math, os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from certified_assignment.alns_baseline import _repair_greedy
from certified_assignment.destroy_repair_analysis import build_destroy_repair_cache
from certified_assignment.paper2_dsb_environment import (
    APP_INDEX, environment, read_manifest,
)
from certified_assignment.feasibility import is_feasible
from certified_assignment.instance import AssignmentInstance
from certified_assignment.matched_lns_controller import IterationRecord, matched_adaptive_lns
from certified_assignment.matched_lns_policies import make_heuristic_repair_arms
from certified_assignment.objective import assignment_cost
from certified_assignment.paper2_online_pilot import (
    FrozenP6Predictor, OnlineStepPolicy, ReplayTraceEntry,
)
from certified_assignment.real_instances import eligible_topologies
from certified_assignment.trace_dynamic_policy import cache_equal_for_resume

DESTROY_SIZE=12
SLICE_POPS=8
ITERS_PER_STATE=20
BUDGET_FRACTION=0.25
POLICIES=("restart","empirical_compatible","learned","keep_all")


def _dsb_path(root:Path, rel:str)->Path:
    # The retained E-DSB package is nested under 09_Supporting_Data/DeathStarBench_Measured_Inputs, while its
    # original frozen manifests use paths relative to the E-DSB run root.
    if rel.startswith('results/'):
        return root.parent/'deathstarbench'/rel[len('results/'):]
    return root/rel

def _verify_frozen(root:Path):
    mf=root.parent/'deathstarbench/prepared/FROZEN_INPUTS_SHA256.csv'
    if not mf.is_file(): raise RuntimeError('missing E-DSB frozen input manifest')
    import hashlib
    with mf.open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            p=_dsb_path(root,r['path'])
            if not p.is_file(): raise RuntimeError(f'missing frozen input: {p}')
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h!=r['sha256']: raise RuntimeError(f'frozen input hash mismatch: {p}')


def _load_sequence(root:Path,row:dict,topologies,cfg):
    data=np.load(_dsb_path(root,row['path']),allow_pickle=False)
    mats=np.asarray(data['interaction'],dtype=float); demands=np.asarray(data['demands'],dtype=float)
    app=row['app']; rep=int(row['repetition']); s=cfg['solver']
    env_seed=int(s['topology_seed_base'])+APP_INDEX[app]*1000+rep
    cost,capacities,p0,envmeta=environment(
        demands,topologies,int(s['hosts']),float(s['target_capacity_load_rho']),
        float(s['minimum_host_headroom_over_largest_node']),env_seed)
    instances=[AssignmentInstance(mats[i],demands,capacities,cost,name=f"{row['sequence']}_state_{i}") for i in range(10)]
    if any(not is_feasible(inst,p0) for inst in instances): raise AssertionError('common incumbent infeasible')
    return instances,p0,envmeta


def _generate_common_trace(instances,p0,seq_seed:int):
    p=p0.copy(); traces=[]
    for si,inst in enumerate(instances):
        rows=[]
        res=matched_adaptive_lns(
            inst,p,make_heuristic_repair_arms(),destroy_size=DESTROY_SIZE,max_iterations=ITERS_PER_STATE,
            seed=6_600_000+seq_seed*100+si,on_iteration=rows.append)
        p=res.placement.copy()
        traces.append(tuple(ReplayTraceEntry(tuple(int(v) for v in r.nodes),int(r.destroy_op_index)) for r in rows))
    return tuple(traces)


def _reconcile_external(policy:OnlineStepPolicy,inst,placement):
    if policy.name=='restart': return dict(examined=0,compatible=0,incompatible=0)
    examined=compatible=incompatible=0
    for key in list(policy.memory.records):
        examined+=1
        record=policy.memory.records[key]
        try:
            prior=policy._deserialize(record)
            fresh=build_destroy_repair_cache(inst,placement,key)
            ok=cache_equal_for_resume(fresh,prior.checkpoint.cache)
        except Exception:
            ok=False
        if ok:
            compatible+=1
        else:
            policy.memory.records.pop(key,None)
            policy.memory.invalidation_evictions+=1
            policy.invalidated_since_observation.add(key)
            incompatible+=1
    policy.memory.update_accounting()
    return dict(examined=examined,compatible=compatible,incompatible=incompatible)


def _run_policy(base:Path,row:dict,instances,p0,traces,policy_name:str,budget_bytes:int|None,predictor):
    p=p0.copy(); policy=OnlineStepPolicy(policy_name,slice_pops=SLICE_POPS,budget_bytes=budget_bytes,predictor=predictor,future_horizon=40)
    seq_seed=20_000+APP_INDEX[row['app']]*1000+({'step':0,'burst':100,'ramp':200}[row['regime']])+int(row['repetition'])
    rng=np.random.default_rng(8_800_000+seq_seed)
    uniforms=rng.random(10*ITERS_PER_STATE)
    objective_ratios=[]; accepted_moves=0; transition_examined=transition_compatible=transition_incompatible=0
    global_iter=0
    state_end_ratios=[]
    for si,(inst,trace) in enumerate(zip(instances,traces)):
        if si>0:
            audit=_reconcile_external(policy,inst,p)
            transition_examined+=audit['examined'];transition_compatible+=audit['compatible'];transition_incompatible+=audit['incompatible']
        current=float(assignment_cost(inst,p)); best=current
        common_ref=max(float(assignment_cost(inst,p0)),1e-12)
        temperature=max(1e-9,0.01*current)
        for entry in trace:
            global_iter+=1
            local_rng=np.random.default_rng(9_900_000+seq_seed*1000+global_iter)
            before=current
            targets,_,cache,_diag=policy.repair(
                instance=inst,placement=p,nodes=entry.nodes,iteration=global_iter,destroy_op_index=entry.destroy_op_index,
                objective_before=current,best_objective=best,temperature=temperature,local_rng=local_rng)
            q=p.copy()
            for node,host in zip(cache.nodes,targets): q[int(node)]=int(host)
            if not is_feasible(inst,q): raise AssertionError('P8 repair produced infeasible placement')
            q_cost=float(assignment_cost(inst,q)); delta=q_cost-current
            accept_prob=1.0 if delta<0 else math.exp(-max(0.0,delta)/max(temperature,1e-12))
            accept=bool(delta<0 or uniforms[global_iter-1]<accept_prob)
            changed=tuple(int(v) for v in np.flatnonzero(q!=p)) if accept else ()
            if accept:
                p=q;current=q_cost;accepted_moves+=1;best=min(best,current)
            policy.notify_after_decision(instance=inst,nodes=entry.nodes,accepted=accept,iteration=global_iter,
                                         objective_before=before,objective_after=current,placement=p,changed_nodes=changed)
            temperature*=0.995
            objective_ratios.append(current/common_ref)
        state_end_ratios.append(current/common_ref)
    return dict(
        sequence=row['sequence'],app=row['app'],regime=row['regime'],repetition=int(row['repetition']),policy=policy_name,
        budget_fraction=(BUDGET_FRACTION if budget_bytes is not None and policy_name not in ('keep_all','restart') else np.nan),
        budget_bytes=(budget_bytes if budget_bytes is not None else np.nan),iterations=global_iter,accepted_moves=accepted_moves,
        mean_normalized_objective=float(np.mean(objective_ratios)),final_state_normalized_objective=float(state_end_ratios[-1]),
        branch_pops_executed=int(policy.branch_pops_executed),useful_resumes=int(policy.useful_resumes),
        reused_prior_branch_pops=int(policy.reused_prior_branch_pops),capacity_evictions=int(policy.memory.capacity_evictions),
        invalidation_evictions=int(policy.memory.invalidation_evictions),not_retained=int(policy.memory.not_retained),
        peak_bytes=int(policy.memory.peak_bytes),byte_time=int(policy.memory.byte_time),peak_active_checkpoints=int(policy.memory.peak_active_checkpoints),
        max_checkpoint_size_bytes=int(policy.max_checkpoint_size_bytes),transition_examined=transition_examined,
        transition_compatible=transition_compatible,transition_incompatible=transition_incompatible,
        transition_compatible_fraction=(transition_compatible/max(1,transition_examined)),
        serialization_ms=float(policy.memory.serialization_ms),restoration_ms=float(policy.memory.restoration_ms),
        selection_ms=float(policy.memory.selection_ms),model_scoring_ms=float(policy.model_scoring_ms),
    )


def _one_sequence(args):
    base_s,predictor_base_s,row,cfg_s=args;base=Path(base_s);predictor_base=Path(predictor_base_s);cfg=json.loads(cfg_s)
    topologies=eligible_topologies(base.parent/'topology_zoo',int(cfg['solver']['hosts']))
    instances,p0,envmeta=_load_sequence(base,row,topologies,cfg)
    seq_seed=20_000+APP_INDEX[row['app']]*1000+({'step':0,'burst':100,'ramp':200}[row['regime']])+int(row['repetition'])
    traces=_generate_common_trace(instances,p0,seq_seed)
    keep=_run_policy(base,row,instances,p0,traces,'keep_all',None,None)
    peak=max(1,int(keep['peak_bytes']));maxcp=max(1,int(keep['max_checkpoint_size_bytes']))
    budget=max(maxcp,int(round(BUDGET_FRACTION*peak)))
    restart=_run_policy(base,row,instances,p0,traces,'restart',None,None)
    emp=_run_policy(base,row,instances,p0,traces,'empirical_compatible',budget,None)
    predictor=FrozenP6Predictor(predictor_base)
    learned=_run_policy(base,row,instances,p0,traces,'learned',budget,predictor)
    return [restart,emp,learned,keep],dict(sequence=row['sequence'],app=row['app'],regime=row['regime'],repetition=int(row['repetition']),
        keep_all_peak_bytes=peak,keep_all_max_checkpoint_size_bytes=maxcp,budget_fraction=BUDGET_FRACTION,budget_bytes=budget,effective_fraction=budget/peak)


def _strat_boot(x, strata, reps=10000,seed=88008):
    x=np.asarray(x,float); strata=np.asarray(strata)
    uniq=np.unique(strata);rng=np.random.default_rng(seed);means=[]
    inds={s:np.flatnonzero(strata==s) for s in uniq}
    for _ in range(reps):
        vals=[]
        for s in uniq:
            ii=inds[s];vals.extend(x[rng.choice(ii,size=len(ii),replace=True)])
        means.append(float(np.mean(vals)))
    return float(np.mean(x)),float(np.quantile(means,.025)),float(np.quantile(means,.975))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--predictor-base',default=None);ap.add_argument('--out-dir',required=True);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    base=Path(a.base).resolve(); predictor_base=Path(a.predictor_base).resolve() if a.predictor_base else base; out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    _verify_frozen(base)
    cfg=json.loads((base/'config/dsb_dynamic.json').read_text())
    rows=read_manifest(base.parent/'deathstarbench/prepared/sequence_manifest.csv')
    if len(rows)!=90: raise RuntimeError(f'expected 90 frozen sequences, got {len(rows)}')
    tasks=[(str(base),str(predictor_base),r,json.dumps(cfg)) for r in rows]
    rr=[];bb=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        fut={ex.submit(_one_sequence,t):t[2]['sequence'] for t in tasks}
        for i,f in enumerate(as_completed(fut),1):
            rs,b=f.result();rr.extend(rs);bb.append(b);print(f'[{i}/90] {fut[f]}',flush=True)
    runs=pd.DataFrame(rr).sort_values(['app','regime','repetition','policy']).reset_index(drop=True)
    budgets=pd.DataFrame(bb).sort_values(['app','regime','repetition']).reset_index(drop=True)
    runs.to_csv(out/'p8_external_runs.csv',index=False);budgets.to_csv(out/'p8_external_budgets.csv',index=False)
    matched=[]
    keys=['app','regime','repetition']
    for key,g in runs.groupby(keys):
        d={r.policy:r for _,r in g.iterrows()};keep=d['keep_all'];restart=d['restart']
        for pol in ('empirical_compatible','learned'):
            r=d[pol]
            matched.append(dict(app=key[0],regime=key[1],repetition=int(key[2]),policy=pol,
                reuse_fraction_of_keep_all=(r.reused_prior_branch_pops/keep.reused_prior_branch_pops if keep.reused_prior_branch_pops>0 else np.nan),
                mean_objective_improvement_vs_restart=float(restart.mean_normalized_objective-r.mean_normalized_objective),
                final_objective_improvement_vs_restart=float(restart.final_state_normalized_objective-r.final_state_normalized_objective),
                reused_prior_branch_pops=int(r.reused_prior_branch_pops),useful_resumes=int(r.useful_resumes),
                transition_compatible_fraction=float(r.transition_compatible_fraction),peak_active_checkpoints=int(r.peak_active_checkpoints),
                effective_fraction=float(budgets[(budgets.app==key[0])&(budgets.regime==key[1])&(budgets.repetition==key[2])].iloc[0].effective_fraction)))
    m=pd.DataFrame(matched);m.to_csv(out/'p8_external_matched.csv',index=False)
    le=m[m.policy=='learned'].set_index(keys).sort_index();em=m[m.policy=='empirical_compatible'].set_index(keys).sort_index()
    diff=(le.reuse_fraction_of_keep_all-em.reuse_fraction_of_keep_all).fillna(0.0); strata=np.array([f'{a}|{r}' for a,r,_ in diff.index])
    mean,lo,hi=_strat_boot(diff.values,strata)
    obj=le.mean_objective_improvement_vs_restart.values;om,olo,ohi=_strat_boot(obj,strata,seed=88009)
    try:p_reuse=float(wilcoxon(diff.values,zero_method='pratt',alternative='greater').pvalue) if np.any(np.abs(diff.values)>1e-15) else 1.0
    except Exception:p_reuse=1.0
    try:p_obj=float(wilcoxon(obj,zero_method='pratt',alternative='greater').pvalue) if np.any(np.abs(obj)>1e-15) else 1.0
    except Exception:p_obj=1.0
    strata_rows=[]
    for (app,reg),g in m.groupby(['app','regime']):
        for pol,h in g.groupby('policy'):
            strata_rows.append(dict(app=app,regime=reg,policy=pol,n=len(h),mean_reuse_fraction_of_keep_all=float(h.reuse_fraction_of_keep_all.mean()),
                median_reuse_fraction_of_keep_all=float(h.reuse_fraction_of_keep_all.median()),mean_objective_improvement_vs_restart=float(h.mean_objective_improvement_vs_restart.mean()),
                median_objective_improvement_vs_restart=float(h.mean_objective_improvement_vs_restart.median()),median_useful_resumes=float(h.useful_resumes.median()),
                median_peak_active_checkpoints=float(h.peak_active_checkpoints.median()),median_transition_compatible_fraction=float(h.transition_compatible_fraction.median())))
    sdf=pd.DataFrame(strata_rows);sdf.to_csv(out/'p8_external_strata.csv',index=False)
    keep=runs[runs.policy=='keep_all'].set_index(keys).sort_index();restart=runs[runs.policy=='restart'].set_index(keys).sort_index()
    keep_obj=(restart.mean_normalized_objective-keep.mean_normalized_objective).values
    km,klo,khi=_strat_boot(keep_obj,np.array([f'{a}|{r}' for a,r,_ in keep.index]),seed=88010)
    summary=dict(status='P8_measured_workload_external_validation',sequences=90,applications=3,regimes=['step','burst','ramp'],repetitions_per_cell=10,
        settings=dict(destroy_size=DESTROY_SIZE,slice_branch_pops=SLICE_POPS,iterations_per_state=ITERS_PER_STATE,total_iterations_per_sequence=200,budget_fraction=BUDGET_FRACTION),
        learned_minus_empirical_reuse=dict(mean=mean,bootstrap_95_low=lo,bootstrap_95_high=hi,wilcoxon_one_sided_p=p_reuse,positive=int((diff.values>1e-12).sum()),negative=int((diff.values<-1e-12).sum()),ties=int((np.abs(diff.values)<=1e-12).sum())),
        learned_objective_vs_restart=dict(mean=om,bootstrap_95_low=olo,bootstrap_95_high=ohi,wilcoxon_one_sided_p=p_obj,positive=int((obj>1e-12).sum()),negative=int((obj<-1e-12).sum()),ties=int((np.abs(obj)<=1e-12).sum())),
        keep_all_objective_vs_restart=dict(mean=km,bootstrap_95_low=klo,bootstrap_95_high=khi,positive=int((keep_obj>1e-12).sum()),negative=int((keep_obj<-1e-12).sum()),ties=int((np.abs(keep_obj)<=1e-12).sum())),
        interpretation='Measured-workload shadow replay; frozen P6-v1; no retraining/recalibration; keep-all is an upper-resource reference, not oracle.')
    (out/'P8_EXTERNAL_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()
