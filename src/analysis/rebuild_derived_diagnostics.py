#!/usr/bin/env python3
"""Rebuild derived summary CSVs and auxiliary diagnostic figures from frozen evidence.

This script does NOT rerun experiments and does NOT regenerate the exact final publication
PDFs in figures/publication. Those final PDFs are retained as frozen outputs. This utility
reconstructs supporting statistics and diagnostic plots in the ignored runtime output
directory from P6--P9/P7B evidence plus the
explicitly labeled post-hoc P7 diagnostics.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, average_precision_score

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'data/core'
D=ROOT/'figures'
FD=ROOT/'results/reproduced/derived_data'; FIG=ROOT/'results/reproduced/diagnostic_figures'; POST=ROOT/'results/posthoc'
FD.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)

def metrics(y,p):
    p=np.clip(np.asarray(p,float),1e-12,1-1e-12); y=np.asarray(y,int)
    return {'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),
            'auroc':float(roc_auc_score(y,p)) if len(np.unique(y))>1 else np.nan,
            'auprc':float(average_precision_score(y,p))}

def case_boot(df,ycol,pcol,casecol,n=2000,seed=20261005):
    rng=np.random.default_rng(seed); cases=np.array(sorted(df[casecol].unique())); cv=df[casecol].to_numpy()
    groups=[np.where(cv==c)[0] for c in cases]; y=df[ycol].to_numpy(); p=df[pcol].to_numpy()
    vals={k:[] for k in ['log_loss','brier','auroc','auprc']}
    for _ in range(n):
        idx=np.concatenate([groups[j] for j in rng.integers(0,len(cases),len(cases))]); m=metrics(y[idx],p[idx])
        for k,v in m.items():
            if np.isfinite(v): vals[k].append(v)
    return {k:(float(np.quantile(v,.025)),float(np.quantile(v,.975))) for k,v in vals.items()}

def mean_boot_ci(arr,seed,reps=10000):
    a=np.asarray(arr,float); rng=np.random.default_rng(seed); idx=rng.integers(0,len(a),size=(reps,len(a))); x=a[idx].mean(1)
    return float(a.mean()),float(np.quantile(x,.025)),float(np.quantile(x,.975))

def strat_boot_col(wide, col, n=10000, seed=88009):
    # Application-stratified BLOCK bootstrap, not 90 independent sequence samples.
    # Each app-repetition block carries its three measured regimes together.
    # Frozen paper CIs are retained separately as original 10,000-resample output;
    # this independent diagnostic resampling is allowed to differ slightly by seed.
    blocks=wide.groupby(['app','repetition'],sort=True)[col].mean().reset_index()
    groups=[g[col].to_numpy(float) for _,g in blocks.groupby('app',sort=True)]
    if len(groups)!=3 or any(len(g)!=10 for g in groups) or len(wide)!=90:
        raise ValueError('Expected 30 app-repetition blocks, each carrying three regimes')
    rng=np.random.default_rng(seed); z=np.zeros(n,float)
    for a in groups:
        z += a[rng.integers(0,len(a),size=(n,len(a)))].mean(axis=1)/len(groups)
    return float(np.quantile(z,.025)),float(np.quantile(z,.975))

# ---------- P6 development ablation + sealed holdout ----------
cv=pd.read_csv(E/'predictor_development/p6_development_cv_metrics.csv')
ab=pd.read_csv(E/'predictor_development/p6_feature_ablation_best_configs.csv')
rows=[]
for fam in ['H','S','D','H+S','H+D','H+S+D']:
    cfg=ab[(ab.model_family=='logistic')&(ab.feature_family==fam)].iloc[0]['config']
    d=cv[(cv.model_family=='logistic')&(cv.feature_family==fam)&(cv.config==cfg)&cv['fold'].astype(str).isin(['0','1','2','3','4'])]
    rows.append({'feature_family':fam,'config':cfg,'mean_log_loss':d.log_loss.mean(),'min_log_loss':d.log_loss.min(),'max_log_loss':d.log_loss.max(),'folds':d['fold'].nunique()})
pd.DataFrame(rows).to_csv(FD/'p6_ablation_fold_ranges.csv',index=False)

p6=pd.read_csv(E/'predictor_holdout/p6_blind_predictions.csv')
p6rows=[]
for name,pcol in [('Prevalence','constant_probability'),('History frequency','history_probability'),('Calibrated logistic H+D','final_probability')]:
    pt=metrics(p6.future_compatible_recurrence,p6[pcol]); ci=case_boot(p6,'future_compatible_recurrence',pcol,'case_id')
    row={'predictor':name}
    for k,v in pt.items(): row[k]=v; row[k+'_lo']=ci[k][0]; row[k+'_hi']=ci[k][1]
    p6rows.append(row)
pd.DataFrame(p6rows).to_csv(FD/'p6_blind_case_bootstrap_summary.csv',index=False)
shutil_needed=False
rel=pd.read_csv(E/'predictor_holdout/p6_blind_reliability_bins.csv'); rel.to_csv(FD/'p6_blind_reliability_bins.csv',index=False)

# ---------- P7B screen ----------
st=pd.read_csv(E/'residence_screen/p7b_structural_aggregate.csv'); st.to_csv(FD/'p7b_structural_aggregate.csv',index=False)

# ---------- P7 confirmatory ----------
p7m=pd.read_csv(E/'residence_primary/results/p7_confirmatory_matched.csv')
p7m.to_csv(FD/'p7_confirmatory_matched.csv',index=False)
ret=[]
for b in [.25,.50,.75]:
    d=p7m[p7m.budget_fraction==b]; le=d[d.policy=='learned'].set_index(['domain','instance_seed']).sort_index(); em=d[d.policy=='empirical_compatible'].set_index(['domain','instance_seed']).sort_index()
    diff=(le.reuse_fraction_of_keep_all-em.reuse_fraction_of_keep_all).to_numpy()
    if b==.25:
        inf=pd.read_csv(E/'residence_primary/results/p7_confirmatory_primary_inference.csv')
        r=inf[inf.comparison=='learned_minus_empirical_reuse'].iloc[0]; mean=float(r.mean_paired_effect); lo=float(r.bootstrap_95_low); hi=float(r.bootstrap_95_high)
    else:
        mean,lo,hi=mean_boot_ci(diff,77000+int(b*100))
    ret.append({'budget_fraction':b,'n_cases':len(diff),'empirical_mean_capture':em.reuse_fraction_of_keep_all.mean(),'learned_mean_capture':le.reuse_fraction_of_keep_all.mean(),'mean_paired_effect':mean,'ci_lo':lo,'ci_hi':hi})
pd.DataFrame(ret).to_csv(FD/'p7_retention_summary.csv',index=False)
pd.DataFrame([r for r in ret if r['budget_fraction']>.25])[['budget_fraction','n_cases','mean_paired_effect','ci_lo','ci_hi']].to_csv(FD/'p7_budget_sensitivity_bootstrap.csv',index=False)
# frozen post-hoc diagnostic runs and pairwise summary
post_runs=pd.read_csv(POST/'p7_posthoc_simple_baselines.csv'); post_sum=pd.read_csv(POST/'p7_posthoc_baseline_summary.csv')

# ---------- P8 external replay ----------
p8=pd.read_csv(E/'measured_replay/p8_external_runs.csv'); p8.to_csv(FD/'p8_external_runs.csv',index=False)
wide=p8.pivot_table(index=['sequence','app','regime','repetition'],columns='policy',values=['branch_pops_executed','mean_normalized_objective']).reset_index()
wide.columns=['__'.join([str(x) for x in c if str(x)!='']) if isinstance(c,tuple) else c for c in wide.columns]
# normalize easy names
for k in ['sequence','app','regime','repetition']:
    if k+'__' in wide: wide=wide.rename(columns={k+'__':k})
for p in ['empirical_compatible','learned','keep_all']:
    wide[f'saved_{p}']=wide['branch_pops_executed__restart']-wide[f'branch_pops_executed__{p}']
wide['learned_minus_empirical_saved']=wide['branch_pops_executed__empirical_compatible']-wide['branch_pops_executed__learned']
het=[]
for (app,reg),g in wide.groupby(['app','regime']):
    het.append({'app':app,'regime':reg,'n':len(g),'learned_mean_saved':g.saved_learned.mean(),'learned_median_saved':g.saved_learned.median(),
                'empirical_mean_saved':g.saved_empirical_compatible.mean(),'learned_minus_empirical_mean_saved':g.learned_minus_empirical_saved.mean(),
                'learned_positive':int((g.saved_learned>0).sum()),'learned_negative':int((g.saved_learned<0).sum()),'learned_tied':int((g.saved_learned==0).sum())})
pd.DataFrame(het).to_csv(FD/'p8_app_regime_heterogeneity.csv',index=False)
# pooled work-saving intervals + overhead economics
p8['overhead_ms']=p8[['serialization_ms','restoration_ms','selection_ms','model_scoring_ms']].sum(axis=1)
pool=[]
for pol,key in [('empirical_compatible','saved_empirical_compatible'),('learned','saved_learned'),('keep_all','saved_keep_all')]:
    vals=wide[key]; lo,hi=strat_boot_col(wide,key); d=p8[p8.policy==pol]
    pool.append({'policy':pol,'n':len(vals),'mean_saved_pops':vals.mean(),'median_saved_pops':vals.median(),'ci_lo':lo,'ci_hi':hi,
                 'mean_overhead_ms':d.overhead_ms.mean(),'median_overhead_ms':d.overhead_ms.median(),
                 'break_even_ms_per_pop_mean_over_mean':d.overhead_ms.mean()/vals.mean() if vals.mean()>0 else np.nan})
lo,hi=strat_boot_col(wide,'learned_minus_empirical_saved')
empoh=p8[p8.policy=='empirical_compatible'].set_index('sequence').overhead_ms; leoh=p8[p8.policy=='learned'].set_index('sequence').overhead_ms; inc=(leoh-empoh)
pool.append({'policy':'learned_minus_empirical','n':len(wide),'mean_saved_pops':wide.learned_minus_empirical_saved.mean(),'median_saved_pops':wide.learned_minus_empirical_saved.median(),'ci_lo':lo,'ci_hi':hi,
             'mean_overhead_ms':inc.mean(),'median_overhead_ms':inc.median(),'break_even_ms_per_pop_mean_over_mean':inc.mean()/wide.learned_minus_empirical_saved.mean()})
pd.DataFrame(pool).to_csv(FD/'p8_stratified_work_saving_and_economics.csv',index=False)
# objective effect
wide['learned_objective_improvement']=wide['mean_normalized_objective__restart']-wide['mean_normalized_objective__learned']
obj_mean=wide.learned_objective_improvement.mean()
obj_check_lo,obj_check_hi=strat_boot_col(wide,'learned_objective_improvement')
# Original paper's final block-bootstrap confidence limits were frozen after
# correcting the early 90-sequence analysis to 30 dependent application-rep blocks.
# The auxiliary diagnostic must use those same reported limits rather than
# replace them with a different RNG stream or the obsolete sequence bootstrap.
final_block=json.loads((ROOT/'results/mdkp/diagnostics/P8_BLOCK_BOOTSTRAP_FINAL.json').read_text())
assert abs(final_block['obj_learned']['mean']-obj_mean)<1e-12
assert abs(obj_check_lo-final_block['obj_learned']['ci95'][0])<0.0001
assert abs(obj_check_hi-final_block['obj_learned']['ci95'][1])<0.0001
obj_lo,obj_hi=map(float,final_block['obj_learned']['ci95'])

# ---------- P9 cross-domain ----------
p9m=pd.read_csv(E/'cross_family_transfer/p9_cross_domain_metrics.csv'); p9m.to_csv(FD/'p9_cross_domain_metrics.csv',index=False)
p9p=pd.read_csv(E/'cross_family_transfer/p9_cross_domain_predictions.csv'); p9ci=[]
for dom,d in p9p.groupby('held_out_domain',sort=True):
    pt=metrics(d.future_compatible_recurrence,d.prediction); ci=case_boot(d,'future_compatible_recurrence','prediction','case_id')
    row={'held_out_domain':dom,'cases':d.case_id.nunique()}
    for k,v in pt.items(): row[k]=v; row[k+'_lo']=ci[k][0]; row[k+'_hi']=ci[k][1]
    p9ci.append(row)
pd.DataFrame(p9ci).to_csv(FD/'p9_case_bootstrap_summary.csv',index=False)

# ---------- measurement-independence audit ----------
mi=pd.read_csv(ROOT/'data/deathstarbench/measurement/MEASUREMENT_INDEX.csv'); sm=pd.read_csv(ROOT/'data/deathstarbench/prepared/sequence_manifest.csv')
audit={'measurement_rows':len(mi),'unique_sequences':int(mi.sequence.nunique()),'unique_measurement_seeds':int(mi.seed.nunique()),'unique_pcap_sha256':int(mi.pcap_sha256.nunique()),'prepared_sequences':int(sm.sequence.nunique())}
(FD/'dsb_measurement_independence_audit.json').write_text(json.dumps(audit,indent=2)+'\n')

# ---------- machine-readable headline summary ----------
p6sel=pd.DataFrame(p6rows).set_index('predictor').loc['Calibrated logistic H+D']
r25=pd.DataFrame(ret).set_index('budget_fraction').loc[.25]
p7runs=pd.read_csv(E/'residence_primary/results/p7_confirmatory_runs.csv')
p7w=p7runs.pivot_table(index=['domain','instance_seed'],columns='policy',values='branch_pops_executed').reset_index(); confirm_saved=(p7w['restart']-p7w['learned']).mean()
p8learn=float(pd.DataFrame(pool).set_index('policy').loc['learned','mean_saved_pops'])
summary={'prediction':{'heldout_auroc':p6sel.auroc,'heldout_ap':p6sel.auprc},'retention':{'budget_25_effect':r25.mean_paired_effect,'ci':[r25.ci_lo,r25.ci_hi]},
         'work_saving':{'confirmatory_pops_per_case':float(confirm_saved),'external_pops_per_sequence':p8learn},
         'objective':{'external_mean_effect':float(obj_mean),'stratified_ci':[float(obj_lo),float(obj_hi)]},'measurement_audit':audit}
(FD/'paper_headline_summary.json').write_text(json.dumps(summary,indent=2)+'\n')

# ---------- publication figures ----------
plt.rcParams.update({'font.family':'Liberation Sans','font.size':8.5,'axes.labelsize':8.5,'xtick.labelsize':7.7,'ytick.labelsize':7.7,'legend.fontsize':7.6,'axes.linewidth':0.8,'lines.linewidth':1.35,'lines.markersize':5.0,'pdf.fonttype':42,'ps.fonttype':42,'savefig.bbox':'tight','savefig.pad_inches':0.025})
cycle=plt.rcParams['axes.prop_cycle'].by_key()['color']; EMP,LEARN,KEEP,CONTRAST=cycle[0],cycle[1],cycle[2],cycle[3]; NEUTRAL='0.55'; LIGHT='0.86'
def tidy(ax,grid='x'):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False); ax.tick_params(direction='out',length=3,width=.7)
    if grid: ax.grid(axis=grid,color=LIGHT,linewidth=.6)
    ax.set_axisbelow(True)
def panel(ax,label): ax.text(-.11,1.04,label,transform=ax.transAxes,fontweight='bold',fontsize=9.5,va='bottom')
# Fig 2
ab2=pd.read_csv(FD/'p6_ablation_fold_ranges.csv'); rel2=pd.read_csv(FD/'p6_blind_reliability_bins.csv'); fig,axes=plt.subplots(1,2,figsize=(7.15,3.05),gridspec_kw={'width_ratios':[1.05,.95]})
ax=axes[0]; order=['H','S','D','H+S','H+D','H+S+D']; d=ab2.set_index('feature_family').loc[order].reset_index(); y=np.arange(len(d))[::-1]; mean=d.mean_log_loss.to_numpy(); ax.errorbar(mean,y,xerr=np.vstack([mean-d.min_log_loss.to_numpy(),d.max_log_loss.to_numpy()-mean]),fmt='o',capsize=2.2,color=EMP,ecolor=EMP); sel=d.feature_family.eq('H+D').to_numpy(); ax.plot(mean[sel],y[sel],marker='s',linestyle='None',markersize=6.2,color=LEARN); ax.set_yticks(y,d.feature_family); ax.set_xlabel('Grouped-CV log loss (lower is better)'); ax.set_xlim(.32,.64); ax.xaxis.set_major_locator(MultipleLocator(.05)); tidy(ax); panel(ax,'(a)')
ax=axes[1]; x=rel2.mean_predicted_probability.to_numpy(); yy=rel2.observed_frequency.to_numpy(); n=rel2.n.to_numpy(); ax.plot([0,1],[0,1],linestyle='--',linewidth=1,color=NEUTRAL); ax.scatter(x,yy,s=18+.72*n,marker='o',color=LEARN,edgecolor='white',linewidth=.55,zorder=3); ax.set_xlabel('Mean predicted probability'); ax.set_ylabel('Observed frequency'); ax.set_xlim(-.02,1.02); ax.set_ylim(-.02,1.02); ax.xaxis.set_major_locator(MultipleLocator(.2)); ax.yaxis.set_major_locator(MultipleLocator(.2)); ax.text(.03,.96,'Point area scales with bin count',transform=ax.transAxes,ha='left',va='top',fontsize=7.2,color='.35'); tidy(ax,'both'); panel(ax,'(b)'); fig.subplots_adjust(wspace=.34,left=.10,right=.99,bottom=.18,top=.94); fig.savefig(FIG/'PAPER2_fig_prediction_ablation.pdf'); fig.savefig(FIG/'PAPER2_fig_prediction_ablation.png',dpi=240); plt.close(fig)
# Fig 3
rs=pd.DataFrame(ret).set_index('budget_fraction'); budgets=np.array([25,50,75]); emp=np.array([rs.loc[b/100,'empirical_mean_capture'] for b in budgets]); learn=np.array([rs.loc[b/100,'learned_mean_capture'] for b in budgets]); ps=post_sum.set_index('policy'); contrasts=pd.DataFrame({'Comparator':['Empirical-compatible','History only','Invested-work only'],'mean':[rs.loc[.25,'mean_paired_effect'],ps.loc['history_only','learned_minus_policy_mean'],ps.loc['work_only','learned_minus_policy_mean']],'lo':[rs.loc[.25,'ci_lo'],ps.loc['history_only','ci_lo'],ps.loc['work_only','ci_lo']],'hi':[rs.loc[.25,'ci_hi'],ps.loc['history_only','ci_hi'],ps.loc['work_only','ci_hi']]}); fig,axes=plt.subplots(1,2,figsize=(7.15,3),gridspec_kw={'width_ratios':[1.05,.95]}); ax=axes[0]; ax.plot(budgets,emp,marker='o',linestyle='--',label='Empirical-compatible',color=EMP); ax.plot(budgets,learn,marker='s',label='Learned',color=LEARN); ax.axhline(1,linestyle=':',linewidth=1.1,label='Keep-all reference',color=KEEP); ax.set_xlabel('Persistence budget (% of keep-all peak bytes)'); ax.set_ylabel('Reusable-work capture / keep-all'); ax.set_xticks(budgets); ax.set_ylim(.78,1.015); ax.yaxis.set_major_locator(MultipleLocator(.05)); ax.legend(frameon=False,loc='lower right'); tidy(ax,'y'); ax.grid(axis='x',color=LIGHT,linewidth=.6); panel(ax,'(a)'); ax=axes[1]; y=np.arange(len(contrasts))[::-1]; mean=contrasts['mean'].to_numpy(); ax.errorbar(mean,y,xerr=np.vstack([mean-contrasts.lo.to_numpy(),contrasts.hi.to_numpy()-mean]),fmt='o',capsize=2.4,color=LEARN,ecolor=LEARN); ax.plot(mean[0],y[0],marker='s',linestyle='None',markersize=6.3,color=LEARN); ax.axvline(0,linestyle=':',linewidth=1,color=NEUTRAL); ax.set_yticks(y,contrasts.Comparator); ax.set_xlabel('Learned - comparator at 25% budget\n(reusable-work capture)'); ax.set_xlim(-.015,.39); ax.xaxis.set_major_locator(MultipleLocator(.05)); tidy(ax); panel(ax,'(b)'); fig.subplots_adjust(wspace=.47,left=.10,right=.99,bottom=.22,top=.94); fig.savefig(FIG/'PAPER2_fig_confirmatory_retention.pdf'); fig.savefig(FIG/'PAPER2_fig_confirmatory_retention.png',dpi=240); plt.close(fig)
# Fig 4
het=pd.DataFrame(het); pooled=pd.DataFrame(pool); app_label={'hotelReservation':'Hotel Reservation','mediaMicroservices':'Media Service','socialNetwork':'Social Network'}; reg_order=['burst','step','ramp']; app_order=['hotelReservation','mediaMicroservices','socialNetwork']; rr=[]
for app in app_order:
 for reg in reg_order:
  g=het[(het.app==app)&(het.regime==reg)].iloc[0]; rr.append((app_label[app],reg,g.empirical_mean_saved,g.learned_mean_saved))
fig,axes=plt.subplots(1,2,figsize=(7.25,4.05),gridspec_kw={'width_ratios':[1.35,.85]}); ax=axes[0]; y=np.arange(len(rr))[::-1]; ev=np.array([r[2] for r in rr]); lv=np.array([r[3] for r in rr]);
for yi,a,b in zip(y,ev,lv): ax.plot([a,b],[yi,yi],linewidth=.9,color=NEUTRAL,alpha=.65)
ax.plot(ev,y,marker='o',linestyle='None',label='Empirical-compatible',color=EMP); ax.plot(lv,y,marker='s',linestyle='None',label='Learned',color=LEARN); ax.set_yticks(y,[f'{a} - {r}' for a,r,_,__ in rr]); ax.set_xlabel('Mean new branch pops avoided vs restart'); ax.set_xlim(-2,60); ax.xaxis.set_major_locator(MultipleLocator(10)); [ax.axhline(s,linewidth=.6,color=LIGHT) for s in [5.5,2.5]]; ax.legend(frameon=False,loc='lower right'); tidy(ax); panel(ax,'(a)'); ax=axes[1]; po=['empirical_compatible','learned','keep_all','learned_minus_empirical']; lab=['Empirical-compatible','Learned','Keep-all','Learned - empirical']; p=pooled.set_index('policy').loc[po].reset_index(); y=np.arange(len(p))[::-1]; mean=p.mean_saved_pops.to_numpy();
for m,yi,l,h,fmt,col in zip(mean,y,mean-p.ci_lo.to_numpy(),p.ci_hi.to_numpy()-mean,['o','s','^','D'],[EMP,LEARN,KEEP,CONTRAST]): ax.errorbar(m,yi,xerr=np.array([[l],[h]]),fmt=fmt,capsize=2.4,color=col,ecolor=col)
ax.axvline(0,linestyle=':',linewidth=1,color=NEUTRAL); ax.set_yticks(y,lab); ax.set_xlabel('Pooled mean avoided pops\n(95% stratified-bootstrap CI)'); ax.set_xlim(-2,36); ax.xaxis.set_major_locator(MultipleLocator(5)); tidy(ax); panel(ax,'(b)'); fig.subplots_adjust(wspace=.43,left=.205,right=.99,bottom=.16,top=.95); fig.savefig(FIG/'PAPER2_fig_external_work_saving.pdf'); fig.savefig(FIG/'PAPER2_fig_external_work_saving.png',dpi=240); plt.close(fig)
# Fig 5
fig,ax=plt.subplots(figsize=(7.15,2.05)); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis('off'); xs=[.13,.38,.63,.87]; w=.20; h=.60; y0=.23; headers=['Prediction','Retention','Search-work saving','Objective effect']; lines=[[f'Held-out',f'AUROC {p6sel.auroc:.3f}',f'AP {p6sel.auprc:.3f}'],['25% budget',f'+{100*r25.mean_paired_effect:.2f} pp','vs empirical'],['Confirmatory',f'+{confirm_saved:.2f} pops/case','Measured replay',f'+{p8learn:.2f} pops/sequence'],[f'{obj_mean:+.6f} vs restart','95% CI',f'[{obj_lo:.6f}, {obj_hi:.6f}]']]; status=['Signal confirmed','Gain confirmed','Regime dependent','Unresolved']; cols=[EMP,LEARN,LEARN,NEUTRAL]
for i,x in enumerate(xs):
    box=FancyBboxPatch((x-w/2,y0),w,h,boxstyle='round,pad=0.010,rounding_size=0.010',linewidth=1.1,edgecolor=cols[i],facecolor='white'); ax.add_patch(box); ax.text(x,y0+h-.09,headers[i],ha='center',va='center',fontweight='bold',fontsize=8.1); ax.plot([x-w/2+.026,x+w/2-.026],[y0+h-.145]*2,linewidth=.8,color=cols[i]); yy=y0+h-.225; step=.088 if len(lines[i])==4 else .102; fsz=6.85 if len(lines[i])==4 else 7.15
    for j,t in enumerate(lines[i]): ax.text(x,yy-step*j,t,ha='center',va='center',fontsize=fsz)
    ax.text(x,y0+.035,status[i],ha='center',va='center',fontsize=7.25,fontweight='bold',color=cols[i])
    if i<3: ax.add_patch(FancyArrowPatch((x+w/2+.008,y0+h/2),(xs[i+1]-w/2-.008,y0+h/2),arrowstyle='-|>',mutation_scale=9,linewidth=.9,color=NEUTRAL))
ax.text(.5,.055,r'Prediction $\rightarrow$ retained reusable state $\rightarrow$ work saving $\rightarrow$ downstream utility',ha='center',va='bottom',fontsize=7.8); fig.savefig(FIG/'PAPER2_fig_evidence_chain.pdf'); fig.savefig(FIG/'PAPER2_fig_evidence_chain.png',dpi=240); plt.close(fig)
# Supplement Fig S1
scales=[(24,6),(32,8),(40,10)]; destroys=[5,8,12]; peak=np.full((3,3),np.nan); frac=np.full((3,3),np.nan)
for i,(nn,nh) in enumerate(scales):
 for j,ds in enumerate(destroys):
  g=st[(st.n_nodes==nn)&(st.n_hosts==nh)&(st.destroy_size==ds)].iloc[0]; peak[i,j]=g.median_peak_active_checkpoints; frac[i,j]=100*g.median_fraction_iterations_k_ge_4
fig,axes=plt.subplots(1,2,figsize=(7.15,2.65),sharey=True)
for ax,mat,title,cbar in [(axes[0],peak,'Median peak live checkpoints','checkpoints'),(axes[1],frac,'Iterations with at least four live checkpoints','% of iterations')]:
 im=ax.imshow(mat,aspect='auto',origin='upper'); ax.set_xticks(range(3),destroys); ax.set_yticks(range(3),[f'{a} nodes / {b} hosts' for a,b in scales]); ax.set_xlabel('Destroy size')
 for i in range(3):
  for j in range(3): ax.text(j,i,f'{mat[i,j]:.0f}' if cbar=='checkpoints' else f'{mat[i,j]:.0f}%',ha='center',va='center',fontsize=8,fontweight='bold',color='white' if mat[i,j]>np.nanmedian(mat) else 'black')
 ax.add_patch(Rectangle((1.5,-.5),1,1,fill=False,linewidth=2,edgecolor='black')); ax.set_title(title,fontsize=8.6,pad=6); cb=fig.colorbar(im,ax=ax,fraction=.045,pad=.035); cb.ax.tick_params(labelsize=7); cb.set_label(cbar,fontsize=7.5); ax.tick_params(length=0)
axes[1].tick_params(labelleft=False); panel(axes[0],'(a)'); panel(axes[1],'(b)'); fig.subplots_adjust(wspace=.20,left=.14,right=.97,bottom=.20,top=.86); fig.savefig(FIG/'PAPER2_fig_structural_screen.pdf'); fig.savefig(FIG/'PAPER2_fig_structural_screen.png',dpi=240); plt.close(fig)

print(json.dumps(summary,indent=2))
print('Rebuilt derived summaries in',FD,'and auxiliary diagnostic figures in',FIG)
