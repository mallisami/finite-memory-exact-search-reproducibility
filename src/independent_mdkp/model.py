from __future__ import annotations
from pathlib import Path
import json
import numpy as np, pandas as pd, joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score,average_precision_score
from .controller import P10_FEATURES

HISTORY_FEATURES=('history_count_same_context','iterations_since_last_context','recent_same_context_count_20')


def _metrics(y,p):
    y=np.asarray(y,dtype=int); p=np.clip(np.asarray(p,dtype=float),1e-9,1-1e-9)
    return {
        'log_loss':float(log_loss(y,p,labels=[0,1])),
        'brier':float(brier_score_loss(y,p)),
        'auroc':float(roc_auc_score(y,p)) if len(np.unique(y))>1 else float('nan'),
        'ap':float(average_precision_score(y,p)) if len(np.unique(y))>1 else float('nan'),
    }


def _pipeline(features):
    return Pipeline([
        ('scale',StandardScaler()),
        ('lr',LogisticRegression(C=10.0,max_iter=4000,solver='lbfgs')),
    ])


def _fit_calibrated_oof(df, features):
    X=df[list(features)].copy(); y=df.future_compatible_recurrence.to_numpy(int); groups=df.case_id.astype(str).to_numpy()
    model=_pipeline(features); cv=GroupKFold(n_splits=5)
    raw=cross_val_predict(model,X,y,groups=groups,cv=cv,method='predict_proba',n_jobs=1)[:,1]
    raw=np.clip(raw,1e-6,1-1e-6); logits=np.log(raw/(1-raw)).reshape(-1,1)
    platt=LogisticRegression(C=1e6,max_iter=4000,solver='lbfgs').fit(logits,y)
    cal=platt.predict_proba(logits)[:,1]
    model.fit(X,y)
    return model,platt,raw,cal


def _predict_saved(model_obj, cal_obj, df, features):
    raw=np.asarray(model_obj['model'].predict_proba(df[list(features)])[:,1],dtype=float)
    raw=np.clip(raw,1e-6,1-1e-6); logits=np.log(raw/(1-raw)).reshape(-1,1)
    return np.asarray(cal_obj['platt'].predict_proba(logits)[:,1],dtype=float)


def _case_bootstrap_metrics(df, probs, reps=2000, seed=102501):
    y=df.future_compatible_recurrence.to_numpy(int); probs=np.asarray(probs,dtype=float)
    cases=np.asarray(sorted(df.case_id.astype(str).unique()))
    case_to_idx={c:np.flatnonzero(df.case_id.astype(str).to_numpy()==c) for c in cases}
    rng=np.random.default_rng(seed); vals={k:[] for k in ('log_loss','brier','auroc','ap')}
    for _ in range(int(reps)):
        draw=rng.choice(cases,size=len(cases),replace=True)
        idx=np.concatenate([case_to_idx[c] for c in draw])
        m=_metrics(y[idx],probs[idx])
        for k,v in m.items():
            if np.isfinite(v): vals[k].append(float(v))
    out={}
    for k,v in vals.items():
        a=np.asarray(v,dtype=float)
        out[k]=[float(np.quantile(a,.025)),float(np.quantile(a,.975))] if len(a) else [float('nan'),float('nan')]
    return out


def _calibration_point(y,p):
    y=np.asarray(y,dtype=int); p=np.clip(np.asarray(p,dtype=float),1e-6,1-1e-6)
    if len(np.unique(y))<2: return {'intercept':float('nan'),'slope':float('nan')}
    x=np.log(p/(1-p)).reshape(-1,1)
    lr=LogisticRegression(C=1e6,max_iter=4000,solver='lbfgs').fit(x,y)
    return {'intercept':float(lr.intercept_[0]),'slope':float(lr.coef_[0,0])}


def _case_bootstrap_calibration(df, probs, reps=2000, seed=102777):
    cases=np.asarray(sorted(df.case_id.astype(str).unique())); ids=df.case_id.astype(str).to_numpy(); y=df.future_compatible_recurrence.to_numpy(int); probs=np.asarray(probs,float)
    case_to_idx={c:np.flatnonzero(ids==c) for c in cases}; rng=np.random.default_rng(seed); ints=[]; slopes=[]
    for _ in range(int(reps)):
        draw=rng.choice(cases,size=len(cases),replace=True); idx=np.concatenate([case_to_idx[c] for c in draw])
        q=_calibration_point(y[idx],probs[idx])
        if np.isfinite(q['intercept']) and np.isfinite(q['slope']): ints.append(q['intercept']); slopes.append(q['slope'])
    def ci(a):
        a=np.asarray(a,float); return [float(np.quantile(a,.025)),float(np.quantile(a,.975))] if len(a) else [float('nan'),float('nan')]
    return {'intercept_95':ci(ints),'slope_95':ci(slopes)}


