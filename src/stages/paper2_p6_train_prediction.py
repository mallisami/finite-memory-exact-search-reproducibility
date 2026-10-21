from __future__ import annotations
import argparse, hashlib, json, math, warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits
warnings.filterwarnings('ignore', category=ConvergenceWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

EPS=1e-6; TARGET='future_compatible_recurrence'; CATS=['current_destroy_op_index','current_repair_arm_index']
SEEDS=[101,202,303,404,505,606,707,808,909,1010,1111,1212,1313,1414,1515]
MLP_SEEDS=[17,29,43]
F={
'H':['history_count_same_context','iterations_since_last_context','recent_same_context_count_20'],
'S':['invested_branch_pops','checkpoint_bytes','additive_gap_at_checkpoint','queue_size','partial_branches_pruned','child_branches_generated','root_upper_bound'],
'D':['current_destroy_op_index','current_repair_arm_index','current_objective_before','current_best_objective','current_temperature','recent_accept_rate_10','recent_accept_rate_20','recent_moved_node_overlap_10','recent_adjacent_move_count_10','recent_moved_node_overlap_20','recent_adjacent_move_count_20','objective_improvement_last_10','objective_improvement_last_20']}
F['H+S']=F['H']+F['S']; F['H+D']=F['H']+F['D']; F['H+S+D']=F['H']+F['S']+F['D']

def clip(p): return np.clip(np.asarray(p,float),EPS,1-EPS)
def mets(y,p):
    p=clip(p); y=np.asarray(y,int)
    return dict(log_loss=float(log_loss(y,p,labels=[0,1])),brier=float(brier_score_loss(y,p)),auroc=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else np.nan,auprc=float(average_precision_score(y,p)) if y.sum()>0 else np.nan)
def fold(seed): return SEEDS.index(int(seed))%5
def histprob(d):
    lam=(d.history_count_same_context.to_numpy(float)+0.5)/(d.decision_iteration.to_numpy(float)+1.0)
    return clip(1-np.exp(-d.future_horizon.to_numpy(float)*lam))
def sha(path):
    h=hashlib.sha256();
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def prep_fold(df, feats, tr, va, standardize):
    cats=[c for c in CATS if c in feats]; nums=[c for c in feats if c not in cats]
    trs=[]
    if nums: trs.append(('num',StandardScaler() if standardize else 'passthrough',nums))
    if cats: trs.append(('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats))
    ct=ColumnTransformer(trs,remainder='drop',sparse_threshold=0.0)
    Xtr=ct.fit_transform(df.loc[tr,feats]); Xva=ct.transform(df.loc[va,feats])
    return Xtr,Xva,ct

def fit_task(family,cfg,ff,fld,Xtr,Xva,ytr,yva):
    with threadpool_limits(limits=1):
        if family=='logistic':
            m=LogisticRegression(C=cfg['C'],solver='lbfgs',max_iter=2000)
            m.fit(Xtr,ytr); p=m.predict_proba(Xva)[:,1]
        elif family=='hgb':
            m=HistGradientBoostingClassifier(learning_rate=cfg['learning_rate'],max_leaf_nodes=cfg['max_leaf_nodes'],max_iter=cfg['max_iter'],l2_regularization=cfg['l2_regularization'],random_state=17)
            m.fit(Xtr,ytr); p=m.predict_proba(Xva)[:,1]
        elif family=='mlp':
            ps=[]
            for s in MLP_SEEDS:
                m=MLPClassifier(hidden_layer_sizes=tuple(cfg['hidden_layer_sizes']),alpha=cfg['alpha'],learning_rate_init=1e-3,max_iter=500,random_state=s,early_stopping=False)
                m.fit(Xtr,ytr); ps.append(m.predict_proba(Xva)[:,1])
            p=np.mean(ps,axis=0)
        else: raise ValueError(family)
    return family,ff,json.dumps(cfg,sort_keys=True,separators=(',',':')),fld,clip(p),mets(yva,p)

def build_final_model(family,cfg,feats,df,y):
    cats=[c for c in CATS if c in feats]; nums=[c for c in feats if c not in cats]
    def ct(std):
        trs=[]
        if nums: trs.append(('num',StandardScaler() if std else 'passthrough',nums))
        if cats: trs.append(('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats))
        return ColumnTransformer(trs,remainder='drop',sparse_threshold=0.0)
    if family=='logistic':
        p=Pipeline([('prep',ct(True)),('clf',LogisticRegression(C=cfg['C'],solver='lbfgs',max_iter=2000))]); p.fit(df[feats],y); return {'model':p}
    if family=='hgb':
        p=Pipeline([('prep',ct(False)),('clf',HistGradientBoostingClassifier(learning_rate=cfg['learning_rate'],max_leaf_nodes=cfg['max_leaf_nodes'],max_iter=cfg['max_iter'],l2_regularization=cfg['l2_regularization'],random_state=17))]); p.fit(df[feats],y); return {'model':p}
    if family=='mlp':
        ms=[]
        for s in MLP_SEEDS:
            p=Pipeline([('prep',ct(True)),('clf',MLPClassifier(hidden_layer_sizes=tuple(cfg['hidden_layer_sizes']),alpha=cfg['alpha'],learning_rate_init=1e-3,max_iter=500,random_state=s,early_stopping=False))]); p.fit(df[feats],y); ms.append(p)
        return {'models':ms}
    return {}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--firewall',required=True); ap.add_argument('--out-dir',required=True); ap.add_argument('--jobs',type=int,default=5); a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(a.dataset); fw=json.load(open(a.firewall)); assert set(F['H+S+D'])==set(fw['allowed_model_features'])
    df['cv_fold']=[fold(s) for s in df.instance_seed]; y=df[TARGET].to_numpy(int)
    rows=[]; oofs={}
    # baselines
    for fam in ['constant','history']:
        oo=np.full(len(df),np.nan); ms=[]
        for k in range(5):
            tr=df.cv_fold!=k; va=df.cv_fold==k
            p=np.full(va.sum(),y[tr].mean()) if fam=='constant' else histprob(df.loc[va]); oo[va]=p; m=mets(y[va],p); ms.append(m); rows.append(dict(model_family=fam,feature_family='none' if fam=='constant' else 'H',config='{}',fold=k,**m))
        avg={z:float(np.nanmean([m[z] for m in ms])) for z in ms[0]}; rows.append(dict(model_family=fam,feature_family='none' if fam=='constant' else 'H',config='{}',fold='mean',**avg)); oofs[(fam,'none' if fam=='constant' else 'H','{}')]=oo
    # preprocess fold matrices once
    cache={}
    for ff,feats in F.items():
        for k in range(5):
            tr=df.cv_fold!=k; va=df.cv_fold==k
            cache[('std',ff,k)]=(*prep_fold(df,feats,tr,va,True)[:2],y[tr],y[va],np.where(va)[0])
            cache[('raw',ff,k)]=(*prep_fold(df,feats,tr,va,False)[:2],y[tr],y[va],np.where(va)[0])
    grids={
      'logistic':[{'C':c} for c in [0.1,1.0,10.0]],
      'hgb':[{'learning_rate':lr,'max_leaf_nodes':leaves,'max_iter':iters,'l2_regularization':l2} for lr in [0.03,0.10] for leaves in [7,15,31] for iters in [100,250] for l2 in [0.0,1.0]],
      'mlp':[{'hidden_layer_sizes':list(h),'alpha':al} for h in [(32,),(64,32)] for al in [1e-4,1e-3]],
    }
    tasks=[]
    for fam,cfgs in grids.items():
        kind='raw' if fam=='hgb' else 'std'
        for ff in F:
            for cfg in cfgs:
                for k in range(5):
                    Xtr,Xva,ytr,yva,idx=cache[(kind,ff,k)]; tasks.append((fam,cfg,ff,k,Xtr,Xva,ytr,yva,idx))
    print('TASKS',len(tasks),flush=True)
    # Fit independent fold/configuration tasks in parallel. joblib preserves
    # input order in the returned list, so downstream aggregation remains
    # deterministic. Each fit is itself constrained to one numerical thread
    # inside fit_task(), preventing nested BLAS/OpenMP oversubscription.
    if a.jobs == 1:
        res=[]
        for ti,t in enumerate(tasks, start=1):
            res.append(fit_task(*t[:-1]))
            if ti % 50 == 0 or ti == len(tasks): print('DONE',ti,'/',len(tasks),flush=True)
    else:
        res=Parallel(n_jobs=a.jobs, backend='loky', verbose=10)(
            delayed(fit_task)(*t[:-1]) for t in tasks
        )
        print('DONE',len(tasks),'/',len(tasks),flush=True)
    # aggregate oof/config
    tmp={}
    for (fam,ff,cfgj,k,p,m),t in zip(res,tasks):
        idx=t[-1]; rows.append(dict(model_family=fam,feature_family=ff,config=cfgj,fold=k,**m)); key=(fam,ff,cfgj); tmp.setdefault(key,np.full(len(df),np.nan)); tmp[key][idx]=p
    for key,oo in tmp.items():
        fam,ff,cfgj=key; fms=[]
        for k in range(5): fms.append(mets(y[df.cv_fold==k],oo[df.cv_fold==k]))
        avg={z:float(np.nanmean([m[z] for m in fms])) for z in fms[0]}; rows.append(dict(model_family=fam,feature_family=ff,config=cfgj,fold='mean',**avg)); oofs[key]=oo
    rr=pd.DataFrame(rows); rr.to_csv(out/'p6_development_cv_metrics.csv',index=False)
    means=rr[rr.fold.astype(str)=='mean'].copy(); rank={'constant':0,'history':1,'logistic':2,'hgb':3,'mlp':4}; means['complexity_rank']=means.model_family.map(rank); means=means.sort_values(['log_loss','brier','auprc','complexity_rank'],ascending=[True,True,False,True]); means.to_csv(out/'p6_development_model_ranking.csv',index=False)
    w=means.iloc[0]; key=(w.model_family,w.feature_family,w.config); oo=oofs[key]; fam=w.model_family; ff=w.feature_family; cfg=json.loads(w.config)
    # calibration
    lg=np.log(clip(oo)/(1-clip(oo))).reshape(-1,1); pl=LogisticRegression(C=1e6,solver='lbfgs',max_iter=2000); pl.fit(lg,y); cal=clip(pl.predict_proba(lg)[:,1]); mu=mets(y,oo); mc=mets(y,cal); use=(mc['log_loss'],mc['brier'])<(mu['log_loss'],mu['brier']); final=cal if use else oo; calchoice='platt' if use else 'none'
    pred=df[['case_id','domain','instance_seed','decision_iteration','candidate_id']].copy(); pred['target']=y; pred['raw_probability']=oo; pred['final_probability']=final; pred['cv_fold']=df.cv_fold; pred.to_csv(out/'p6_selected_oof_predictions.csv',index=False)
    feats=[] if ff=='none' else F[ff]; meta={'model_family':fam,'feature_family':ff,'config':cfg,'features':feats,'calibration':calchoice}
    with threadpool_limits(limits=1):
        if fam=='constant': obj={'meta':meta,'constant_probability':float(y.mean())}
        elif fam=='history': obj={'meta':meta}
        else: obj={'meta':meta,**build_final_model(fam,cfg,feats,df,y)}
    joblib.dump(obj,out/'p6_final_model.joblib'); joblib.dump({'choice':calchoice,'platt':pl if use else None,'coef':float(pl.coef_[0,0]),'intercept':float(pl.intercept_[0])},out/'p6_calibration.joblib')
    # Export the selected logistic coefficients used by the manuscript audit.
    if fam=='logistic':
        names=obj['model'].named_steps['prep'].get_feature_names_out()
        coef=obj['model'].named_steps['clf'].coef_[0]
        pd.DataFrame({'transformed_feature':names,'coefficient':coef,'abs_coefficient':np.abs(coef)}).sort_values('abs_coefficient',ascending=False).reset_index(drop=True).to_csv(out/'p6_selected_logistic_coefficients.csv',index=False)
    summ={'development_rows':len(df),'development_cases':df[['domain','instance_seed']].drop_duplicates().shape[0],'target_prevalence':float(y.mean()),'selected_model_family':fam,'selected_feature_family':ff,'selected_config':cfg,'selected_mean_cv_metrics':{z:float(w[z]) for z in ['log_loss','brier','auroc','auprc']},'oof_uncalibrated':mu,'oof_platt':mc,'calibration_choice':calchoice,'final_oof_metrics':mets(y,final),'platt_coef':float(pl.coef_[0,0]),'platt_intercept':float(pl.intercept_[0])}
    json.dump(summ,open(out/'P6_DEVELOPMENT_SUMMARY.json','w'),indent=2,sort_keys=True); open(out/'P6_DEVELOPMENT_SUMMARY.json','a').write('\n'); json.dump(meta,open(out/'P6_SELECTED_MODEL_SPEC.json','w'),indent=2,sort_keys=True); open(out/'P6_SELECTED_MODEL_SPEC.json','a').write('\n')
    # ablations best per family/feature
    ab=[]
    for mf in ['logistic','hgb','mlp']:
        for fx in F:
            s=means[(means.model_family==mf)&(means.feature_family==fx)].sort_values(['log_loss','brier','auprc'],ascending=[True,True,False]); ab.append(s.iloc[0])
    pd.DataFrame(ab).to_csv(out/'p6_feature_ablation_best_configs.csv',index=False)
    names=['p6_development_cv_metrics.csv','p6_development_model_ranking.csv','p6_selected_oof_predictions.csv','p6_final_model.joblib','p6_calibration.joblib','P6_DEVELOPMENT_SUMMARY.json','P6_SELECTED_MODEL_SPEC.json','p6_feature_ablation_best_configs.csv']; json.dump({n:sha(out/n) for n in names},open(out/'P6_DEVELOPMENT_HASHES.json','w'),indent=2,sort_keys=True); open(out/'P6_DEVELOPMENT_HASHES.json','a').write('\n')
    print(json.dumps(summ,indent=2,sort_keys=True),flush=True)
if __name__=='__main__': main()
