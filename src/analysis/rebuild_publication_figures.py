#!/usr/bin/env python3
"""Rebuild Fig2-Fig5 and FigS1 from frozen PCR2 numerical sources, not manuscript files."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"figures/data"
def read(path):
    if not path.is_file(): raise FileNotFoundError(path)
    return pd.read_csv(path)
def finish(fig,out,name):
    path=out/name
    fig.savefig(path,format="pdf",bbox_inches="tight")
    plt.close(fig)
    if path.stat().st_size<1000: raise RuntimeError(f"Empty output: {path}")
    print("REBUILT",path)
def build(out):
    out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"Liberation Sans","font.size":8,
                         "pdf.fonttype":42,"ps.fonttype":42})
    # Figure 2: grouped-feature log loss and held-out P6 reliability.
    ab=read(DATA/"p6_ablation_fold_ranges.csv")
    rel=read(ROOT/"data/core/predictor_holdout/p6_blind_reliability_bins.csv")
    order=["H","S","D","H+S","H+D","H+S+D"]
    ab=ab.set_index("feature_family").loc[order].reset_index()
    if len(ab)!=6 or len(rel)!=10 or rel.n.sum()!=225:raise ValueError("P6 input mismatch")
    fig,axes=plt.subplots(1,2,figsize=(7.15,3.05))
    yy=np.arange(6)[::-1];v=ab.mean_log_loss.to_numpy()
    axes[0].errorbar(v,yy,xerr=np.vstack([v-ab.min_log_loss.to_numpy(),
        ab.max_log_loss.to_numpy()-v]),fmt="o",capsize=2)
    axes[0].plot(v[4],yy[4],"s");axes[0].set_yticks(yy,ab.feature_family)
    axes[0].set_xlabel("Grouped-CV log loss (lower is better)");axes[0].set_xlim(.32,.64)
    axes[0].set_title("(a)",loc="left",fontweight="bold");axes[0].grid(axis="x",alpha=.25)
    axes[1].plot([0,1],[0,1],"--",color="gray")
    axes[1].scatter(rel.mean_predicted_probability,rel.observed_frequency,s=18+.72*rel.n)
    for x,y,n in zip(rel.mean_predicted_probability,rel.observed_frequency,rel.n):
        axes[1].annotate(f"n={int(n)}",(x,y),xytext=(5,5),textcoords="offset points",fontsize=6)
    axes[1].set_xlim(-.02,1.04);axes[1].set_ylim(-.02,1.02)
    axes[1].set_xlabel("Mean predicted probability");axes[1].set_ylabel("Observed frequency")
    axes[1].set_title("(b)",loc="left",fontweight="bold");axes[1].grid(alpha=.25)
    fig.tight_layout();finish(fig,out,"Fig2.pdf")

    # Figure 3: primary 25/50/75% budget captures and fixed posthoc comparators.
    ret=read(DATA/"p7_retention_summary.csv").set_index("budget_fraction")
    post=read(ROOT/"results/posthoc/p7_posthoc_baseline_summary.csv").set_index("policy")
    if set(ret.index)!={.25,.5,.75}:raise ValueError("P7 budgets not sealed")
    b=np.array([25,50,75]);fig,axes=plt.subplots(1,2,figsize=(7.15,3))
    axes[0].plot(b,ret.loc[[.25,.5,.75],"empirical_mean_capture"],"o--",label="Empirical-compatible")
    axes[0].plot(b,ret.loc[[.25,.5,.75],"learned_mean_capture"],"s-",label="Learned")
    axes[0].axhline(1,ls=":",color="gray",label="Keep-all")
    axes[0].set_xticks(b);axes[0].set_ylim(.78,1.015)
    axes[0].set_ylabel("Keep-all-normalized reusable work");axes[0].set_xlabel("Budget (% peak bytes)")
    axes[0].legend(frameon=False);axes[0].grid(alpha=.25)
    v=np.array([ret.loc[.25,"mean_paired_effect"],post.loc["history_only","learned_minus_policy_mean"],
                post.loc["work_only","learned_minus_policy_mean"]])
    lo=np.array([ret.loc[.25,"ci_lo"],post.loc["history_only","ci_lo"],post.loc["work_only","ci_lo"]])
    hi=np.array([ret.loc[.25,"ci_hi"],post.loc["history_only","ci_hi"],post.loc["work_only","ci_hi"]])
    axes[1].errorbar(v,[2,1,0],xerr=[v-lo,hi-v],fmt="o",capsize=2)
    axes[1].axvline(0,ls=":",color="gray")
    axes[1].set_yticks([2,1,0],["Empirical-compatible","History only","Invested-work only"])
    axes[1].set_xlim(-.015,.39);axes[1].set_xlabel("Learned - comparator at 25% budget")
    axes[1].grid(axis="x",alpha=.25);fig.tight_layout()
    finish(fig,out,"Fig3.pdf")

    # Figure 4: corrected AWS P8 (90 sequences, 30 triplet blocks).
    p8=read(DATA/"p8_aws_triplet_block_work_saving_20261107.csv").set_index("policy")
    cells=read(DATA/"p8_aws_app_regime_heterogeneity_20261107.csv")
    original=read(ROOT/"results/measured_replay/aws_20261107/p8_external_runs.csv")
    if len(cells)!=9 or len(original)!=360 or original.sequence.nunique()!=90:
        raise ValueError("P8 AWS source population mismatch")
    w=original.pivot(index="sequence",columns="policy",values="branch_pops_executed")
    if not np.isclose(float((w.empirical_compatible-w.learned).mean()),
                      float(p8.loc["learned_minus_empirical","mean_saved_pops"]),atol=1e-9):
        raise ValueError("P8 summary disagrees with retained raw AWS output")
    fig=plt.figure(figsize=(10.4,6.1))
    a=fig.add_axes([.10,.60,.31,.30]);c=fig.add_axes([.10,.13,.31,.30])
    d=fig.add_axes([.62,.13,.33,.77])
    for i,(key,label,marker) in enumerate([("empirical_compatible","Empirical-compatible","o"),
                                            ("learned","Learned","s"),("keep_all","Keep-all","^")]):
        row=p8.loc[key];m=float(row.mean_saved_pops)
        a.errorbar(m,i,xerr=[[m-float(row.triplet_block_ci_lo)],
                   [float(row.triplet_block_ci_hi)-m]],fmt=marker,capsize=3)
    a.set_yticks(range(3),["Empirical-compatible","Learned","Keep-all"]);a.invert_yaxis()
    a.set_xlabel("Mean avoided new branch pops vs restart");a.set_title("(a)",loc="left")
    row=p8.loc["learned_minus_empirical"];m=float(row.mean_saved_pops)
    c.errorbar(m,0,xerr=[[m-float(row.triplet_block_ci_lo)],
                 [float(row.triplet_block_ci_hi)-m]],fmt="D",capsize=3)
    c.axvline(0,ls=":",color="gray");c.set_yticks([0],["Learned - empirical"])
    c.set_xlabel("Incremental avoided new branch pops");c.set_title("(b)",loc="left")
    labels=[]
    for i,app in enumerate(["Hotel Reservation","Media Service","Social Network"]):
        for j,regime in enumerate(["burst","step","ramp"]):
            row=cells[(cells.application_label==app)&(cells.regime==regime)]
            if len(row)!=1: raise ValueError(f"P8 cell mismatch {app}/{regime}")
            r=row.iloc[0];y=3*i+j
            d.plot([r.empirical_mean_saved,r.learned_mean_saved],[y,y],"-",color="gray",alpha=.5)
            d.plot(r.empirical_mean_saved,y,"o",color="#1f77b4")
            d.plot(r.learned_mean_saved,y,"s",color="#ff7f0e")
            labels.append(f"{app} - {regime}")
    d.set_yticks(range(9),labels);d.invert_yaxis()
    d.set_xlabel("Mean new branch pops avoided vs restart");d.set_title("(c)",loc="left")
    for ax in (a,c,d):ax.grid(axis="x",alpha=.2)
    finish(fig,out,"Fig4.pdf")

    # Figure 5: source-verified eight-row L1-L4 graph timing figure data.
    runtime=read(DATA/"rq2_graph_runtime_figure_summary_20261107.csv")
    if len(runtime)!=8 or not runtime.n_cases.eq(60).all() or set(runtime.repair_cap)!={8,16,32,64}:
        raise ValueError("Graph-runtime eight-cell source mismatch")
    fig,ax=plt.subplots(figsize=(7.15,2.05))
    for policy,marker,label in [("empirical_pW","o","Empirical-pW"),
                                 ("learned_pW","s","Learned-pW")]:
        row=runtime[runtime.policy==policy].sort_values("repair_cap")
        if len(row)!=4: raise ValueError(f"Incomplete graph-runtime policy: {policy}")
        ax.plot(row.repair_cap,row.geometric_restart_to_policy_runtime_ratio,
                marker=marker,label=label)
    ax.axhline(1,ls=":",color="gray",label="Restart parity")
    ax.set_xticks([8,16,32,64]);ax.set_xlim(6,66);ax.set_ylim(.88,1.09)
    ax.set_xlabel("Repair cap (branch pops per repair)")
    ax.set_ylabel("Geometric runtime ratio: restart / policy")
    ax.legend(frameon=False,ncol=3,loc="lower right");ax.grid(alpha=.25)
    fig.tight_layout();finish(fig,out,"Fig5.pdf")

    # Figure S1: nine original outcome-blind structural screen cells.
    screen=read(ROOT/"data/core/residence_screen/p7b_structural_aggregate.csv")
    peaks=np.full((3,3),np.nan);fractions=np.full((3,3),np.nan)
    for i,(nodes,hosts) in enumerate([(24,6),(32,8),(40,10)]):
        for j,destroy in enumerate([5,8,12]):
            row=screen[(screen.n_nodes==nodes)&(screen.n_hosts==hosts)&(screen.destroy_size==destroy)]
            if len(row)!=1:raise ValueError(f"P7B cell mismatch {nodes}/{hosts}/{destroy}")
            peaks[i,j]=row.iloc[0].median_peak_active_checkpoints
            fractions[i,j]=100*row.iloc[0].median_fraction_iterations_k_ge_4
    fig,axes=plt.subplots(1,2,figsize=(7.15,2.65),sharey=True)
    for ax,values,title in [(axes[0],peaks,"Median peak live checkpoints"),
                             (axes[1],fractions,"Iterations with >=4 live checkpoints")]:
        im=ax.imshow(values,aspect="auto")
        ax.set_xticks(range(3),[5,8,12]);ax.set_xlabel("Destroy size")
        ax.set_yticks(range(3),["24 / 6","32 / 8","40 / 10"])
        for i in range(3):
            for j in range(3):
                ax.text(j,i,f"{values[i,j]:.0f}",ha="center",va="center",
                        color="white" if values[i,j]>np.median(values) else "black")
        ax.set_title(title);fig.colorbar(im,ax=ax,fraction=.045,pad=.035)
    fig.tight_layout();finish(fig,out,"FigS1.pdf")
    print("PASS: five data figures reconstructed; Fig1 is frozen schematic artwork.")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,
                        default=ROOT/"results/reproduced/publication_figures")
    args=parser.parse_args()
    out=args.out.resolve()
    frozen=(ROOT/"figures/publication").resolve()
    if frozen==out or frozen in out.parents:
        parser.error("Refusing to overwrite frozen publication figure outputs")
    build(out)
