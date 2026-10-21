#!/usr/bin/env python3
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd
from scipy.stats import wilcoxon
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(); ap.add_argument('--results-root',type=Path,default=ROOT/'09_RESULTS'); ap.add_argument('--out-dir',type=Path,default=Path('P0_ANALYSIS')); a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
POL={'restart','empirical_pW','learned_pW','empirical_pC','learned_pC'}
LEVELS=['L1','L2','L3','L4']

def latest_success(p:Path):
    if not p.is_file(): raise FileNotFoundError(p)
    d=pd.read_csv(p)
    d=d[d.status.eq('SUCCESS')].drop_duplicates('run_id',keep='last')
    return d

def verify_against_original(d:pd.DataFrame,label:str):
    old=pd.read_csv(ROOT/'08_REFERENCE'/'original_pipeline_combined_graph_results.csv')
    cols=['run_id','trajectory_hash','accepted_moves','executed_branches','useful_resumes','reused_branches','checkpoint_creations','capacity_evictions','invalidation_evictions','peak_bytes','byte_time','final_objective','best_objective','expanded_nodes','bound_evals','generated_children','feasibility_checks','incumbent_evals','frontier_inserts']
    m=d.merge(old[cols],on='run_id',suffixes=('_new','_old'),validate='many_to_one')
    if len(m)!=len(d): raise RuntimeError(f'{label}: not every run_id mapped to original campaign')
    mis={}
    for c in cols[1:]:
        x=m[f'{c}_new']; y=m[f'{c}_old']
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y): neq=~np.isclose(x.to_numpy(float),y.to_numpy(float),rtol=0,atol=1e-9,equal_nan=True)
        else: neq=~x.astype(str).eq(y.astype(str)).to_numpy()
        n=int(np.sum(neq))
        if n: mis[c]=n
    if mis: raise RuntimeError(f'{label}: scientific equivalence failure {mis}')
    return True

def reduce_case(d):
    return d.groupby(['case_id','physical_vm','host_label','family','level','policy'],as_index=False).agg(
      wall_ms=('end_to_end_wall_ms','median'),cpu_ms=('end_to_end_cpu_ms','median'),score_ms=('model_scoring_ms','median'),
      repeat_cv=('end_to_end_wall_ms',lambda x: float(np.std(x,ddof=1)/np.mean(x)) if len(x)>1 and np.mean(x)!=0 else 0.0))

def pivot(agg):
    return agg.pivot(index=['case_id','physical_vm','host_label','family','level'],columns='policy',values='wall_ms').reset_index()

def bootstrap_logs(vals,strata,seed,B=10000):
    vals=np.asarray(vals,float); strata=np.asarray(strata,str); rng=np.random.default_rng(seed)
    boots=np.zeros(B,float); n_total=0
    for s in np.unique(strata):
        ix=np.where(strata==s)[0]; n=len(ix)
        draw=rng.choice(ix,size=(B,n),replace=True)
        boots += vals[draw].sum(axis=1); n_total += n
    boots /= float(n_total)
    lo,hi=np.percentile(boots,[2.5,97.5]); return float(np.exp(np.mean(vals))), [float(np.exp(lo)),float(np.exp(hi))]

def boot_ratio(df,num,den,seed,B=10000,stratum_col='strata',with_test=False):
    logs=np.log(df[num].to_numpy(float)/df[den].to_numpy(float)); ratio,ci=bootstrap_logs(logs,df[stratum_col].astype(str).to_numpy(),seed,B)
    out={'learned_over_empirical_ratio':ratio,'ci95_ratio':ci,'percent_learned_minus_empirical':(ratio-1)*100.0,'median_paired_ms':float(np.median(df[num]-df[den])),'n_cases':int(len(df))}
    if with_test:
        try: out['wilcoxon_p_raw']=float(wilcoxon(logs,alternative='two-sided').pvalue)
        except Exception: out['wilcoxon_p_raw']=1.0
    return out

def overall_case_effect(piv,num,den,seed):
    z=piv.copy(); z['log_ratio']=np.log(z[num].to_numpy(float)/z[den].to_numpy(float))
    if set(z.level)!=set(LEVELS): raise RuntimeError('Overall effect missing one or more levels')
    counts=z.groupby('case_id')['level'].nunique()
    if not (counts==4).all(): raise RuntimeError('Each primary case must contribute all four levels')
    c=z.groupby(['case_id','physical_vm','family'],as_index=False).log_ratio.mean(); c['strata']=c.physical_vm.astype(str)+'_'+c.family.astype(str)
    ratio,ci=bootstrap_logs(c.log_ratio,c.strata,seed)
    try: pv=float(wilcoxon(c.log_ratio.to_numpy(float),alternative='two-sided').pvalue)
    except Exception: pv=1.0
    return {'learned_over_empirical_ratio':ratio,'ci95_ratio':ci,'percent_learned_minus_empirical':(ratio-1)*100.0,'wilcoxon_p_raw':pv,'n_cases':int(len(c)),'aggregation':'mean of four within-case level-specific log ratios'}

