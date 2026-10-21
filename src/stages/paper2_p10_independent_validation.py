from __future__ import annotations
import argparse, json, math, time, os, platform, sys, hashlib
from pathlib import Path
import importlib.metadata as md
import numpy as np, pandas as pd
from scipy.stats import wilcoxon

from independent_mdkp.controller import run_live_policy, build_prediction_dataset, P10Predictor, P10_FEATURES
from independent_mdkp.model import fit_p10_model, evaluate_p10_model

PRIMARY_ENDPOINTS=(
    'primary_mechanistic_learned_minus_empirical_reused_prior_nodes',
    'primary_operational_empirical_minus_learned_new_nodes',
    'primary_wallclock_restart_minus_learned_ms',
)

TIMING_COMPONENTS=(
    'serialization_ms','restoration_ms','selection_ms','model_scoring_ms','repair_search_ms','end_to_end_ms',
)


def load_cfg(path): return json.loads(Path(path).read_text())

def _sha(path:Path):
    h=hashlib.sha256();
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def _guard_absent(paths):
    exists=[str(p) for p in paths if Path(p).exists()]
    if exists: raise FileExistsError('authoritative P10 output already exists; use a fresh output directory rather than overwriting: '+', '.join(exists[:4]))

def _validate_cfg(cfg):
    groups={
        'screen':set(cfg['screen']['seeds']),
        'development':set(cfg['prediction']['development_seeds']),
        'holdout':set(cfg['prediction']['sealed_holdout_seeds']),
        'confirmatory':set(cfg['confirmatory']['seeds']),
        'warmup':{cfg['screen']['warmup_seed'],cfg['confirmatory']['timing_warmup_seed']},
    }
    names=list(groups)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            if groups[a]&groups[b]: raise ValueError(f'P10 seed blocks overlap: {a}/{b}: {sorted(groups[a]&groups[b])}')
    expected=tuple(cfg['prediction']['feature_contract'])
    if expected!=tuple(P10_FEATURES): raise ValueError('P10 feature contract does not match frozen config')
    forbidden=set(cfg['prediction'].get('forbidden_privileged_features',[]))
    if forbidden.intersection(P10_FEATURES): raise ValueError('privileged generator feature entered P10 predictor')

def boot(x,seed=101001,reps=10000):
    a=np.asarray(x,dtype=float); a=a[np.isfinite(a)]
    rng=np.random.default_rng(seed); idx=rng.integers(0,len(a),size=(reps,len(a))); m=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(m,.025)),float(np.quantile(m,.975))

def _one_sided_wilcoxon_greater(x):
    a=np.asarray(x,dtype=float); a=a[np.isfinite(a)]
    if len(a)==0 or np.allclose(a,0): return 1.0
    try: return float(wilcoxon(a,alternative='greater',zero_method='wilcox',method='auto').pvalue)
    except ValueError: return 1.0

def _holm(pairs):
    pairs=sorted(pairs,key=lambda z:z[1]); m=len(pairs); out={}; running=0.0
    for i,(name,p) in enumerate(pairs):
        adj=min(1.0,(m-i)*float(p)); running=max(running,adj); out[name]=running
    return out

def selection_path(out): return Path(out)/'screen'/'p10_screen_selection.json'

def _screen_cells(sc):
    return sc.get('candidate_cells') or [{'n_items':n,'destroy_size':d} for n in sc['n_items'] for d in sc['destroy_sizes']]

