from __future__ import annotations
import argparse, json, math
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from certified_assignment.paper2_online_pilot import FrozenP6Predictor, generate_replay_trace, run_online_replay

DOMAINS=("generic","workflow","microservice")
SEEDS=tuple(range(3301,3316))
BUDGETS=(0.25,0.50,0.75)
DESTROY_SIZE=12
ITERATIONS=200
SLICE_POPS=8


def _run_case(args):
    base,domain,seed=args
    predictor=None
    trace=generate_replay_trace(domain,seed,iterations=ITERATIONS,destroy_size=DESTROY_SIZE)
    rows=[]; budgets=[]
    keep=run_online_replay(domain,seed,trace,policy_name='keep_all',slice_pops=SLICE_POPS)
    restart=run_online_replay(domain,seed,trace,policy_name='restart',slice_pops=SLICE_POPS)
    rows.extend([keep.to_dict(),restart.to_dict()])
    peak=max(1,keep.peak_bytes); max_cp=max(1,keep.max_checkpoint_size_bytes)
    case_budgets = {}
    for frac in BUDGETS:
        budget=max(max_cp,int(round(frac*peak)))
        case_budgets[frac] = budget
        budgets.append(dict(domain=domain,instance_seed=seed,budget_fraction=frac,budget_bytes=budget,
                            keep_all_peak_bytes=peak,keep_all_max_checkpoint_size_bytes=max_cp,
                            effective_fraction=budget/peak))
    # Execution-only ordering: keep policy families grouped rather than
    # alternating sklearn scoring and SciPy/HiGHS MILP calls in one process.
    # Each policy/budget replay is independent and receives the same trace, so
    # this changes no scientific input or result.
    for policy in ('empirical_compatible','learned'):
        if policy == 'learned':
            predictor = FrozenP6Predictor(base)
        for frac in BUDGETS:
            budget = case_budgets[frac]
            r=run_online_replay(domain,seed,trace,policy_name=policy,slice_pops=SLICE_POPS,
                                budget_bytes=budget,budget_fraction=frac,
                                predictor=predictor if policy=='learned' else None)
            rows.append(r.to_dict())
    return rows,budgets


def _boot_ci(x, seed=77001, reps=10000):
    a=np.asarray(x,dtype=float); a=a[np.isfinite(a)]
    if len(a)==0: return (math.nan,math.nan,math.nan)
    rng=np.random.default_rng(seed); idx=rng.integers(0,len(a),size=(reps,len(a)))
    means=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(means,.025)),float(np.quantile(means,.975))


