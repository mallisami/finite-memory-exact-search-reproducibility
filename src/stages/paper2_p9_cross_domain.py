from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score,average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler

TARGET='future_compatible_recurrence'; EPS=1e-6
CATS=['current_destroy_op_index','current_repair_arm_index']
FEATS=['history_count_same_context','iterations_since_last_context','recent_same_context_count_20','current_destroy_op_index','current_repair_arm_index','current_objective_before','current_best_objective','current_temperature','recent_accept_rate_10','recent_accept_rate_20','recent_moved_node_overlap_10','recent_adjacent_move_count_10','recent_moved_node_overlap_20','recent_adjacent_move_count_20','objective_improvement_last_10','objective_improvement_last_20']
DOMAINS=['generic','workflow','microservice']

def clip(p): return np.clip(np.asarray(p,float),EPS,1-EPS)
def metrics(y,p):
 p=clip(p);y=np.asarray(y,int)
 return {'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),'auroc':float(roc_auc_score(y,p)),'auprc':float(average_precision_score(y,p))}
def histprob(d):
 lam=(d.history_count_same_context.to_numpy(float)+0.5)/(d.decision_iteration.to_numpy(float)+1.0)
 return clip(1-np.exp(-d.future_horizon.to_numpy(float)*lam))
def build_model():
 cats=[c for c in CATS if c in FEATS];nums=[c for c in FEATS if c not in cats]
 ct=ColumnTransformer([('num',StandardScaler(),nums),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)],remainder='drop',sparse_threshold=0.0)
 return Pipeline([('prep',ct),('clf',LogisticRegression(C=10.0,solver='lbfgs',max_iter=2000))])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dataset',required=True);ap.add_argument('--out-dir',required=True);a=ap.parse_args()
 df=pd.read_csv(a.dataset);out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);rows=[];preds=[]
 seeds=sorted(df.instance_seed.unique())
 seed_fold={int(s):i%5 for i,s in enumerate(seeds)}
 for held in DOMAINS:
  tr=df[df.domain!=held].copy();te=df[df.domain==held].copy();ytr=tr[TARGET].to_numpy(int);yte=te[TARGET].to_numpy(int)
  oof=np.full(len(tr),np.nan)
  for k in range(5):
   mask=tr.instance_seed.map(seed_fold).to_numpy()==k
   m=build_model();m.fit(tr.loc[~mask,FEATS],ytr[~mask]);oof[mask]=m.predict_proba(tr.loc[mask,FEATS])[:,1]
  lg=np.log(clip(oof)/(1-clip(oof))).reshape(-1,1);cal=LogisticRegression(C=1e6,solver='lbfgs',max_iter=2000);cal.fit(lg,ytr)
  m=build_model();m.fit(tr[FEATS],ytr);raw=clip(m.predict_proba(te[FEATS])[:,1]);logit=np.log(raw/(1-raw)).reshape(-1,1);p=clip(cal.predict_proba(logit)[:,1])
  const=np.full(len(te),float(ytr.mean()));hist=histprob(te)
  for name,prob in [('prevalence',const),('history',hist),('logistic_HD',p)]: rows.append({'held_out_domain':held,'model':name,'n_cases':te[['domain','instance_seed']].drop_duplicates().shape[0],'n_rows':len(te),'prevalence':float(yte.mean()),**metrics(yte,prob)})
  z=te[['case_id','domain','instance_seed','decision_iteration','candidate_id',TARGET]].copy();z['prediction']=p;z['held_out_domain']=held;preds.append(z)
 pd.DataFrame(rows).to_csv(out/'p9_cross_domain_metrics.csv',index=False);pd.concat(preds,ignore_index=True).to_csv(out/'p9_cross_domain_predictions.csv',index=False)
 r=pd.DataFrame(rows);model=r[r.model=='logistic_HD'];summary={'status':'P9_cross_domain_complete','held_out_domains':DOMAINS,'macro_log_loss':float(model.log_loss.mean()),'macro_brier':float(model.brier.mean()),'macro_auroc':float(model.auroc.mean()),'macro_auprc':float(model.auprc.mean()),'all_three_beat_prevalence_logloss':bool(all(model.set_index('held_out_domain').log_loss<r[r.model=='prevalence'].set_index('held_out_domain').log_loss)),'all_three_beat_history_logloss':bool(all(model.set_index('held_out_domain').log_loss<r[r.model=='history'].set_index('held_out_domain').log_loss))}
 (out/'P9_CROSS_DOMAIN_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(json.dumps(summary,indent=2,sort_keys=True));print(r.to_string(index=False))
if __name__=='__main__':main()