def screen(cfg,out):
    sc=cfg['screen']; od=Path(out)/'screen'; _guard_absent([od/'p10_screen_selection.json',od/'p10_screen_runs.csv']); od.mkdir(parents=True,exist_ok=True)
    cells=list(_screen_cells(sc))
    # Non-authoritative warm-up prevents the first candidate cell from paying one-time interpreter/cache costs.
    mid=cells[len(cells)//2]
    run_live_policy(seed=int(sc['warmup_seed']),n_items=int(mid['n_items']),destroy_size=int(mid['destroy_size']),slice_nodes=min(int(sc['slice_nodes']),64),iterations=20,policy='keep_all',context_count=min(int(sc['context_count']),8))
    rows=[]
    # Interleave/rotate candidate cells within each screen seed so timing rank is not confounded with fixed cell order.
    for si,seed in enumerate(sc['seeds']):
        rot=si%len(cells); ordered=cells[rot:]+cells[:rot]
        for cell in ordered:
            n=int(cell['n_items']); d=int(cell['destroy_size'])
            r,_=run_live_policy(seed=seed,n_items=n,destroy_size=d,slice_nodes=sc['slice_nodes'],iterations=sc['iterations'],policy='keep_all',context_count=sc['context_count'])
            r['screen_order_index']=len(rows); rows.append(r); print('screen',seed,n,d,flush=True)
    df=pd.DataFrame(rows); df.to_csv(od/'p10_screen_runs.csv',index=False)
    ag=[]
    for (n,d),g in df.groupby(['n_items','destroy_size']):
        peak=float(g.peak_checkpoint_bytes.median()); maxcp=float(g.max_checkpoint_size_bytes.median())
        ag.append(dict(n_items=int(n),destroy_size=int(d),cases=len(g),
          median_peak_live_checkpoints=float(g.peak_live_checkpoints.median()),
          median_fraction_iterations_live_ge4=float(g.fraction_iterations_live_ge4.median()),
          median_useful_resumes=float(g.useful_resumes.median()),
          median_repair_ms_per_decision=float((g.repair_search_ms/g.iterations).median()),
          median_peak_checkpoint_bytes=peak,median_max_checkpoint_size_bytes=maxcp,
          median_max_checkpoint_to_peak_ratio=float(maxcp/max(peak,1.0))))
    a=pd.DataFrame(ag); e=sc['eligibility']
    a['eligible']=(a.median_peak_live_checkpoints>=e['median_peak_live_checkpoints_min']) & (a.median_fraction_iterations_live_ge4>=e['median_fraction_iterations_live_ge4_min']) & (a.median_useful_resumes>=e['median_useful_resumes_min']) & (a.median_max_checkpoint_to_peak_ratio<=e['median_max_checkpoint_to_peak_ratio_max'])
    a.to_csv(od/'p10_screen_aggregate.csv',index=False)
    q=a[a.eligible].copy()
    if q.empty: raise RuntimeError('P10 screen found no eligible cell; protocol requires halt rather than outcome-driven fallback.')
    q=q.sort_values(['median_repair_ms_per_decision','median_fraction_iterations_live_ge4','median_peak_live_checkpoints'],ascending=False)
    w=q.iloc[0]
    M=max(int(round(w.median_max_checkpoint_size_bytes)),int(round(.25*w.median_peak_checkpoint_bytes)))
    sel={'n_items':int(w.n_items),'destroy_size':int(w.destroy_size),'slice_nodes':int(sc['slice_nodes']),'context_count':int(sc['context_count']),
         'primary_budget_bytes':int(M),'screen_cases_per_cell':int(w.cases),
         'screen_cell':{k:(bool(v) if k=='eligible' else float(v) if isinstance(v,(np.floating,float)) else int(v) if isinstance(v,(np.integer,int)) else v) for k,v in w.to_dict().items()},
         'selection_rule':sc['selection_rule'],'budget_rule':sc['primary_memory_budget_rule']}
    (od/'p10_screen_selection.json').write_text(json.dumps(sel,indent=2,sort_keys=True)+'\n')
    return sel

def _sel(out):
    p=selection_path(out)
    if not p.exists(): raise FileNotFoundError(f'run screen first: {p}')
    return json.loads(p.read_text())

def development(cfg,out):
    sel=_sel(out); pc=cfg['prediction']; od=Path(out)/'development'; _guard_absent([od/'p10_development_dataset.csv',od/'P10_MODEL_SUMMARY.json',od/'p10_final_model.joblib']); od.mkdir(parents=True,exist_ok=True)
    df=build_prediction_dataset(seeds=pc['development_seeds'],n_items=sel['n_items'],destroy_size=sel['destroy_size'],slice_nodes=sel['slice_nodes'],iterations=pc['iterations'],context_count=sel['context_count'],horizon=pc['future_horizon'])
    df.to_csv(od/'p10_development_dataset.csv',index=False); return fit_p10_model(df,od)

def blind(cfg,out):
    sel=_sel(out); pc=cfg['prediction']; od=Path(out)/'blind_holdout'; _guard_absent([od/'p10_blind_dataset.csv',od/'P10_BLIND_METRICS.json',od/'p10_blind_predictions.csv']); od.mkdir(parents=True,exist_ok=True)
    df=build_prediction_dataset(seeds=pc['sealed_holdout_seeds'],n_items=sel['n_items'],destroy_size=sel['destroy_size'],slice_nodes=sel['slice_nodes'],iterations=pc['iterations'],context_count=sel['context_count'],horizon=pc['future_horizon'])
    df.to_csv(od/'p10_blind_dataset.csv',index=False); return evaluate_p10_model(df,Path(out)/'development',od)

def _deterministic_signature(r):
    keys=['seed','final_cost','best_cost','branch_nodes_executed','useful_resumes','reused_prior_nodes','checkpoint_creations','capacity_evictions','invalidation_evictions','peak_checkpoint_bytes','byte_time','peak_live_checkpoints','accepted_moves']
    return tuple(r[k] for k in keys)

LATIN4=((0,1,3,2),(1,2,0,3),(2,3,1,0),(3,0,2,1))
def policy_order(seed,rep,policies):
    if len(policies)!=4: raise ValueError('P10 counterbalanced timing design requires four policies')
    row=LATIN4[(int(seed)+int(rep))%4]
    return [policies[i] for i in row]

def _environment_record(cfg):
    packages={}
    for name in ['numpy','scipy','scikit-learn','pandas','joblib','pytest']:
        try: packages[name]=md.version(name)
        except Exception: packages[name]='unavailable'
    cpu_model=''
    try:
        for line in Path('/proc/cpuinfo').read_text(errors='ignore').splitlines():
            if line.lower().startswith('model name'):
                cpu_model=line.split(':',1)[1].strip(); break
    except Exception: pass
    affinity=None
    try:
        if hasattr(os,'sched_getaffinity'): affinity=sorted(int(x) for x in os.sched_getaffinity(0))
    except Exception: pass
    loadavg=None
    try: loadavg=[float(x) for x in os.getloadavg()]
    except Exception: pass
    mem_total_kib=None
    try:
        for line in Path('/proc/meminfo').read_text(errors='ignore').splitlines():
            if line.startswith('MemTotal:'):
                mem_total_kib=int(line.split()[1]); break
    except Exception: pass
    governor=None
    try:
        gp=Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')
        if gp.exists(): governor=gp.read_text().strip()
    except Exception: pass
    return {
        'python':sys.version.split()[0],'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),
        'cpu_model':cpu_model,'logical_cpu_count':os.cpu_count(),'process_cpu_affinity':affinity,'load_average_before_confirmatory':loadavg,
        'memory_total_kib':mem_total_kib,'cpu_scaling_governor':governor,'packages':packages,
        'thread_environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONHASHSEED']},
        'timing_scope':'controller execution only; excludes one-time model loading, instance generation, and context-trace construction',
        'timing_design':cfg['confirmatory']['timing_design'],
    }