def holm2(x,y):
    vals=[x,y]; order=np.argsort(vals); out=[0.,0.]; running=0.
    for rank,i in enumerate(order):
        v=min(1.,(2-rank)*vals[i]); running=max(running,v); out[i]=running
    return out

# Phase A: six concurrent primary lanes.
phaseA=[]
for vm in ['a','b']:
    for lane in range(3): phaseA.append(latest_success(a.results_root/f'vm-{vm}'/f'phaseA_lane{lane}'/'results_success_latest.csv'))
A=pd.concat(phaseA,ignore_index=True)
if len(A)!=6000 or A.run_id.nunique()!=6000: raise RuntimeError(f'Phase A primary incomplete: {len(A)} rows, {A.run_id.nunique()} unique; expected 6000')
if set(A.policy)!=POL or set(A.level)!=set(LEVELS): raise RuntimeError('Phase A policy/level mismatch')
if set(A.phase)!={'phaseA_7core'} or set(A.concurrency_width.astype(int))!={3}: raise RuntimeError('Phase A metadata mismatch')
for key,g in A.groupby(['case_id','level','policy']):
    if len(g)!=5: raise RuntimeError(f'Phase A {key}: expected 5 repeats, got {len(g)}')
    if g.trajectory_hash.nunique()!=1: raise RuntimeError(f'Phase A {key}: trajectory changed across repeats')
verify_against_original(A,'Phase A')

# Phase B: full isolated original A/B schedules.
phaseB=[]
for vm in ['a','b']: phaseB.append(latest_success(a.results_root/f'vm-{vm}'/'phaseB_isolated_full'/'results_success_latest.csv'))
B=pd.concat(phaseB,ignore_index=True)
if len(B)!=6000 or B.run_id.nunique()!=6000: raise RuntimeError(f'Phase B incomplete: {len(B)} rows, {B.run_id.nunique()} unique; expected 6000')
if set(B.policy)!=POL or set(B.level)!=set(LEVELS): raise RuntimeError('Phase B policy/level mismatch')
if set(B.phase)!={'phaseB_isolated_full'} or set(B.concurrency_width.astype(int))!={1}: raise RuntimeError('Phase B metadata mismatch')
for key,g in B.groupby(['case_id','level','policy']):
    if len(g)!=5: raise RuntimeError(f'Phase B {key}: expected 5 repeats, got {len(g)}')
    if g.trajectory_hash.nunique()!=1: raise RuntimeError(f'Phase B {key}: trajectory changed across repeats')
verify_against_original(B,'Phase B')

# Secondary C.
C=latest_success(a.results_root/'vm-c'/'phaseA_lane0'/'results_success_latest.csv')
if len(C)!=500 or C.run_id.nunique()!=500: raise RuntimeError(f'VM-C incomplete: {len(C)} rows; expected 500')
verify_against_original(C,'VM-C')

# Authoritative Phase-B analysis.
aggB=reduce_case(B); aggB.to_csv(a.out_dir/'phaseB_isolated_full_case_medians.csv',index=False); pB=pivot(aggB); pB['strata']=pB.physical_vm.astype(str)+'_'+pB.family.astype(str)
prim={
 'P0_A_overall_L1_L4_learned_pW_vs_empirical_pW':overall_case_effect(pB,'learned_pW','empirical_pW',20261014),
 'P0_B_overall_L1_L4_learned_pC_vs_empirical_pC':overall_case_effect(pB,'learned_pC','empirical_pC',20261015)}
adj=holm2(prim['P0_A_overall_L1_L4_learned_pW_vs_empirical_pW']['wilcoxon_p_raw'],prim['P0_B_overall_L1_L4_learned_pC_vs_empirical_pC']['wilcoxon_p_raw'])
for v,q in zip(prim.values(),adj): v['holm_adjusted_p']=float(q)
phaseB_levels={}
for idx,lev in enumerate(LEVELS):
    x=pB[pB.level.eq(lev)].copy(); phaseB_levels[lev]={
      'learned_pW_vs_empirical_pW':boot_ratio(x,'learned_pW','empirical_pW',1100+idx,stratum_col='strata'),
      'learned_pC_vs_empirical_pC':boot_ratio(x,'learned_pC','empirical_pC',1200+idx,stratum_col='strata')}

# Supporting Phase-A full-regime analysis.
aggA=reduce_case(A); aggA.to_csv(a.out_dir/'phaseA_7core_case_medians.csv',index=False); pA=pivot(aggA); pA['strata']=pA.host_label.astype(str)+'_'+pA.family.astype(str)
phaseA_levels={}
for idx,lev in enumerate(LEVELS):
    x=pA[pA.level.eq(lev)].copy(); phaseA_levels[lev]={
      'learned_pW_vs_empirical_pW':boot_ratio(x,'learned_pW','empirical_pW',300+idx,stratum_col='strata'),
      'learned_pC_vs_empirical_pC':boot_ratio(x,'learned_pC','empirical_pC',400+idx,stratum_col='strata')}

