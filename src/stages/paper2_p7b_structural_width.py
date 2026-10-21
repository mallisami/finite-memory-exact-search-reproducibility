from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

from certified_assignment.paper2_structural_width import generate_structural_trace, characterize_keep_all

DOMAINS=("generic","workflow","microservice")
SCALES=((24,6),(32,8),(40,10))
DESTROY=(5,8,12)
SEEDS=(2626,2727,2828)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out-dir',required=True)
    ap.add_argument('--iterations',type=int,default=200)
    ap.add_argument('--slice-pops',type=int,default=8)
    a=ap.parse_args()
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
    rows=[]
    total=len(DOMAINS)*len(SCALES)*len(DESTROY)*len(SEEDS); done=0
    for n,m in SCALES:
      for dsize in DESTROY:
       for domain in DOMAINS:
        for seed in SEEDS:
         done += 1
         print(f'[{done}/{total}] {domain} n={n} m={m} destroy={dsize} seed={seed}',flush=True)
         tr=generate_structural_trace(domain,n,m,seed,iterations=a.iterations,destroy_size=dsize)
         r=characterize_keep_all(domain,n,m,seed,tr,slice_pops=a.slice_pops)
         rows.append(r.to_dict())
    df=pd.DataFrame(rows)
    df.to_csv(out/'p7b_structural_cases.csv',index=False)

    ag=[]
    for (n,m,dsize),g in df.groupby(['n_nodes','n_hosts','destroy_size'],sort=True):
        rec={
          'n_nodes':int(n),'n_hosts':int(m),'destroy_size':int(dsize),'cases':int(len(g)),
          'median_peak_active_checkpoints':float(g.peak_active_checkpoints.median()),
          'max_peak_active_checkpoints':int(g.peak_active_checkpoints.max()),
          'cases_peak_k_ge_4':int((g.peak_active_checkpoints>=4).sum()),
          'median_mean_active_checkpoints':float(g.mean_active_checkpoints_end_iteration.median()),
          'median_fraction_iterations_k_ge_2':float(g.fraction_iterations_k_ge_2.median()),
          'median_fraction_iterations_k_ge_3':float(g.fraction_iterations_k_ge_3.median()),
          'median_fraction_iterations_k_ge_4':float(g.fraction_iterations_k_ge_4.median()),
          'median_trace_recurrence_events':float(g.trace_recurrence_events.median()),
          'median_useful_resumes':float(g.useful_resumes.median()),
          'median_reused_prior_branch_pops':float(g.reused_prior_branch_pops.median()),
          'median_unfinished_return_fraction':float(g.unfinished_return_fraction.median()),
          'median_invalidation_evictions':float(g.invalidation_evictions.median()),
          'median_peak_bytes':float(g.peak_bytes.median()),
          'median_max_checkpoint_size_bytes':float(g.max_checkpoint_size_bytes.median()),
          'median_max_checkpoint_fraction_of_peak':float(g.max_checkpoint_fraction_of_peak.median()),
        }
        rec['eligible'] = bool(
            rec['median_peak_active_checkpoints'] >= 4 and
            rec['cases_peak_k_ge_4'] >= 6 and
            rec['median_fraction_iterations_k_ge_4'] >= 0.05 and
            rec['median_useful_resumes'] > 0 and
            rec['median_unfinished_return_fraction'] >= 0.20 and
            rec['median_max_checkpoint_fraction_of_peak'] <= 0.40
        )
        ag.append(rec)
    agg=pd.DataFrame(ag)
    agg.to_csv(out/'p7b_structural_aggregate.csv',index=False)
    eligible=agg[agg.eligible].copy()
    if len(eligible):
        selected=eligible.sort_values(
            ['median_fraction_iterations_k_ge_4','median_peak_active_checkpoints','median_useful_resumes','n_nodes','n_hosts'],
            ascending=[False,False,False,True,True],kind='mergesort').iloc[0].to_dict()
        status='eligible_regime_selected'
    else:
        selected=None; status='no_eligible_regime'
    summary={
      'design_status':'P7B_structural_portfolio_width_characterization',
      'domains':list(DOMAINS),'scales':[list(x) for x in SCALES],'destroy_sizes':list(DESTROY),'seeds':list(SEEDS),
      'independent_cases':int(len(df)),'iterations_per_case':int(a.iterations),'slice_branch_pops':int(a.slice_pops),
      'selection_uses_objective_outcomes':False,'eligibility_count':int(agg.eligible.sum()),
      'selection_status':status,'selected_regime':selected,
      'aggregate':agg.to_dict(orient='records'),
    }
    (out/'P7B_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'selection_status':status,'selected_regime':selected},indent=2,sort_keys=True),flush=True)

if __name__=='__main__': main()
