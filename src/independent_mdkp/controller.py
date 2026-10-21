from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Literal
import json, math, pickle, time
import numpy as np
import pandas as pd
import joblib

from .allocation import ValueItem, select_exact_expected_value
from .core import (
    MDKPInstance, MDKPCheckpoint, make_instance, initial_solution, make_context_library,
    make_context_trace, initialize_checkpoint, advance_checkpoint, checkpoint_compatible,
    checkpoint_solution, objective_cost, residual_capacity,
)

PolicyName=Literal['restart','empirical_compatible','learned','keep_all']

P10_FEATURES=(
    'history_count_same_context','iterations_since_last_context','recent_same_context_count_20',
    'current_cost_ratio','current_best_cost_ratio','temperature_ratio',
    'recent_accept_rate_10','recent_accept_rate_20','recent_moved_item_overlap_10','recent_moved_item_overlap_20',
    'accepted_moves_since_context','cost_delta_since_context','objective_improvement_last_10','objective_improvement_last_20',
)

@dataclass
class HistoryRow:
    iteration:int
    context:tuple[int,...]
    context_class:int
    accepted:bool
    moved:tuple[int,...]
    cost_before:float
    cost_after:float

@dataclass
class CompatStats:
    compatible:int=0
    incompatible:int=0
    def prob(self, global_stats:'CompatStats')->float:
        n=self.compatible+self.incompatible
        if n: return float((self.compatible+0.5)/(n+1.0))
        gn=global_stats.compatible+global_stats.incompatible
        if gn: return float((global_stats.compatible+0.5)/(gn+1.0))
        return 0.5

@dataclass
class StoredCP:
    key:tuple[int,...]
    blob:bytes
    size_bytes:int
    expected_value:float
    cumulative_nodes:int
    created_iteration:int

class P10Predictor:
    """Frozen P10 logistic+Platt predictor with an algebraically identical low-overhead path.

    Model fitting still uses scikit-learn. Deployment extracts the fitted StandardScaler,
    logistic coefficients, and Platt coefficients once so timing experiments do not measure
    per-decision DataFrame construction or generic pipeline dispatch.
    """
    def __init__(self, model_path: str|Path, calibration_path: str|Path):
        o=joblib.load(model_path); c=joblib.load(calibration_path)
        self.model=o['model']; self.features=tuple(o['features']); self.calibration=c
        if tuple(self.features)!=tuple(P10_FEATURES): raise ValueError('P10 feature contract mismatch')
        scale=self.model.named_steps['scale']; lr=self.model.named_steps['lr']; pl=c['platt']
        self.mean_=np.asarray(scale.mean_,dtype=float); self.scale_=np.asarray(scale.scale_,dtype=float)
        self.coef_=np.asarray(lr.coef_[0],dtype=float); self.intercept_=float(lr.intercept_[0])
        self.platt_coef_=float(pl.coef_[0,0]); self.platt_intercept_=float(pl.intercept_[0])
    @staticmethod
    def _sigmoid(z:float)->float:
        if z>=0:
            e=math.exp(-z); return 1.0/(1.0+e)
        e=math.exp(z); return e/(1.0+e)
    def predict(self, feats:dict[str,float|int])->float:
        x=np.asarray([float(feats[k]) for k in self.features],dtype=float)
        z=(x-self.mean_)/np.where(self.scale_==0,1.0,self.scale_)
        raw=self._sigmoid(float(np.dot(self.coef_,z)+self.intercept_))
        raw=float(np.clip(raw,1e-6,1-1e-6)); logit=math.log(raw/(1.0-raw))
        p=self._sigmoid(self.platt_coef_*logit+self.platt_intercept_)
        return float(np.clip(p,1e-6,1-1e-6))


def _feature_row(history:Sequence[HistoryRow], iteration:int, context:tuple[int,...], context_class:int,
                 cost_before:float,best_cost:float,temperature:float,initial_cost:float)->dict[str,float|int]:
    same=[r for r in history if r.context==context]
    last=same[-1] if same else None
    def recent(w:int):
        rows=list(history[-w:])
        rate=(sum(r.accepted for r in rows)/len(rows)) if rows else 0.0
        same_n=sum(r.context==context for r in rows)
        overlap=sum(len(set(r.moved).intersection(context)) for r in rows if r.accepted)
        if rows: imp=float(rows[0].cost_before-rows[-1].cost_after)
        else: imp=0.0
        return rate,same_n,overlap,imp
    r10=recent(10); r20=recent(20)
    denom=max(abs(float(initial_cost)),1.0)
    accepted_since=sum(r.accepted for r in history[(last.iteration if last else 0):]) if history else 0
    cost_at_last=float(last.cost_after) if last else float(initial_cost)
    return {
        'history_count_same_context':int(len(same)),
        'iterations_since_last_context':int(iteration-last.iteration) if last else int(iteration),
        'recent_same_context_count_20':int(r20[1]),
        'current_cost_ratio':float(cost_before/denom),
        'current_best_cost_ratio':float(best_cost/denom),
        'temperature_ratio':float(temperature/denom),
        'recent_accept_rate_10':float(r10[0]),'recent_accept_rate_20':float(r20[0]),
        'recent_moved_item_overlap_10':int(r10[2]),'recent_moved_item_overlap_20':int(r20[2]),
        'accepted_moves_since_context':int(accepted_since),
        'cost_delta_since_context':float((cost_before-cost_at_last)/denom),
        'objective_improvement_last_10':float(r10[3]/denom),
        'objective_improvement_last_20':float(r20[3]/denom),
    }


