from pathlib import Path
import json, math
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

OUT=Path('/mnt/data/MDKP_FINAL_DERIVED')
OUT.mkdir(exist_ok=True)
VM=Path('/mnt/data/_vm90/PCR2_V6B_VM90_RESULTS/outputs/MERGED_RAW.csv')
R1=Path('/mnt/data/V6B_CONFIRMATORY_RAW.csv')
R2=Path('/mnt/data/V6B_R2_CONFIRMATORY_RAW.csv')

def geo(a):
    a=np.asarray(a,float)
    return float(np.exp(np.mean(np.log(a))))

def bootstrap_geo_ratio(ratios, strata=None, B=10000, seed=20261011):
    ratios=np.asarray(ratios,float)
    rng=np.random.default_rng(seed)
    logs=np.log(ratios)
    vals=[]
    if strata is None:
        strata=np.zeros(len(logs),dtype=int)
    strata=np.asarray(strata)
    uniq=np.unique(strata)
    idxs={s:np.flatnonzero(strata==s) for s in uniq}
    for _ in range(B):
        draw=[]
        for s,ix in idxs.items():
            draw.extend(rng.choice(ix,size=len(ix),replace=True).tolist())
        vals.append(math.exp(float(logs[draw].mean())))
    return [float(x) for x in np.quantile(vals,[.025,.975])]

raw=pd.read_csv(VM)
agg=raw.groupby(['vm_id','global_case_index','seed','policy'],as_index=False).agg(
    wall_ms=('wall_ms','median'), cpu_ms=('cpu_ms','median'), repair_search_ms=('repair_search_ms','median'),
    branches=('branches','first'), useful_resumes=('useful_resumes','first'), reused_prior_nodes=('reused_prior_nodes','first'),
    final_cost=('final_cost','first'), best_cost=('best_cost','first'), trajectory_hash=('trajectory_hash','first'),
    model_scoring_ms=('model_scoring_ms','median'), selection_ms=('selection_ms','median'),
    serialization_ms=('serialization_ms','median'), restoration_ms=('restoration_ms','median'))
agg.to_csv(OUT/'MDKP_VM90_CASE_POLICY_MEDIANS.csv',index=False)

p=agg.pivot(index=['vm_id','global_case_index','seed'],columns='policy')
vm_index=np.array([x[0] for x in p.index])

def contrast(metric,a='direct_utility',b='empirical_pW',seed=20261011):
    ratio=(p[(metric,a)]/p[(metric,b)]).to_numpy(float)
    log=np.log(ratio)
    try: wp=float(wilcoxon(log,alternative='two-sided',zero_method='wilcox').pvalue)
    except Exception: wp=float('nan')
    return {
      'ratio':geo(ratio),'ci95':bootstrap_geo_ratio(ratio,vm_index,10000,seed),
      'wins_a_lower':int((ratio<1).sum()),'ties':int((ratio==1).sum()),'losses_a_higher':int((ratio>1).sum()),
      'wilcoxon_p_two_sided':wp,'n_cases':int(len(ratio))}

res={
 'primary_wall_direct_vs_empirical':contrast('wall_ms',seed=202610111001),
 'secondary_wall_direct_vs_restart':contrast('wall_ms','direct_utility','restart',202610111002),
 'nodes_direct_vs_empirical':contrast('branches',seed=202610111004),
 'nodes_direct_vs_restart':contrast('branches','direct_utility','restart',202610111005),
 'nodes_empirical_vs_restart':contrast('branches','empirical_pW','restart',202610111006),
 'solution_quality':{}
}
fd=(p[('final_cost','direct_utility')]-p[('final_cost','empirical_pW')]).to_numpy(float)
res['solution_quality']={'same':int((fd==0).sum()),'direct_better':int((fd<0).sum()),'direct_worse':int((fd>0).sum()),'mean_direct_minus_empirical':float(fd.mean()),'max_abs_diff':float(np.abs(fd).max())}

# same-trajectory regression: saved repair time = beta0 + beta1*saved nodes + beta2*resumes
same=(p[('trajectory_hash','direct_utility')]==p[('trajectory_hash','restart')]).to_numpy()
q=p.loc[same]
nodes_saved=(q[('branches','restart')]-q[('branches','direct_utility')]).to_numpy(float)
repair_saved=(q[('repair_search_ms','restart')]-q[('repair_search_ms','direct_utility')]).to_numpy(float)
resumes=q[('useful_resumes','direct_utility')].to_numpy(float)
X=np.column_stack([np.ones(len(q)),nodes_saved,resumes])
beta=np.linalg.lstsq(X,repair_saved,rcond=None)[0]
res['same_trajectory_diagnostic']={
 'n_cases':int(len(q)), 'intercept_ms':float(beta[0]), 'ms_per_saved_node':float(beta[1]), 'ms_per_resume':float(beta[2]),
 'mean_restart_nodes':float(q[('branches','restart')].mean()), 'mean_direct_nodes':float(q[('branches','direct_utility')].mean()),
 'mean_node_reduction_pct':float(100*(1-q[('branches','direct_utility')].mean()/q[('branches','restart')].mean())),
 'mean_restart_repair_ms':float(q[('repair_search_ms','restart')].mean()), 'mean_direct_repair_ms':float(q[('repair_search_ms','direct_utility')].mean()),
 'mean_repair_reduction_pct':float(100*(1-q[('repair_search_ms','direct_utility')].mean()/q[('repair_search_ms','restart')].mean())),
 'mean_direct_resumes':float(resumes.mean())}

