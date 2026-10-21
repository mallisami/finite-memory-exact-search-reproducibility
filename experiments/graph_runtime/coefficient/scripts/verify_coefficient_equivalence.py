#!/usr/bin/env python3
from pathlib import Path
import json,sys,joblib,numpy as np,pandas as pd,tempfile,shutil
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'04_SOURCE'; EXT=SRC/'pcr_tx_extension'; sys.path.insert(0,str(SRC)); sys.path.insert(0,str(EXT))
from fast_p6_predictor import FrozenP6CoefficientPredictor
from pcr_tx_extension.certified_assignment.paper2_online_pilot import FrozenP6Predictor,generate_replay_trace
from pcr_tx_extension.certified_assignment.pcr_graph_engine import run_graph_campaign_case
model=ROOT/'05_MODELS'/'p6_final_model.joblib'; calp=ROOT/'05_MODELS'/'p6_calibration.joblib'; fast=FrozenP6CoefficientPredictor(model,calp)
obj=joblib.load(model); cal=joblib.load(calp); pipe=obj['model']; df=pd.read_csv(ROOT/'10_VERIFICATION'/'p56_final_blind_features.csv'); stored=pd.read_csv(ROOT/'10_VERIFICATION'/'p6_blind_predictions.csv')
vals=np.asarray([fast.predict(r) for r in df[obj['meta']['features']].to_dict('records')]); raw=np.clip(pipe.predict_proba(df[obj['meta']['features']])[:,1],1e-6,1-1e-6); logits=np.log(raw/(1-raw)).reshape(-1,1); pp=np.clip(cal['platt'].predict_proba(logits)[:,1],1e-6,1-1e-6)
held={'rows':len(df),'max_abs_fast_vs_pipeline':float(np.max(np.abs(vals-pp))),'max_abs_fast_vs_retained':float(np.max(np.abs(vals-stored.final_probability.to_numpy(float))))}
if held['max_abs_fast_vs_pipeline']>=1e-12: raise SystemExit('Held-out scorer equivalence failed')
with tempfile.TemporaryDirectory() as td:
    b=Path(td); d=b/'03_P6_Predictor_Development'; d.mkdir(); shutil.copy2(model,d/'p6_final_model.joblib'); shutil.copy2(calp,d/'p6_calibration.joblib'); slow=FrozenP6Predictor(b)
    weights=json.load(open(ROOT/'06_FROZEN_INPUTS'/'PRIMARY_A_CALIBRATION.json'))['graph']['integer_weights']; pairs=[]
    fam,seed='generic',3301
    trace=generate_replay_trace(fam,seed,iterations=10,destroy_size=12)
    lev,pops='L1',8
    for pol in ['learned_pW','learned_pC']:
      a=run_graph_campaign_case(domain=fam,seed=seed,trace=trace,policy_name=pol,slice_pops=pops,budget_bytes=750000,predictor=slow,compute_weights=weights); bres=run_graph_campaign_case(domain=fam,seed=seed,trace=trace,policy_name=pol,slice_pops=pops,budget_bytes=750000,predictor=fast,compute_weights=weights)
      keys=['trajectory_hash','accepted_moves','branch_pops_executed','useful_resumes','reused_prior_branch_pops','checkpoint_creations','capacity_evictions','invalidation_evictions','final_objective','best_objective','peak_bytes','byte_time']; mism=[k for k in keys if getattr(a,k)!=getattr(bres,k)]; pairs.append({'family':fam,'seed':seed,'level':lev,'iterations':10,'policy':pol,'mismatches':mism})
      if mism: raise SystemExit(f'Campaign equivalence failed: {pairs[-1]}')
report={'status':'PASS','heldout':held,'development_campaign_pairs':pairs,'note':'Timing fields intentionally excluded from equivalence.'}; (ROOT/'09_RESULTS'/'COEFFICIENT_EQUIVALENCE_PREEXECUTION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps(report,indent=2))