def _history_recurrence_prob(history:Sequence[HistoryRow], iteration:int, context:tuple[int,...], horizon:int=40)->float:
    c=float(sum(r.context==context for r in history)); lam=(c+0.5)/(float(iteration)+1.0)
    return float(np.clip(1.0-math.exp(-horizon*lam),1e-6,1-1e-6))


def _select_memory(records:dict[tuple[int,...],StoredCP], incoming:StoredCP|None, budget_bytes:int|None, keep_all:bool):
    c=dict(records)
    if incoming is not None: c[incoming.key]=incoming
    if keep_all:
        return c, incoming is None or True, 0.0, 0
    assert budget_bytes is not None
    items=[ValueItem(k,v.size_bytes,v.expected_value) for k,v in c.items()]
    t=time.perf_counter(); keep=set(select_exact_expected_value(items,budget_bytes=int(budget_bytes))); ms=(time.perf_counter()-t)*1000
    evicted=len(set(records)-keep)
    out={k:v for k,v in c.items() if k in keep}
    admitted=incoming is None or incoming.key in keep
    return out,bool(admitted),float(ms),int(evicted)


def _invalidate_incompatible(instance:MDKPInstance,x:np.ndarray,records:dict[tuple[int,...],StoredCP])->int:
    bad=[]
    for k,r in records.items():
        try: cp=pickle.loads(r.blob)
        except Exception: bad.append(k); continue
        if not checkpoint_compatible(instance,x,cp): bad.append(k)
    for k in bad: records.pop(k,None)
    return len(bad)


