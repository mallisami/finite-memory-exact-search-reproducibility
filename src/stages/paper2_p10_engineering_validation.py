from __future__ import annotations
import argparse, pickle
import numpy as np
from independent_mdkp.core import make_instance,initial_solution,make_context_library,initialize_checkpoint,advance_checkpoint,checkpoint_solution,solve_with_highs,checkpoint_compatible,residual_capacity

SCALES=((36,12),(80,24),(120,42),(144,48),(168,54))

def finish(inst,cp,chunk=4096):
    while not cp.exact: advance_checkpoint(inst,cp,chunk)
    return cp

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--cases',type=int,default=12); a=ap.parse_args()
    for j in range(a.cases):
        n,d=SCALES[j%len(SCALES)]; seed=70001+j; inst=make_instance(n,seed); x=initial_solution(inst); ctx=make_context_library(n,d,seed,count=6)[j%6]
        # Interrupt, serialize/restore, and preserve the exact work-accounting identity.
        part=initialize_checkpoint(inst,x,ctx); advance_checkpoint(inst,part,min(73,max(7,d)))
        invested=int(part.invested_nodes); blob=pickle.dumps(part,protocol=pickle.HIGHEST_PROTOCOL); resumed=pickle.loads(blob)
        assert checkpoint_compatible(inst,x,resumed)
        finish(inst,resumed); resume_new=int(resumed.invested_nodes-invested)
        fresh=initialize_checkpoint(inst,x,ctx); finish(inst,fresh); restart_total=int(fresh.invested_nodes)
        if restart_total-resume_new!=invested:
            raise AssertionError(('restart-resume work identity failed',seed,restart_total,resume_new,invested))
        opt,_=solve_with_highs(inst,x,ctx)
        if resumed.best_profit!=opt or fresh.best_profit!=opt: raise AssertionError((seed,resumed.best_profit,fresh.best_profit,opt))
        sol=checkpoint_solution(inst,x,resumed); assert np.all(inst.weights@sol<=inst.capacities)
        # Change an outside item when possible; a residual change must reject the stale checkpoint.
        outside=[i for i in range(inst.n_items) if i not in set(ctx)]; saw=False
        for i in outside:
            y=x.copy(); y[i]=1-y[i]
            if np.all(inst.weights@y<=inst.capacities):
                changed=not np.array_equal(residual_capacity(inst,y,ctx),np.asarray(resumed.residual,dtype=np.int64))
                if changed:
                    assert not checkpoint_compatible(inst,y,resumed); saw=True; break
        if not saw: raise AssertionError(('could not construct compatibility-change audit',seed))
        print('PASS',seed,'n/d',n,d,'opt_context_profit',opt,'restart_nodes',restart_total,'invested',invested)
    print('ALL P10 ENGINEERING CHECKS PASSED')
if __name__=='__main__': main()
