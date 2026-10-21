#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-base',required=True,help='directory containing reproduced P56 and P6 stage folders')
    ap.add_argument('--protocol-dir',required=True)
    a=ap.parse_args()
    base=Path(a.run_base); prot=Path(a.protocol_dir)
    p6=base/'predictor_development'; p56=base/'graph_holdout'
    required=[
        p6/'P6_DEVELOPMENT_HASHES.json',p6/'P6_DEVELOPMENT_SUMMARY.json',p6/'P6_SELECTED_MODEL_SPEC.json',
        p6/'p6_final_model.joblib',p6/'p6_calibration.joblib',p56/'P56_FEATURE_FIREWALL.json',
        p56/'P56_BLIND_HOLDOUT_SEAL.json',p56/'p56_final_blind_features.csv',p56/'p56_final_blind_labels.SEALED.csv',
        prot/'P6_FROZEN_PROTOCOL_PRETRAINING.md',prot/'P6_IMPLEMENTATION_FREEZE_PRETRAINING.md']
    missing=[str(p) for p in required if not p.is_file()]
    if missing: raise FileNotFoundError('missing preblind inputs: '+', '.join(missing))
    spec=json.loads((p6/'P6_SELECTED_MODEL_SPEC.json').read_text())
    manifest={
      'bootstrap_replicates':2000,
      'bootstrap_seed':20261005,
      'calibration_choice':spec['calibration'],
      'hashes':{
        'base_protocol':sha(prot/'P6_FROZEN_PROTOCOL_PRETRAINING.md'),
        'calibration':sha(p6/'p6_calibration.joblib'),
        'dev_hashes':sha(p6/'P6_DEVELOPMENT_HASHES.json'),
        'dev_summary':sha(p6/'P6_DEVELOPMENT_SUMMARY.json'),
        'feature_firewall':sha(p56/'P56_FEATURE_FIREWALL.json'),
        'final_model':sha(p6/'p6_final_model.joblib'),
        'holdout_features':sha(p56/'p56_final_blind_features.csv'),
        'holdout_labels':sha(p56/'p56_final_blind_labels.SEALED.csv'),
        'holdout_seal':sha(p56/'P56_BLIND_HOLDOUT_SEAL.json'),
        'implementation_freeze':sha(prot/'P6_IMPLEMENTATION_FREEZE_PRETRAINING.md'),
        'model_spec':sha(p6/'P6_SELECTED_MODEL_SPEC.json'),
      },
      'rule':'No model, feature, hyperparameter, calibration, selector, or metric change is permitted after the sealed label file is opened.',
      'selected_model':spec,
      'status':'PREBLIND_FROZEN_READY_FOR_ONE_TIME_RELEASE',
    }
    (p6/'P6_PREBLIND_RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lines=[]
    for key in ('implementation_freeze','feature_firewall','dev_summary','model_spec','final_model','calibration'):
        rel={
          'implementation_freeze':prot/'P6_IMPLEMENTATION_FREEZE_PRETRAINING.md',
          'feature_firewall':p56/'P56_FEATURE_FIREWALL.json','dev_summary':p6/'P6_DEVELOPMENT_SUMMARY.json',
          'model_spec':p6/'P6_SELECTED_MODEL_SPEC.json','final_model':p6/'p6_final_model.joblib','calibration':p6/'p6_calibration.joblib'}[key]
        lines.append(f"{sha(rel)}  {rel.name}")
    (p6/'P6_PREBLIND_FREEZE.sha256').write_text('\n'.join(lines)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