def fit_p10_model(df:pd.DataFrame,out_dir:str|Path)->dict:
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    y=df.future_compatible_recurrence.to_numpy(int); groups=df.case_id.astype(str).to_numpy()
    model,platt,raw,cal=_fit_calibrated_oof(df,P10_FEATURES)
    hmodel,hplatt,hraw,hcal=_fit_calibrated_oof(df,HISTORY_FEATURES)
    prevalence=float(y.mean())
    obj={'model':model,'features':list(P10_FEATURES),'model_family':'logistic_fixed_HD_analogue','C':10.0,'development_prevalence':prevalence}
    hobj={'model':hmodel,'features':list(HISTORY_FEATURES),'model_family':'logistic_history_only','C':10.0,'development_prevalence':prevalence}
    joblib.dump(obj,out/'p10_final_model.joblib'); joblib.dump({'platt':platt,'choice':'platt'},out/'p10_calibration.joblib')
    joblib.dump(hobj,out/'p10_history_model.joblib'); joblib.dump({'platt':hplatt,'choice':'platt'},out/'p10_history_calibration.joblib')
    pred=pd.DataFrame({'case_id':df.case_id,'seed':df.seed,'iteration':df.iteration,'y':y,'oof_raw_probability':raw,'oof_calibrated_probability':cal,'oof_history_probability':hcal})
    pred.to_csv(out/'p10_oof_predictions.csv',index=False)
    summary={
        'development_cases':int(pd.Series(groups).nunique()),'development_events':int(len(df)),'prevalence':prevalence,
        'fixed_features':list(P10_FEATURES),'history_baseline_features':list(HISTORY_FEATURES),
        'oof_raw':_metrics(y,raw),'oof_calibrated':_metrics(y,cal),'oof_history_only':_metrics(y,hcal),
        'privileged_generator_features_excluded':['current_context_class'],
    }
    (out/'P10_MODEL_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return summary


def evaluate_p10_model(df:pd.DataFrame,model_dir:str|Path,out_dir:str|Path)->dict:
    from .controller import P10Predictor
    model_dir=Path(model_dir); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    pmod=P10Predictor(model_dir/'p10_final_model.joblib',model_dir/'p10_calibration.joblib')
    p=np.array([pmod.predict({k:r[k] for k in P10_FEATURES}) for _,r in df.iterrows()])
    hobj=joblib.load(model_dir/'p10_history_model.joblib'); hcal=joblib.load(model_dir/'p10_history_calibration.joblib')
    ph=_predict_saved(hobj,hcal,df,HISTORY_FEATURES)
    prevalence=float(joblib.load(model_dir/'p10_final_model.joblib')['development_prevalence']); pp=np.full(len(df),prevalence,dtype=float)
    y=df.future_compatible_recurrence.to_numpy(int)
    pred=df[['case_id','seed','iteration','future_compatible_recurrence']].copy(); pred['prevalence_probability']=pp; pred['history_only_probability']=ph; pred['final_probability']=p; pred.to_csv(out/'p10_blind_predictions.csv',index=False)
    models={'prevalence':pp,'history_only':ph,'learned_HD':p}
    metrics={name:_metrics(y,v) for name,v in models.items()}
    cis={name:_case_bootstrap_metrics(df,v,reps=2000,seed=102501+j) for j,(name,v) in enumerate(models.items())}
    calpoint=_calibration_point(y,p); calci=_case_bootstrap_calibration(df,p,reps=2000,seed=102777)
    result={
        'cases':int(df.case_id.nunique()),'events':int(len(df)),'prevalence':float(y.mean()),
        'models':metrics,'case_bootstrap_95':cis,
        'learned_calibration':{**calpoint,**calci},
        'bootstrap_unit':'independent case','bootstrap_reps':2000,
    }
    (out/'P10_BLIND_METRICS.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result
