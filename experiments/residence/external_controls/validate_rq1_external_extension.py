from pathlib import Path
import pandas as pd, json
root=Path(__file__).resolve().parents[1]
e=root/'02_Authoritative_Experimental_Evidence/11_RQ1_External_Comparator'
df=pd.read_csv(e/'results/p7_external_comparator_runs.csv')
assert len(df)==945
assert df.task_id.nunique()==945
assert (df.policy=='fifo').sum()==135
assert (df.policy=='lru').sum()==135
assert (df.policy=='random').sum()==675
assert (df.peak_bytes <= df.budget_bytes).all()
assert (df.not_retained==0).all()
r=df[df.policy=='random']
g=r.groupby(['domain','instance_seed','budget_fraction']).agg(n=('task_id','size'), seeds=('eviction_seed','nunique'))
assert (g.n==5).all() and (g.seeds==5).all() and len(g)==135
print('RQ1 external extension validation: PASS')