def _holm(pvals):
    names=list(pvals); m=len(names); order=sorted(names,key=lambda k:pvals[k]); out={}
    running=0.0
    for rank,name in enumerate(order):
        adj=min(1.0,(m-rank)*pvals[name]); running=max(running,adj); out[name]=running
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--out-dir',required=True);ap.add_argument('--workers',type=int,default=3);a=ap.parse_args()
    base=str(Path(a.base).resolve());out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    tasks=[(base,d,s) for d in DOMAINS for s in SEEDS]
    rows=[];budgets=[]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        fut={ex.submit(_run_case,t):t for t in tasks}
        for i,f in enumerate(as_completed(fut),1):
            t=fut[f]; rr,bb=f.result(); rows.extend(rr);budgets.extend(bb); print(f'[{i}/{len(tasks)}] {t[1]} {t[2]}',flush=True)
    df=pd.DataFrame(rows).sort_values(['domain','instance_seed','policy','budget_fraction'],na_position='first').reset_index(drop=True)
    bd=pd.DataFrame(budgets).sort_values(['domain','instance_seed','budget_fraction']).reset_index(drop=True)
    df.to_csv(out/'p7_confirmatory_runs.csv',index=False);bd.to_csv(out/'p7_confirmatory_budgets.csv',index=False)

    comp=[]
    for _,r in df[df.policy.isin(['empirical_compatible','learned'])].iterrows():
        rr=df[(df.domain==r.domain)&(df.instance_seed==r.instance_seed)&(df.policy=='restart')].iloc[0]
        kk=df[(df.domain==r.domain)&(df.instance_seed==r.instance_seed)&(df.policy=='keep_all')].iloc[0]
        denom=max(abs(float(rr.best_objective)),1e-12)
        comp.append(dict(
            domain=r.domain,instance_seed=int(r.instance_seed),budget_fraction=float(r.budget_fraction),policy=r.policy,
            reuse_fraction_of_keep_all=float(r.reused_prior_branch_pops/kk.reused_prior_branch_pops) if kk.reused_prior_branch_pops>0 else np.nan,
            reused_prior_branch_pops=int(r.reused_prior_branch_pops),useful_resumes=int(r.useful_resumes),
            best_objective_improvement_vs_restart=float(rr.best_objective-r.best_objective),
            relative_best_improvement_vs_restart=float((rr.best_objective-r.best_objective)/denom),
            anytime_improvement_vs_restart=float(rr.mean_objective_ratio-r.mean_objective_ratio),
            relative_best_gap_to_keep_all=float((r.best_objective-kk.best_objective)/denom),
            byte_time=int(r.byte_time),peak_bytes=int(r.peak_bytes),capacity_evictions=int(r.capacity_evictions),
            invalidation_evictions=int(r.invalidation_evictions),
            persistence_overhead_ms=float(r.serialization_ms+r.restoration_ms+r.selection_ms+r.model_scoring_ms),
        ))
    cmp=pd.DataFrame(comp).sort_values(['budget_fraction','policy','domain','instance_seed']).reset_index(drop=True)
    cmp.to_csv(out/'p7_confirmatory_matched.csv',index=False)

    agg=[]
    for (b,p),g in cmp.groupby(['budget_fraction','policy']):
        agg.append(dict(
            budget_fraction=float(b),policy=p,cases=len(g),
            mean_reuse_fraction_of_keep_all=float(g.reuse_fraction_of_keep_all.mean()),median_reuse_fraction_of_keep_all=float(g.reuse_fraction_of_keep_all.median()),
            mean_relative_best_improvement_vs_restart=float(g.relative_best_improvement_vs_restart.mean()),median_relative_best_improvement_vs_restart=float(g.relative_best_improvement_vs_restart.median()),
            mean_anytime_improvement_vs_restart=float(g.anytime_improvement_vs_restart.mean()),median_anytime_improvement_vs_restart=float(g.anytime_improvement_vs_restart.median()),
            cases_better_best_than_restart=int((g.relative_best_improvement_vs_restart>1e-12).sum()),
            cases_worse_best_than_restart=int((g.relative_best_improvement_vs_restart<-1e-12).sum()),
            cases_no_worse_best_than_restart=int((g.relative_best_improvement_vs_restart>=-1e-12).sum()),
            median_useful_resumes=float(g.useful_resumes.median()),median_reused_prior_branch_pops=float(g.reused_prior_branch_pops.median()),
            median_persistence_overhead_ms=float(g.persistence_overhead_ms.median()),
        ))
    adf=pd.DataFrame(agg);adf.to_csv(out/'p7_confirmatory_aggregate.csv',index=False)

    # Primary paired inference at 25%.
    c25=cmp[cmp.budget_fraction==0.25]
    le=c25[c25.policy=='learned'].set_index(['domain','instance_seed']).sort_index()
    em=c25[c25.policy=='empirical_compatible'].set_index(['domain','instance_seed']).sort_index()
    stats=[]; rawp={}
    tests={
      'learned_minus_empirical_reuse': le.reuse_fraction_of_keep_all-em.reuse_fraction_of_keep_all,
      'learned_relative_best_vs_restart': le.relative_best_improvement_vs_restart,
      'learned_minus_empirical_relative_best': le.relative_best_improvement_vs_restart-em.relative_best_improvement_vs_restart,
      'learned_minus_empirical_anytime': le.anytime_improvement_vs_restart-em.anytime_improvement_vs_restart,
    }
    for j,(name,x) in enumerate(tests.items()):
        mean,lo,hi=_boot_ci(x.values,seed=77001+j)
        arr=np.asarray(x.values,dtype=float)
        try: p=float(wilcoxon(arr,zero_method='pratt',alternative='greater').pvalue) if np.any(np.abs(arr)>1e-15) else 1.0
        except Exception: p=1.0
        rawp[name]=p
        stats.append(dict(comparison=name,n=len(arr),mean_paired_effect=mean,bootstrap_95_low=lo,bootstrap_95_high=hi,
                          median_paired_effect=float(np.median(arr)),positive_cases=int((arr>1e-12).sum()),negative_cases=int((arr<-1e-12).sum()),ties=int((np.abs(arr)<=1e-12).sum()),wilcoxon_one_sided_p=p))
    holm=_holm(rawp)
    for r in stats:r['holm_adjusted_p']=holm[r['comparison']]
    sdf=pd.DataFrame(stats);sdf.to_csv(out/'p7_confirmatory_primary_inference.csv',index=False)

    # Keep-all opportunity vs restart on all 45 cases.
    kk=df[df.policy=='keep_all'].set_index(['domain','instance_seed']).sort_index(); rr=df[df.policy=='restart'].set_index(['domain','instance_seed']).sort_index()
    rel=(rr.best_objective-kk.best_objective)/np.maximum(np.abs(rr.best_objective),1e-12)
    km,klo,khi=_boot_ci(rel.values,seed=77991)
    summary=dict(
      design_status='P7_confirmatory_online_persistence',regime=dict(n_nodes=24,n_hosts=6,destroy_size=12,slice_branch_pops=8),
      independent_cases=45,domains=list(DOMAINS),seeds=list(SEEDS),iterations_per_case=ITERATIONS,budget_fractions=list(BUDGETS),primary_budget_fraction=0.25,
      keep_all_opportunity=dict(mean_relative_best_improvement_vs_restart=km,bootstrap_95_low=klo,bootstrap_95_high=khi,
                                better_cases=int((rel>1e-12).sum()),worse_cases=int((rel<-1e-12).sum()),no_worse_cases=int((rel>=-1e-12).sum()),
                                median_useful_resumes=float(kk.useful_resumes.median()),median_reused_prior_branch_pops=float(kk.reused_prior_branch_pops.median()),median_peak_active_checkpoints=float(kk.peak_active_checkpoints.median())),
      primary_inference=sdf.to_dict(orient='records'),aggregate=adf.to_dict(orient='records'),
      interpretation='Keep-all is an upper-resource opportunity reference, not a clairvoyant future oracle. Learned P6-v1 is frozen with no retraining.'
    )
    (out/'P7_CONFIRMATORY_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'keep_all_opportunity':summary['keep_all_opportunity'],'primary_inference':summary['primary_inference']},indent=2,sort_keys=True),flush=True)

if __name__=='__main__': main()