# R2 tail sensitivity
r2=pd.read_csv(R2).pivot(index='case_index',columns='policy',values='branches')
r2ratio=(r2.direct_utility/r2.empirical_pW)
net=(r2.empirical_pW-r2.direct_utility)
res['r2_45_tail_sensitivity']={
 'ratio_all':geo(r2ratio), 'ratio_drop_best_1':geo(r2ratio.sort_values().iloc[1:]), 'ratio_drop_best_3':geo(r2ratio.sort_values().iloc[3:]),
 'median_case_ratio':float(r2ratio.median()), 'best_case_ratio':float(r2ratio.min()), 'best_case_index':int(r2ratio.idxmin()),
 'best_case_nodes_saved':int(net.max()), 'best_case_share_total_net_saving':float(net.max()/net.sum())}

# 150-case stratified by study
r1=pd.read_csv(R1).pivot(index='case_index',columns='policy',values='branches')
vmnodes=agg.pivot(index=['vm_id','global_case_index','seed'],columns='policy',values='branches')
blocks=[]
for name,z in [('heldout15',r1),('heldout45',r2),('vm90',vmnodes)]:
    rr=(z.direct_utility/z.empirical_pW).to_numpy(float)
    blocks.append((name,rr))
allr=np.concatenate([a for _,a in blocks])
strata=np.concatenate([[name]*len(a) for name,a in blocks])
res['pooled_150_node_sensitivity']={
 'ratio':geo(allr),'ci95':bootstrap_geo_ratio(allr,strata,10000,202610111500),
 'wins_direct_lower':int((allr<1).sum()),'ties':int((allr==1).sum()),'losses_direct_higher':int((allr>1).sum()),
 'n_cases':int(len(allr)), 'block_ratios':{name:geo(a) for name,a in blocks}}

# per VM
res['per_vm_wall_direct_vs_empirical']={}
for vm in sorted(set(vm_index)):
    z=p.loc[[i for i in p.index if i[0]==vm]]
    rr=(z[('wall_ms','direct_utility')]/z[('wall_ms','empirical_pW')]).to_numpy(float)
    res['per_vm_wall_direct_vs_empirical'][vm]={'ratio':geo(rr),'wins_direct_faster':int((rr<1).sum()),'losses_direct_slower':int((rr>1).sum()),'ties':int((rr==1).sum()),'n_cases':len(rr)}

# diagnosis values from instrumented re-execution supplied with the study record
res['instrumented_cost_structure']={
 'depth_bins':['0-9','10-19','20-29','30-39','40-49','50-59'],
 'ms_per_node':[0.057,0.043,0.034,0.023,0.014,0.006],
 'representative_seed':2122060784,
 'representative_direct_resumes':59,
 'representative_cap_hitting_resumes':48,
 'representative_early_retiring_resumes':11,
 'estimated_oracle_wall_saving_pct_approx':2.5,
 'provenance':'instrumented local re-execution and diagnostic analysis supplied with the final study record; not a new confirmatory timing campaign'}

with open(OUT/'MDKP_WORK_TO_RUNTIME_FINAL_ANALYSIS.json','w') as f: json.dump(res,f,indent=2,sort_keys=True)

# compact case summary
rows=[]
for idx,row in p.iterrows():
    vm,case,seed=idx
    rows.append({'vm_id':vm,'case':case,'seed':seed,
      'wall_direct_over_empirical':row[('wall_ms','direct_utility')]/row[('wall_ms','empirical_pW')],
      'wall_direct_over_restart':row[('wall_ms','direct_utility')]/row[('wall_ms','restart')],
      'nodes_direct_over_empirical':row[('branches','direct_utility')]/row[('branches','empirical_pW')],
      'nodes_direct_over_restart':row[('branches','direct_utility')]/row[('branches','restart')],
      'same_traj_direct_restart':row[('trajectory_hash','direct_utility')]==row[('trajectory_hash','restart')],
      'direct_resumes':row[('useful_resumes','direct_utility')],
      'direct_final_cost':row[('final_cost','direct_utility')], 'empirical_final_cost':row[('final_cost','empirical_pW')]})
pd.DataFrame(rows).to_csv(OUT/'MDKP_VM90_CASE_SUMMARY.csv',index=False)
print(json.dumps(res,indent=2))
