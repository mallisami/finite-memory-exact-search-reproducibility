#!/usr/bin/env python3
"""Generate and seal the P5.6 blind final holdout without reporting labels.

This script deliberately writes decision-time features and future labels to
separate files.  It reports only case/event counts and cryptographic hashes;
it does not compute class prevalence or any model metric.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from certified_assignment.paper2_dataset_hardening import (
    P55_DOMAINS,
    P56_ALLOWED_FEATURES,
    P56_BLIND_SEEDS,
    feature_firewall_p56,
    generate_natural_case_events,
)

IDENTIFIERS=(
    'case_id','domain','instance_seed','decision_iteration','candidate_id',
    'destroy_set','future_horizon','requested_invested_branch_pops'
)
LABELS=('candidate_id','future_compatible_recurrence','future_recurred','future_incompatible_only')


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str,object]], fields: tuple[str,...]|list[str]) -> None:
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(fields)); w.writeheader(); w.writerows(rows)


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--out-dir',default='graph_holdout'); args=ap.parse_args()
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    feature_rows=[]; label_rows=[]; case_rows=[]
    for domain in P55_DOMAINS:
        for seed in P56_BLIND_SEEDS:
            events, summary=generate_natural_case_events(domain,seed)
            case_rows.append({
                'case_id':summary['case_id'],'domain':domain,'instance_seed':seed,
                'controller_iterations':summary['controller_iterations'],
                'decision_events_emitted':summary['decision_events_emitted'],
            })
            for e in events:
                d=e.to_dict()
                feature_rows.append({k:d[k] for k in (*IDENTIFIERS,*P56_ALLOWED_FEATURES)})
                label_rows.append({k:d[k] for k in LABELS})

    feature_path=out/'p56_final_blind_features.csv'
    label_path=out/'p56_final_blind_labels.SEALED.csv'
    cases_path=out/'p56_final_blind_cases.csv'
    firewall_path=out/'P56_FEATURE_FIREWALL.json'
    write_csv(feature_path,feature_rows,(*IDENTIFIERS,*P56_ALLOWED_FEATURES))
    write_csv(label_path,label_rows,LABELS)
    write_csv(cases_path,case_rows,('case_id','domain','instance_seed','controller_iterations','decision_events_emitted'))
    firewall_path.write_text(json.dumps(feature_firewall_p56(),indent=2),encoding='utf-8')

    manifest={
        'status':'SEALED_FINAL_HOLDOUT_DO_NOT_INSPECT_DURING_MODEL_SELECTION',
        'domains':list(P55_DOMAINS),
        'seeds_per_domain':list(P56_BLIND_SEEDS),
        'independent_cases':len(case_rows),
        'event_rows':len(feature_rows),
        'feature_count':len(P56_ALLOWED_FEATURES),
        'target_prevalence_inspected':False,
        'model_performance_inspected':False,
        'features_sha256':sha256(feature_path),
        'sealed_labels_sha256':sha256(label_path),
        'cases_sha256':sha256(cases_path),
        'firewall_sha256':sha256(firewall_path),
        'release_rule':(
            'Do not open or summarize the sealed-label file until the P6 model family, hyperparameters, '
            'calibration rule, exact byte selector, and decision metrics are frozen from development data.'
        ),
    }
    (out/'P56_BLIND_HOLDOUT_SEAL.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    # Intentionally print only non-label metadata/hashes.
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
