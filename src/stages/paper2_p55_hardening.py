#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median

from certified_assignment.paper2_dataset_hardening import (
    P55_ALLOWED_FEATURES,
    P55_DECISION_ITERATIONS,
    P55_DOMAINS,
    P55_FORBIDDEN_FEATURES,
    P55_SEEDS,
    feature_firewall,
    generate_natural_case_events,
    split_for_seed,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8'); return
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--out-dir', default='graph_development')
    ap.add_argument('--domains', default=','.join(P55_DOMAINS))
    ap.add_argument('--seeds', default=','.join(str(x) for x in P55_SEEDS))
    args=ap.parse_args()

    out=Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    domains=[x.strip() for x in args.domains.split(',') if x.strip()]
    seeds=[int(x) for x in args.seeds.split(',') if x.strip()]

    event_rows=[]; case_rows=[]; split_rows=[]
    for domain in domains:
        for seed in seeds:
            events, case_summary=generate_natural_case_events(domain,seed)
            split=split_for_seed(seed)
            case_summary['split']=split
            case_rows.append(case_summary)
            split_rows.append({'case_id':case_summary['case_id'],'domain':domain,'instance_seed':seed,'split':split})
            for e in events:
                row=e.to_dict(); row['split']=split; event_rows.append(row)

    write_csv(out/'p55_natural_candidate_dataset.csv', event_rows)
    write_csv(out/'p55_case_summary.csv', case_rows)
    write_csv(out/'p55_group_splits.csv', split_rows)
    (out/'P55_FEATURE_FIREWALL.json').write_text(json.dumps(feature_firewall(), indent=2), encoding='utf-8')

    by_split=Counter(r['split'] for r in event_rows)
    by_domain=Counter(r['domain'] for r in event_rows)
    target_by_split={}
    for split in ('train','validation','test'):
        rows=[r for r in event_rows if r['split']==split]
        target_by_split[split]={
            'rows':len(rows),
            'future_recurrence_fraction': mean(int(r['future_recurred']) for r in rows) if rows else 0.0,
            'future_compatible_recurrence_fraction': mean(int(r['future_compatible_recurrence']) for r in rows) if rows else 0.0,
            'incompatible_only_fraction': mean(int(r['future_incompatible_only']) for r in rows) if rows else 0.0,
        }
    recur=[r for r in event_rows if int(r['future_recurred'])]
    useful=[r for r in event_rows if int(r['future_compatible_recurrence'])]
    natural_compat=(len(useful)/len(recur)) if recur else 0.0

    summary={
        'design_status':'P5.5_hardened_preML_corpus',
        'domains':domains,
        'seeds':seeds,
        'independent_base_cases':len(case_rows),
        'decision_iterations':list(P55_DECISION_ITERATIONS),
        'natural_event_rows':len(event_rows),
        'events_by_domain':dict(by_domain),
        'events_by_split':dict(by_split),
        'target_prevalence_by_split':target_by_split,
        'overall_future_recurrence_fraction': mean(int(r['future_recurred']) for r in event_rows) if event_rows else 0.0,
        'overall_future_compatible_recurrence_fraction': mean(int(r['future_compatible_recurrence']) for r in event_rows) if event_rows else 0.0,
        'conditional_compatibility_given_recurrence':natural_compat,
        'mean_natural_recurrence_events_per_case':mean(int(r['natural_recurrence_events']) for r in case_rows) if case_rows else 0.0,
        'median_natural_recurrence_events_per_case':median(int(r['natural_recurrence_events']) for r in case_rows) if case_rows else 0.0,
        'allowed_feature_count':len(P55_ALLOWED_FEATURES),
        'forbidden_future_field_count':len(P55_FORBIDDEN_FEATURES),
        'split_rule':'grouped by (domain, instance_seed); 9/3/3 seeds per domain train/validation/test',
        'interpretation_boundary':(
            'P5.5 is a natural-controller dataset/protocol hardening gate. It is not an ML superiority '
            'result and not an end-to-end budgeted persistence performance result.'
        ),
    }
    (out/'P55_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