# VM-C descriptive.
aggC=reduce_case(C); pC=pivot(aggC); pC['strata']=pC.host_label.astype(str)+'_'+pC.family.astype(str)
vmc={'learned_pW_vs_empirical_pW':boot_ratio(pC,'learned_pW','empirical_pW',501,stratum_col='strata'),'learned_pC_vs_empirical_pC':boot_ratio(pC,'learned_pC','empirical_pC',502,stratum_col='strata')}

# Historical original-scorer reference for descriptive before/after context only.
old=pd.read_csv(ROOT/'08_REFERENCE'/'original_pipeline_combined_graph_results.csv'); old=old[old.status.eq('SUCCESS')]
oldagg=old.groupby(['case_id','primary_machine','family','level','policy'],as_index=False).end_to_end_wall_ms.median(); oldp=oldagg.pivot(index=['case_id','primary_machine','family','level'],columns='policy',values='end_to_end_wall_ms').reset_index(); oldp=oldp.rename(columns={'primary_machine':'physical_vm'}); oldp['host_label']=oldp.physical_vm; oldp['strata']=oldp.physical_vm.astype(str)+'_'+oldp.family.astype(str)
old_overall={'learned_pW_vs_empirical_pW':overall_case_effect(oldp,'learned_pW','empirical_pW',1601),'learned_pC_vs_empirical_pC':overall_case_effect(oldp,'learned_pC','empirical_pC',1602)}
old_levels={}
for idx,lev in enumerate(LEVELS):
    x=oldp[oldp.level.eq(lev)].copy(); old_levels[lev]={'learned_pW_vs_empirical_pW':boot_ratio(x,'learned_pW','empirical_pW',1700+idx,stratum_col='strata'),'learned_pC_vs_empirical_pC':boot_ratio(x,'learned_pC','empirical_pC',1800+idx,stratum_col='strata')}

scoreB=B[B.policy.str.startswith('learned')].groupby(['level','policy']).agg(mean_model_scoring_ms=('model_scoring_ms','mean'),median_model_scoring_ms=('model_scoring_ms','median'),mean_wall_ms=('end_to_end_wall_ms','mean')).reset_index().to_dict('records')
cvB=aggB.repeat_cv.describe(percentiles=[.5,.9,.95]).to_dict()
result={
 'status':'PASS',
 'authoritative_endpoint':'Phase B full isolated L1-L4 coefficient-only learned-versus-empirical timing',
 'scientific_equivalence_to_original_campaign':True,
 'phaseB_primary_overall_L1_L4':prim,
 'phaseB_secondary_by_level':phaseB_levels,
 'phaseA_full_regime_7core_supporting':phaseA_levels,
 'vmC_descriptive_L4':vmc,
 'historical_original_sklearn_overall_descriptive_reference':old_overall,
 'historical_original_sklearn_by_level_descriptive_reference':old_levels,
 'phaseB_coefficient_scoring_diagnostics':scoreB,
 'phaseB_repeat_cv_summary':{k:float(v) for k,v in cvB.items() if isinstance(v,(float,int,np.floating,np.integer))},
 'interpretation_rule':'Primary P0 inference comes only from full isolated Phase B. Ratio < 1 favors learned; > 1 favors empirical. CI spanning 1 is unresolved because no equivalence margin was prespecified. Per-level Phase-B effects are secondary; Phase A and VM-C are supporting/descriptive and are not pooled with Phase B.',
 'caution':'Historical original-scorer ratios are descriptive context only; campaign-to-campaign changes are not treated as a causal scorer-effect estimate.'
}
(a.out_dir/'P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
md=['# P0 Coefficient-Only Timing Analysis — Full Isolated Confirmation','',f"Status: **{result['status']}**",'', '## Authoritative overall L1-L4 contrasts']
for k,v in prim.items(): md += [f"- **{k}**: learned/empirical = {v['learned_over_empirical_ratio']:.4f}, 95% CI [{v['ci95_ratio'][0]:.4f}, {v['ci95_ratio'][1]:.4f}], Holm p = {v['holm_adjusted_p']:.4g}, n={v['n_cases']}"]
md += ['', '## Secondary isolated effects by level']
for lev,x in phaseB_levels.items():
    for name,v in x.items(): md += [f"- {lev} {name}: ratio = {v['learned_over_empirical_ratio']:.4f}, 95% CI [{v['ci95_ratio'][0]:.4f}, {v['ci95_ratio'][1]:.4f}], n={v['n_cases']}"]
md += ['', 'Phase-A seven-core and VM-C results are supporting only. See the JSON for all prespecified outputs.']
(a.out_dir/'P0_COEFFICIENT_GRAPH_7CORE_FULLISO_ANALYSIS.md').write_text('\n'.join(md)+'\n')
print(json.dumps(result,indent=2))
