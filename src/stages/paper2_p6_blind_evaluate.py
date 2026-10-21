from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,brier_score_loss,log_loss,roc_auc_score

EPS=1e-6

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def clip(p): return np.clip(np.asarray(p,float),EPS,1-EPS)
def basic_metrics(y,p):
 y=np.asarray(y,int); p=clip(p)
 return {
  'log_loss':float(log_loss(y,p,labels=[0,1])),
  'brier':float(brier_score_loss(y,p)),
  'auroc':float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
  'auprc':float(average_precision_score(y,p)) if y.sum()>0 else None,
 }
def calib_params(y,p):
 y=np.asarray(y,int); p=clip(p)
 if len(np.unique(y))<2: return (None,None)
 x=np.log(p/(1-p)).reshape(-1,1)
 m=LogisticRegression(C=1e6,solver='lbfgs',max_iter=2000)
 m.fit(x,y)
 return float(m.intercept_[0]),float(m.coef_[0,0])
def history_prob(df):
 c=df['history_count_same_context'].to_numpy(float); t=df['decision_iteration'].to_numpy(float); h=df['future_horizon'].to_numpy(float)
 lam=(c+0.5)/(t+1.0)
 return clip(1-np.exp(-h*lam))
def eval_all(y,p):
 out=basic_metrics(y,p); ci,cs=calib_params(y,p); out['calibration_intercept']=ci; out['calibration_slope']=cs; return out

def bootstrap(df,y,p,reps=2000,seed=20261005):
 rng=np.random.default_rng(seed)
 keys=df[['domain','instance_seed']].drop_duplicates().apply(tuple,axis=1).tolist()
 idx_by={k:np.where((df.domain==k[0])&(df.instance_seed==k[1]))[0] for k in keys}
 vals={k:[] for k in ['log_loss','brier','auroc','auprc','calibration_intercept','calibration_slope']}
 for _ in range(reps):
  sampled=rng.integers(0,len(keys),size=len(keys)); idx=np.concatenate([idx_by[keys[j]] for j in sampled])
  yy=y[idx]; pp=p[idx]; m=eval_all(yy,pp)
  for k,v in m.items():
   if v is not None and np.isfinite(v): vals[k].append(float(v))
 out={}
 for k,a in vals.items():
  if a: out[k]={'lower':float(np.percentile(a,2.5)),'upper':float(np.percentile(a,97.5)),'valid_replicates':len(a)}
  else: out[k]={'lower':None,'upper':None,'valid_replicates':0}
 return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--out-dir',required=True); a=ap.parse_args()
 base=Path(a.base); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((base/'predictor_development/P6_PREBLIND_RELEASE_MANIFEST.json').read_text())
 fpath=base/'graph_holdout/p56_final_blind_features.csv'; lpath=base/'graph_holdout/p56_final_blind_labels.SEALED.csv'
 assert sha(fpath)==manifest['hashes']['holdout_features']; assert sha(lpath)==manifest['hashes']['holdout_labels']
 feats=pd.read_csv(fpath); labs=pd.read_csv(lpath)
 # join by candidate_id if available; otherwise assert same rows
 if 'candidate_id' in labs.columns and 'candidate_id' in feats.columns:
  df=feats.merge(labs,on='candidate_id',how='inner',validate='one_to_one',suffixes=('','_label'))
 else:
  assert len(feats)==len(labs); df=pd.concat([feats.reset_index(drop=True),labs.reset_index(drop=True)],axis=1)
 assert len(df)==225
 y=df['future_compatible_recurrence'].to_numpy(int)
 model_obj=joblib.load(base/'predictor_development/p6_final_model.joblib'); meta=model_obj['meta']; ff=meta['features']
 if meta['model_family']=='logistic' or meta['model_family']=='hgb': raw=model_obj['model'].predict_proba(df[ff])[:,1]
 elif meta['model_family']=='mlp': raw=np.mean([m.predict_proba(df[ff])[:,1] for m in model_obj['models']],axis=0)
 elif meta['model_family']=='constant': raw=np.full(len(df),model_obj['constant_probability'])
 elif meta['model_family']=='history': raw=history_prob(df)
 else: raise ValueError(meta['model_family'])
 raw=clip(raw)
 cal_obj=joblib.load(base/'predictor_development/p6_calibration.joblib')
 if cal_obj['choice']=='platt':
  x=np.log(raw/(1-raw)).reshape(-1,1); p=clip(cal_obj['platt'].predict_proba(x)[:,1])
 else: p=raw
 dev=json.loads((base/'predictor_development/P6_DEVELOPMENT_SUMMARY.json').read_text())
 p_const=np.full(len(df),dev['target_prevalence'],dtype=float)
 p_hist=history_prob(df)
 res={
  'release_status':'ONE_TIME_BLIND_TEST_RELEASED_NO_RETUNING_ALLOWED',
  'rows':int(len(df)),
  'independent_cases':int(df[['domain','instance_seed']].drop_duplicates().shape[0]),
  'target_prevalence':float(y.mean()),
  'selected_model':meta,
  'selected_model_raw':eval_all(y,raw),
  'selected_model_final':eval_all(y,p),
  'constant_development_prevalence_baseline':eval_all(y,p_const),
  'history_frequency_baseline':eval_all(y,p_hist),
  'selected_model_case_bootstrap_95pct':bootstrap(df,y,p,2000,20261005),
  'label_sha256':sha(lpath),
  'feature_sha256':sha(fpath),
 }
 # descriptive domains only, no tuning
 domains={}
 for d,g in df.assign(_p=p,_raw=raw).groupby('domain'):
  domains[d]={'rows':int(len(g)),'cases':int(g.instance_seed.nunique()),'target_prevalence':float(g.future_compatible_recurrence.mean()),'metrics':eval_all(g.future_compatible_recurrence.to_numpy(int),g._p.to_numpy(float))}
 res['domain_descriptive']=domains
 pred=df[['case_id','domain','instance_seed','decision_iteration','candidate_id','future_compatible_recurrence']].copy()
 pred['raw_probability']=raw; pred['final_probability']=p; pred['constant_probability']=p_const; pred['history_probability']=p_hist
 pred.to_csv(out/'p6_blind_predictions.csv',index=False)
 (out/'P6_BLIND_TEST_RESULTS.json').write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
 (out/'P6_BLIND_LABEL_RELEASE_MARKER.json').write_text(json.dumps({'released':True,'label_sha256':sha(lpath),'preblind_manifest_sha256':sha(base/'predictor_development/P6_PREBLIND_RELEASE_MANIFEST.json'),'rule':'No model/feature/hyperparameter/calibration changes may be made in response to these results.'},indent=2,sort_keys=True)+'\n')
 print(json.dumps(res,indent=2,sort_keys=True))
if __name__=='__main__': main()