def run_live_policy(*, seed:int,n_items:int,destroy_size:int,slice_nodes:int,iterations:int,policy:PolicyName,
                    context_count:int=18,budget_bytes:int|None=None,predictor:P10Predictor|None=None,
                    n_dims:int=3,future_horizon:int=40, collect_events:bool=False)->tuple[dict,list[dict]]:
    """Run one end-to-end MDKP LNS-like trajectory with real checkpoint restore/serialization."""
    instance=make_instance(n_items,seed,n_dims=n_dims); x=initial_solution(instance); init_cost=objective_cost(instance,x)
    best_cost=init_cost; contexts=make_context_library(n_items,destroy_size,seed,count=context_count)
    trace=make_context_trace(contexts,iterations,seed)
    history=[]; records={}; compat={}; global_compat=CompatStats(); events=[]
    branch_nodes=0; useful_resumes=0; reused_prior=0; creations=0; cap_evict=0; invalid_evict=0
    serialization_ms=restoration_ms=selection_ms=scoring_ms=repair_ms=0.0
    peak_bytes=0; byte_time=0; peak_live=0; live_ge4=0; checkpoint_sizes=[]; accepted_moves=0
    t_run=time.perf_counter()
    for t,(ctx,ctx_class,u_accept) in enumerate(trace,1):
        before=objective_cost(instance,x); temp=max(1e-9,0.02*abs(init_cost)*(0.995**(t-1)))
        feats=_feature_row(history,t,ctx,ctx_class,before,best_cost,temp,init_cost)
        resid_before=tuple(int(v) for v in residual_capacity(instance,x,ctx))
        record=records.get(ctx); cp=None; resumed=False; reused=0
        if policy!='restart' and record is not None:
            tt=time.perf_counter(); cand=pickle.loads(record.blob); restoration_ms+=(time.perf_counter()-tt)*1000
            if checkpoint_compatible(instance,x,cand):
                cp=cand; resumed=True; reused=int(record.cumulative_nodes); useful_resumes+=1; reused_prior+=reused
                s=compat.setdefault(ctx,CompatStats()); s.compatible+=1; global_compat.compatible+=1
            else:
                records.pop(ctx,None); invalid_evict+=1
                s=compat.setdefault(ctx,CompatStats()); s.incompatible+=1; global_compat.incompatible+=1
        if cp is None: cp=initialize_checkpoint(instance,x,ctx); creations+=1
        tt=time.perf_counter(); _,_,expanded,exact=advance_checkpoint(instance,cp,slice_nodes); repair_ms+=(time.perf_counter()-tt)*1000
        branch_nodes+=int(expanded)
        proposal=checkpoint_solution(instance,x,cp); after_prop=objective_cost(instance,proposal); delta=after_prop-before
        accept=(delta<=0) or (u_accept < math.exp(-max(delta,0.0)/temp))
        if accept:
            moved=tuple(np.flatnonzero(proposal!=x).astype(int).tolist()); x=proposal; accepted_moves+=1
            if objective_cost(instance,x)<best_cost: best_cost=objective_cost(instance,x)
        else: moved=()
        # Current checkpoint is meaningful after this repair; exact search needs no persistence.
        if policy!='restart' and not exact:
            if policy=='keep_all': p=1.0
            elif policy=='empirical_compatible':
                p_rec=_history_recurrence_prob(history,t,ctx,future_horizon); s=compat.setdefault(ctx,CompatStats()); p=float(np.clip(p_rec*s.prob(global_compat),1e-6,1-1e-6))
            elif policy=='learned':
                if predictor is None: raise ValueError('learned policy needs P10 predictor')
                tt=time.perf_counter(); p=predictor.predict(feats); scoring_ms+=(time.perf_counter()-tt)*1000
            else: raise AssertionError(policy)
            tt=time.perf_counter(); blob=pickle.dumps(cp,protocol=pickle.HIGHEST_PROTOCOL); serialization_ms+=(time.perf_counter()-tt)*1000
            size=len(blob); checkpoint_sizes.append(size); incoming=StoredCP(ctx,blob,size,float(p*cp.invested_nodes),int(cp.invested_nodes),t)
            records,admitted,sel_ms,ev=_select_memory(records,incoming,budget_bytes,policy=='keep_all')
            selection_ms+=sel_ms; cap_evict+=ev
        else:
            records.pop(ctx,None)
        if accept and moved:
            invalid_evict += _invalidate_incompatible(instance,x,records)
        bytes_now=sum(r.size_bytes for r in records.values()); peak_bytes=max(peak_bytes,bytes_now); byte_time+=bytes_now
        peak_live=max(peak_live,len(records)); live_ge4+=int(len(records)>=4)
        after=objective_cost(instance,x)
        history.append(HistoryRow(t,ctx,ctx_class,bool(accept),moved,float(before),float(after)))
        if collect_events:
            ev={'case_id':f'mdkp_{seed}','seed':int(seed),'iteration':int(t),'context_key':'-'.join(map(str,ctx)),
                'residual_key':','.join(map(str,resid_before)),'unfinished':int(not exact),'invested_nodes':int(cp.invested_nodes),
                **{k:feats[k] for k in P10_FEATURES}}
            events.append(ev)
    elapsed_ms=(time.perf_counter()-t_run)*1000
    summary={
        'seed':int(seed),'n_items':int(n_items),'n_dims':int(n_dims),'destroy_size':int(destroy_size),'slice_nodes':int(slice_nodes),
        'iterations':int(iterations),'context_count':int(context_count),'policy':str(policy),'budget_bytes':None if budget_bytes is None else int(budget_bytes),
        'initial_cost':float(init_cost),'final_cost':float(objective_cost(instance,x)),'best_cost':float(best_cost),
        'branch_nodes_executed':int(branch_nodes),'useful_resumes':int(useful_resumes),'reused_prior_nodes':int(reused_prior),
        'checkpoint_creations':int(creations),'capacity_evictions':int(cap_evict),'invalidation_evictions':int(invalid_evict),
        'peak_checkpoint_bytes':int(peak_bytes),'byte_time':int(byte_time),'peak_live_checkpoints':int(peak_live),
        'fraction_iterations_live_ge4':float(live_ge4/max(iterations,1)),'mean_checkpoint_size_bytes':float(np.mean(checkpoint_sizes)) if checkpoint_sizes else 0.0,
        'max_checkpoint_size_bytes':int(max(checkpoint_sizes) if checkpoint_sizes else 0),
        'serialization_ms':float(serialization_ms),'restoration_ms':float(restoration_ms),'selection_ms':float(selection_ms),'model_scoring_ms':float(scoring_ms),
        'repair_search_ms':float(repair_ms),'end_to_end_ms':float(elapsed_ms),'accepted_moves':int(accepted_moves),
    }
    return summary,events


def build_prediction_dataset(*, seeds:Sequence[int],n_items:int,destroy_size:int,slice_nodes:int,iterations:int,
                             context_count:int=18,n_dims:int=3,horizon:int=40)->pd.DataFrame:
    """Build outcome labels from restart-only live trajectories; no retention policy outcomes enter development."""
    rows=[]
    for seed in seeds:
        _,events=run_live_policy(seed=int(seed),n_items=n_items,destroy_size=destroy_size,slice_nodes=slice_nodes,
                                 iterations=iterations,policy='restart',context_count=context_count,n_dims=n_dims,collect_events=True)
        # Label an unfinished event positive iff the same context recurs compatibly within H in the reference trajectory.
        for i,e in enumerate(events):
            if not int(e.get('unfinished',0)):
                continue
            y=0
            for f in events[i+1:]:
                if int(f['iteration'])-int(e['iteration'])>int(horizon): break
                if f['context_key']==e['context_key'] and f['residual_key']==e['residual_key']:
                    y=1; break
            z=dict(e); z['future_compatible_recurrence']=int(y); rows.append(z)
    return pd.DataFrame(rows)
