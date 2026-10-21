import pickle
import numpy as np
from independent_mdkp.core import (
    make_instance, initial_solution, make_context_library, initialize_checkpoint,
    advance_checkpoint, checkpoint_solution, solve_with_highs, checkpoint_compatible,
    residual_capacity,
)
from independent_mdkp.controller import run_live_policy, build_prediction_dataset, P10_FEATURES


def _finish(inst,cp):
    while not cp.exact: advance_checkpoint(inst,cp,4096)
    return cp


def test_p10_exact_solver_matches_highs_small_and_representative_cases():
    cases=((32,10,71001),(120,42,71002),(168,54,71003))
    for n,d,seed in cases:
        inst=make_instance(n,seed); x=initial_solution(inst); ctx=make_context_library(n,d,seed,count=5)[0]
        cp=_finish(inst,initialize_checkpoint(inst,x,ctx)); opt,_=solve_with_highs(inst,x,ctx)
        assert cp.best_profit==opt
        sol=checkpoint_solution(inst,x,cp); assert np.all(inst.weights@sol<=inst.capacities)


def test_p10_interrupted_serialized_resume_matches_uninterrupted_and_work_identity():
    seed=72001; inst=make_instance(100,seed); x=initial_solution(inst); ctx=make_context_library(100,32,seed,count=6)[1]
    part=initialize_checkpoint(inst,x,ctx); advance_checkpoint(inst,part,37); invested=part.invested_nodes
    part=pickle.loads(pickle.dumps(part,protocol=pickle.HIGHEST_PROTOCOL)); assert checkpoint_compatible(inst,x,part)
    _finish(inst,part); resume_new=part.invested_nodes-invested
    full=_finish(inst,initialize_checkpoint(inst,x,ctx))
    assert (part.best_profit,part.best_bits)==(full.best_profit,full.best_bits)
    assert full.invested_nodes-resume_new==invested


def test_p10_compatibility_detects_outside_capacity_change():
    seed=73001; inst=make_instance(40,seed); x=initial_solution(inst); ctx=make_context_library(40,12,seed,count=6)[2]
    cp=initialize_checkpoint(inst,x,ctx); before=residual_capacity(inst,x,ctx); outside=[i for i in range(inst.n_items) if i not in set(ctx)]
    changed=False
    for i in outside:
        y=x.copy(); y[i]=1-y[i]
        if np.all(inst.weights@y<=inst.capacities) and not np.array_equal(residual_capacity(inst,y,ctx),before):
            assert not checkpoint_compatible(inst,y,cp); changed=True; break
    assert changed


def test_p10_predictor_feature_firewall_excludes_generator_class():
    assert 'current_context_class' not in P10_FEATURES
    assert len(P10_FEATURES)==14


def test_p10_live_controller_and_dataset_smoke():
    r,_=run_live_policy(seed=74001,n_items=48,destroy_size=14,slice_nodes=32,iterations=30,policy='keep_all',context_count=8)
    assert r['branch_nodes_executed']>0 and r['checkpoint_creations']>0
    df=build_prediction_dataset(seeds=[74002,74003],n_items=48,destroy_size=14,slice_nodes=32,iterations=40,context_count=8,horizon=12)
    assert set(P10_FEATURES).issubset(df.columns); assert 'future_compatible_recurrence' in df.columns; assert len(df)>0


def test_p10_counterbalanced_policy_order_is_position_balanced():
    import importlib.util
    from pathlib import Path
    script=Path(__file__).resolve().parents[1]/'src'/'stages'/'paper2_p10_independent_validation.py'
    spec=importlib.util.spec_from_file_location('p10_runtime_for_test',script)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    policies=['restart','empirical_compatible','learned','keep_all']
    counts={p:[0,0,0,0] for p in policies}
    for seed in range(8401,8446):
        for rep in range(3):
            for pos,pol in enumerate(mod.policy_order(seed,rep,policies)):
                counts[pol][pos]+=1
    assert all(max(v)-min(v)<=1 for v in counts.values())


def test_p10_local_allocator_wide_pool_matches_bruteforce():
    from independent_mdkp.allocation import ValueItem, select_exact_expected_value
    rng=np.random.default_rng(76001)
    items=[ValueItem(f'i{i}',int(rng.integers(1,10)),float(rng.uniform(0.01,2.0))) for i in range(13)]
    budget=28
    got=set(select_exact_expected_value(items,budget_bytes=budget))
    best=-1.0; bestsets=[]
    for mask in range(1<<len(items)):
        sz=sum(items[i].size_bytes for i in range(len(items)) if (mask>>i)&1)
        if sz>budget: continue
        val=sum(items[i].expected_value for i in range(len(items)) if (mask>>i)&1)
        if val>best+1e-10: best=val; bestsets=[{items[i].key for i in range(len(items)) if (mask>>i)&1}]
        elif abs(val-best)<=1e-10: bestsets.append({items[i].key for i in range(len(items)) if (mask>>i)&1})
    gotval=sum(x.expected_value for x in items if x.key in got)
    assert abs(gotval-best)<=1e-8


def test_p10_controller_uses_local_allocator_only():
    from pathlib import Path
    import independent_mdkp.controller as c
    text=Path(c.__file__).read_text()
    assert 'from .allocation import' in text
    assert 'certified_assignment' not in text


def test_p10_frozen_primary_wallclock_is_net_restart_contrast():
    from pathlib import Path
    import json
    root=Path(__file__).resolve().parents[1]
    candidates=[root/'protocol/P10_FROZEN_CONFIG.json',root/'experiments/mdkp/engineering_validation/P10_FROZEN_CONFIG.json']
    cp=next((x for x in candidates if x.exists()),None)
    assert cp is not None
    cfg=json.loads(cp.read_text())
    assert 'restart-minus-learned' in cfg['confirmatory']['primary_wall_clock_endpoint']
