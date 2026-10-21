#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data/core'
fail=[]
def chk(cond,msg):
    print(('PASS' if cond else 'FAIL'),msg)
    if not cond: fail.append(msg)
def close(a,b,tol=1e-9): return abs(float(a)-float(b))<=tol

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-root',required=True); ap.add_argument('--allow-p10-pending',action='store_true'); a=ap.parse_args(); R=Path(a.run_root)
    # P5.5/P5.6 exact deterministic regeneration.
    for stage,files in {
      'graph_development':['P55_FEATURE_FIREWALL.json','P55_SUMMARY.json','p55_case_summary.csv','p55_group_splits.csv','p55_natural_candidate_dataset.csv'],
      'graph_holdout':['P56_BLIND_HOLDOUT_SEAL.json','P56_FEATURE_FIREWALL.json','p56_final_blind_cases.csv','p56_final_blind_features.csv','p56_final_blind_labels.SEALED.csv'],
      'predictor_holdout':['P6_BLIND_LABEL_RELEASE_MARKER.json','P6_BLIND_TEST_RESULTS.json','p6_blind_predictions.csv'],
    }.items():
        for fn in files:
            rp=R/stage/fn; fp=E/stage/fn
            chk(rp.is_file() and fp.is_file() and rp.read_bytes()==fp.read_bytes(),f'{stage}/{fn} exactly reproduces frozen evidence')
    # P6 development deterministic artifacts.
    for fn in ['P6_DEVELOPMENT_HASHES.json','P6_DEVELOPMENT_SUMMARY.json','P6_SELECTED_MODEL_SPEC.json','p6_calibration.joblib','p6_development_cv_metrics.csv','p6_development_model_ranking.csv','p6_feature_ablation_best_configs.csv','p6_final_model.joblib','p6_selected_oof_predictions.csv','p6_selected_logistic_coefficients.csv']:
        rp=R/'predictor_development'/fn; fp=E/'predictor_development'/fn
        chk(rp.is_file() and fp.is_file() and rp.read_bytes()==fp.read_bytes(),f'P6 development {fn} exactly reproduces')
    # P7B structural selection/result fields (timing not involved).
    try:
        rr=json.loads((R/'residence_screen/P7B_SUMMARY.json').read_text()); ff=json.loads((E/'residence_screen/P7B_SUMMARY.json').read_text())
        chk(rr==ff,'P7B structural screen summary exactly reproduces')
    except Exception as ex: chk(False,f'P7B summary readable ({ex!r})')
    # P7 scientific quantities; do not require timing columns to match wall clock.
    try:
        rr=pd.read_csv(R/'residence_primary/p7_confirmatory_matched.csv'); ff=pd.read_csv(E/'residence_primary/results/p7_confirmatory_matched.csv')
        keys=['domain','instance_seed','policy','budget_fraction']; sci=['reuse_fraction_of_keep_all','relative_best_improvement_vs_restart','anytime_improvement_vs_restart','reused_prior_branch_pops','useful_resumes']
        a1=rr[keys+sci].sort_values(keys).reset_index(drop=True); b1=ff[keys+sci].sort_values(keys).reset_index(drop=True)
        chk(a1.shape==b1.shape and all((a1[c].fillna(-999999)==b1[c].fillna(-999999)).all() for c in keys+sci),'P7 scientific matched outcomes reproduce (timing excluded)')
    except Exception as ex: chk(False,f'P7 scientific comparison readable ({ex!r})')
    # P8 scientific quantities; runtime bookkeeping may vary but deterministic branch/objective outcomes should match.
    try:
        rr=pd.read_csv(R/'measured_replay/p8_external_runs.csv'); ff=pd.read_csv(E/'measured_replay/p8_external_runs.csv')
        keys=['sequence','app','regime','repetition','policy']; sci=['branch_pops_executed','reused_prior_branch_pops','useful_resumes','mean_normalized_objective','final_state_normalized_objective']
        a1=rr[keys+sci].sort_values(keys).reset_index(drop=True); b1=ff[keys+sci].sort_values(keys).reset_index(drop=True)
        ok=a1.shape==b1.shape
        for c in keys:
            ok=ok and a1[c].equals(b1[c])
        for c in sci:
            ok=ok and (a1[c]-b1[c]).abs().fillna(0).max()<=1e-12
        chk(ok,'P8 deterministic scientific outcomes reproduce (timing excluded)')
    except Exception as ex: chk(False,f'P8 scientific comparison readable ({ex!r})')
    # P9 exact summary/metrics.
    try:
        rr=json.loads((R/'cross_family_transfer/P9_CROSS_DOMAIN_SUMMARY.json').read_text()); ff=json.loads((E/'cross_family_transfer/P9_CROSS_DOMAIN_SUMMARY.json').read_text())
        chk(rr==ff,'P9 cross-domain summary exactly reproduces')
    except Exception as ex: chk(False,f'P9 summary readable ({ex!r})')
    # P10 is prospective: verify complete authoritative output contract and seal, not equality to nonexistent frozen results.
    p10=R/'09_P10_Independent_MDKP_Validation'
    expected=[p10/'screen/p10_screen_selection.json',p10/'development/p10_final_model.joblib',p10/'development/p10_history_model.joblib',p10/'blind_holdout/P10_BLIND_METRICS.json',p10/'confirmatory/p10_confirmatory_inference.csv',p10/'confirmatory/p10_policy_descriptives.csv',p10/'confirmatory/P10_ENVIRONMENT.json',p10/'confirmatory/P10_EXECUTION_SEAL.json']
    p10_complete=all(p.is_file() for p in expected)
    if a.allow_p10_pending and not p10_complete:
        chk(True,'P10 authoritative outputs pending by explicit verifier option')
    else:
        chk(p10_complete,'P10 authoritative output contract is complete')
        if (p10/'confirmatory/P10_EXECUTION_SEAL.json').is_file():
            seal=json.loads((p10/'confirmatory/P10_EXECUTION_SEAL.json').read_text())
            chk(bool(seal.get('source_sha256')) and bool(seal.get('result_sha256')) and bool(seal.get('environment_sha256')),'P10 execution seal binds source/environment/results')
    if fail:
        print(f'\nFULL RERUN VERIFICATION FAILED: {len(fail)} checks'); sys.exit(1)
    print('\nALL REPRODUCED-RESULT CHECKS PASSED')
if __name__=='__main__': main()