def _source_fingerprints():
    code_dir=Path(__file__).resolve().parents[1]
    paths=[Path(__file__).resolve(),code_dir/'independent_mdkp/core.py',code_dir/'independent_mdkp/controller.py',code_dir/'independent_mdkp/model.py',code_dir/'independent_mdkp/allocation.py']
    return {str(x.relative_to(code_dir.parent)):_sha(x) for x in paths}

def _package_manifest_hash():
    root=Path(__file__).resolve().parents[2]
    for p in (root/'PACKAGE_MANIFEST_SHA256.csv',):
        if p.exists(): return {'path':str(p.relative_to(root)),'sha256':_sha(p)}
    return None

def _warm_timing(sel,cc,pred):
    seed=int(cc['timing_warmup_seed']); policies=list(cc['policies'])
    for pol in policy_order(seed,0,policies):
        run_live_policy(seed=seed,n_items=sel['n_items'],destroy_size=sel['destroy_size'],slice_nodes=min(sel['slice_nodes'],96),iterations=30,policy=pol,context_count=sel['context_count'],budget_bytes=None if pol in ('restart','keep_all') else sel['primary_budget_bytes'],predictor=pred if pol=='learned' else None)

def confirm(cfg,out,timing_repeats=None):
    sel=_sel(out); cc=cfg['confirmatory']; frozen=int(cc['timing_repeats_per_case_policy'])
    if timing_repeats is not None and int(timing_repeats)!=frozen: raise ValueError('authoritative P10 timing repeats are frozen; use the configured value')
    blind_marker=Path(out)/'blind_holdout/P10_BLIND_METRICS.json'
    if not blind_marker.exists(): raise FileNotFoundError('sealed holdout stage must complete before confirmatory execution: '+str(blind_marker))
    reps=frozen; od=Path(out)/'confirmatory'; _guard_absent([od/'p10_confirmatory_runs.csv',od/'p10_timing_repeats.csv',od/'p10_confirmatory_inference.csv',od/'p10_policy_descriptives.csv',od/'P10_CONFIRMATORY_SUMMARY.json',od/'P10_EXECUTION_SEAL.json']); od.mkdir(parents=True,exist_ok=True)
    pred=P10Predictor(Path(out)/'development/p10_final_model.joblib',Path(out)/'development/p10_calibration.joblib')
    env_path=od/'P10_ENVIRONMENT.json'; env_path.write_text(json.dumps(_environment_record(cfg),indent=2,sort_keys=True)+'\n')
    _warm_timing(sel,cc,pred)
    rows=[]; timing=[]; policies=list(cc['policies'])
    for seed in cc['seeds']:
        bypol={p:[] for p in policies}
        for rep in range(reps):
            order=policy_order(seed,rep,policies)
            for pos,pol in enumerate(order,1):
                r,_=run_live_policy(seed=seed,n_items=sel['n_items'],destroy_size=sel['destroy_size'],slice_nodes=sel['slice_nodes'],iterations=cc['iterations'],policy=pol,context_count=sel['context_count'],budget_bytes=None if pol in ('restart','keep_all') else sel['primary_budget_bytes'],predictor=pred if pol=='learned' else None)
                bypol[pol].append(r)
                tr={'seed':seed,'policy':pol,'repeat':rep+1,'execution_position':pos}
                tr.update({k:float(r[k]) for k in TIMING_COMPONENTS}); timing.append(tr)
        for pol in policies:
            runs=bypol[pol]; sig=_deterministic_signature(runs[0])
            if any(_deterministic_signature(z)!=sig for z in runs[1:]): raise RuntimeError(f'nondeterministic scientific counters for seed {seed} policy {pol}')
            base=dict(runs[0]); base['timing_repeats']=reps; base['timing_aggregation']='median_of_repeats'
            for k in TIMING_COMPONENTS:
                med=float(np.median([z[k] for z in runs])); base[k]=med; base['median_'+k]=med
            rows.append(base)
            print('confirm',seed,pol,'median_ms',base['median_end_to_end_ms'],flush=True)
    df=pd.DataFrame(rows); timing_df=pd.DataFrame(timing); df.to_csv(od/'p10_confirmatory_runs.csv',index=False); timing_df.to_csv(od/'p10_timing_repeats.csv',index=False)
    piv={p:df[df.policy==p].set_index('seed').sort_index() for p in policies}
    expected=set(map(int,cc['seeds']))
    for pol,q in piv.items():
        if set(map(int,q.index))!=expected: raise RuntimeError(f'missing/extra confirmatory case for policy {pol}')
    L=piv['learned'];E=piv['empirical_compatible'];R=piv['restart'];K=piv['keep_all']
    effects={
      'primary_mechanistic_learned_minus_empirical_reused_prior_nodes':L.reused_prior_nodes-E.reused_prior_nodes,
      'primary_operational_empirical_minus_learned_new_nodes':E.branch_nodes_executed-L.branch_nodes_executed,
      'primary_wallclock_restart_minus_learned_ms':R.median_end_to_end_ms-L.median_end_to_end_ms,
      'secondary_incremental_wallclock_empirical_minus_learned_ms':E.median_end_to_end_ms-L.median_end_to_end_ms,
      'secondary_restart_minus_learned_new_nodes':R.branch_nodes_executed-L.branch_nodes_executed,
      'secondary_mechanistic_learned_minus_empirical_useful_resumes':L.useful_resumes-E.useful_resumes,
      'secondary_memory_learned_minus_empirical_byte_time':L.byte_time-E.byte_time,
      'secondary_memory_learned_minus_empirical_peak_checkpoint_bytes':L.peak_checkpoint_bytes-E.peak_checkpoint_bytes,
      'secondary_capacity_evictions_learned_minus_empirical':L.capacity_evictions-E.capacity_evictions,
      'secondary_invalidation_evictions_learned_minus_empirical':L.invalidation_evictions-E.invalidation_evictions,
      'downstream_relative_best_objective_learned_vs_restart':(R.best_cost-L.best_cost)/np.maximum(np.abs(R.best_cost),1.0),
      'secondary_relative_best_objective_learned_vs_empirical':(E.best_cost-L.best_cost)/np.maximum(np.abs(E.best_cost),1.0),
    }
    rawp={name:_one_sided_wilcoxon_greater(effects[name].values) for name in PRIMARY_ENDPOINTS}; holm=_holm(list(rawp.items()))
    inf=[]
    for j,(name,x) in enumerate(effects.items()):
        m,lo,hi=boot(x.values,seed=101001+j); row={'endpoint':name,'n_cases':len(x),'mean_paired_effect':m,'bootstrap_95_low':lo,'bootstrap_95_high':hi,'median_paired_effect':float(np.median(x.values)),'positive_cases':int((x>0).sum()),'negative_cases':int((x<0).sum()),'ties':int((x==0).sum())}
        if name in rawp: row.update({'wilcoxon_one_sided_p':rawp[name],'holm_adjusted_p_primary_family':holm[name]})
        inf.append(row)
    infdf=pd.DataFrame(inf); infdf.to_csv(od/'p10_confirmatory_inference.csv',index=False)
    desc=[]
    desc_metrics=['reused_prior_nodes','useful_resumes','branch_nodes_executed','median_end_to_end_ms','median_serialization_ms','median_restoration_ms','median_selection_ms','median_model_scoring_ms','median_repair_search_ms','byte_time','peak_checkpoint_bytes','peak_live_checkpoints','capacity_evictions','invalidation_evictions','checkpoint_creations','best_cost','final_cost']
    for pol in policies:
        q=piv[pol]
        row={'policy':pol,'n_cases':len(q)}
        for metric in desc_metrics:
            vals=np.asarray(q[metric],dtype=float); row['mean_'+metric]=float(np.mean(vals)); row['median_'+metric]=float(np.median(vals))
        desc.append(row)
    pd.DataFrame(desc).to_csv(od/'p10_policy_descriptives.csv',index=False)
    summary={'selected_regime':sel,'cases':len(cc['seeds']),'timing_repeats':reps,'timing_design':cc['timing_design'],'primary_family_adjustment':cc['primary_family_adjustment'],'endpoint_roles':{k:cc[k] for k in ['primary_mechanistic_endpoint','primary_operational_endpoint','primary_wall_clock_endpoint','downstream_optimization_endpoint']},'inference':inf,'policy_descriptives_file':'p10_policy_descriptives.csv','keep_all_role':'upper-resource descriptive reference; no common-trajectory oracle interpretation'}
    sum_path=od/'P10_CONFIRMATORY_SUMMARY.json'; sum_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    files=[od/'p10_confirmatory_runs.csv',od/'p10_timing_repeats.csv',od/'p10_confirmatory_inference.csv',od/'p10_policy_descriptives.csv',sum_path,env_path]
    seal={'config_sha256':_sha(Path(cfg['_config_path'])) if '_config_path' in cfg else None,'source_sha256':_source_fingerprints(),'package_manifest':_package_manifest_hash(),'environment_sha256':_sha(env_path),'result_sha256':{p.name:_sha(p) for p in files},'status':'AUTHORITATIVE_P10_CONFIRMATORY_COMPLETED'}
    (od/'P10_EXECUTION_SEAL.json').write_text(json.dumps(seal,indent=2,sort_keys=True)+'\n')
    return summary

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('stage',choices=['screen','development','blind','confirmatory','all']); ap.add_argument('--config',required=True); ap.add_argument('--out-dir',required=True); ap.add_argument('--timing-repeats',type=int,default=None); a=ap.parse_args()
    cfg=load_cfg(a.config); cfg['_config_path']=str(Path(a.config).resolve()); _validate_cfg(cfg); Path(a.out_dir).mkdir(parents=True,exist_ok=True)
    if a.stage in ('screen','all'): screen(cfg,a.out_dir)
    if a.stage in ('development','all'): development(cfg,a.out_dir)
    if a.stage in ('blind','all'): blind(cfg,a.out_dir)
    if a.stage in ('confirmatory','all'): confirm(cfg,a.out_dir,a.timing_repeats)
if __name__=='__main__': main()
