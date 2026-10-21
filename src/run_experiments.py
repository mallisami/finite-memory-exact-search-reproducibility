#!/usr/bin/env python3
"""Convenience runner for Paper-2 experiments and full chained reproduction.

Individual stages write to results/reproduced by default and never alter
data/core.  The `all_paper2` target performs a clean chained rerun of
P5.5 -> P5.6 -> P6 development/freeze/blind -> P7B -> P7 -> P8 -> P9 -> P10,
using regenerated intermediate artifacts wherever scientifically appropriate.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys, time

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data/core'
C=ROOT/'src'
DEFAULT_O=ROOT/'results/reproduced'
PROT=ROOT/'experiments/core_protocols'
DEFAULT_O.mkdir(exist_ok=True)

env=os.environ.copy()
env['PYTHONPATH']=str(C)+os.pathsep+env.get('PYTHONPATH','')
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    env[k]='1'
env['PYTHONHASHSEED']='0'

def run(args, log_file:Path|None=None):
    args=[str(x) for x in args]
    print('+',' '.join(args),flush=True)
    if log_file:
        log_file.parent.mkdir(parents=True,exist_ok=True)
        with log_file.open('a',encoding='utf-8') as f:
            f.write('+ '+' '.join(args)+'\n'); f.flush()
            proc=subprocess.Popen(args,env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line,end='',flush=True); f.write(line); f.flush()
            rc=proc.wait()
            if rc!=0: raise subprocess.CalledProcessError(rc,args)
    else:
        subprocess.run(args,check=True,env=env,cwd=ROOT)

def stage_path(base:Path,name:str,filename:str)->Path:
    p=base/name/filename
    return p if p.is_file() else E/name/filename

def ensure_fresh(path:Path):
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f'Refusing to overwrite non-empty reproduction directory: {path}\nUse --run-id with a new name or move/delete the old reproduction directory.')
    path.mkdir(parents=True,exist_ok=True)

def run_p55(outroot,log=None):
    run([sys.executable,C/'stages/paper2_p55_hardening.py','--out-dir',outroot/'graph_development'],log)

def run_p56(outroot,log=None):
    run([sys.executable,C/'stages/paper2_p56_blind_holdout.py','--out-dir',outroot/'graph_holdout'],log)

def run_p6_train(outroot,workers,log=None):
    dataset=stage_path(outroot,'graph_development','p55_natural_candidate_dataset.csv')
    firewall=stage_path(outroot,'graph_holdout','P56_FEATURE_FIREWALL.json')
    run([sys.executable,C/'stages/paper2_p6_train_prediction.py','--dataset',dataset,'--firewall',firewall,'--out-dir',outroot/'predictor_development','--jobs',workers],log)
    # Freeze the regenerated P6 before opening/releasing the regenerated P5.6 labels.
    run([sys.executable,C/'stages/paper2_p6_freeze_preblind.py','--run-base',outroot,'--protocol-dir',PROT],log)

def run_p6_blind(outroot,log=None):
    # A fully reproduced base contains P56 + P6. Fall back to frozen evidence only
    # for standalone p6_blind usage when those stages have not been regenerated.
    base=outroot if (outroot/'predictor_development/P6_PREBLIND_RELEASE_MANIFEST.json').is_file() and (outroot/'graph_holdout/p56_final_blind_features.csv').is_file() else E
    run([sys.executable,C/'stages/paper2_p6_blind_evaluate.py','--base',base,'--out-dir',outroot/'predictor_holdout'],log)

def run_p7b(outroot,log=None):
    run([sys.executable,C/'stages/paper2_p7b_structural_width.py','--out-dir',outroot/'residence_screen','--iterations','200','--slice-pops','8'],log)

def run_p7(outroot,workers,log=None):
    base=outroot if (outroot/'predictor_development/p6_final_model.joblib').is_file() else E
    run([sys.executable,C/'stages/paper2_p7_confirmatory.py','--base',base,'--out-dir',outroot/'residence_primary','--workers',workers],log)

def run_p8(outroot,workers,log=None):
    predictor_base=outroot if (outroot/'predictor_development/p6_final_model.joblib').is_file() else E
    run([sys.executable,C/'stages/paper2_p8_external_validation.py','--base',E,'--predictor-base',predictor_base,'--out-dir',outroot/'measured_replay','--workers',workers],log)

def run_p9(outroot,log=None):
    dataset=stage_path(outroot,'graph_development','p55_natural_candidate_dataset.csv')
    run([sys.executable,C/'stages/paper2_p9_cross_domain.py','--dataset',dataset,'--out-dir',outroot/'cross_family_transfer'],log)

def run_p10(outroot,stage,timing_repeats=None,log=None):
    if stage=='verify':
        run([sys.executable,ROOT/'verify.py'],log); return
    if stage=='engineering':
        run([sys.executable,C/'stages/paper2_p10_engineering_validation.py','--cases','12'],log); return
    if stage=='all':
        run([sys.executable,ROOT/'verify.py'],log)
        run([sys.executable,'-m','pytest','-q',ROOT/'tests'],log)
        run([sys.executable,C/'stages/paper2_p10_engineering_validation.py','--cases','12'],log)
    cmdstage={'screen':'screen','development':'development','blind':'blind','confirmatory':'confirmatory','all':'all'}[stage]
    cmd=[sys.executable,C/'stages/paper2_p10_independent_validation.py',cmdstage,'--config',ROOT/'experiments/mdkp/engineering_validation/P10_FROZEN_CONFIG.json','--out-dir',outroot/'09_P10_Independent_MDKP_Validation']
    if timing_repeats is not None: cmd += ['--timing-repeats',str(timing_repeats)]
    run(cmd,log)

def full_reproduction(outroot,workers):
    ensure_fresh(outroot)
    log=outroot/'FULL_RERUN.log'
    started=time.time()
    metadata={'status':'RUNNING','run_root':str(outroot.relative_to(ROOT)),'workers':workers,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'stages':[]}
    def mark(name,fn):
        t=time.time(); print(f'\n=== {name} ===',flush=True); metadata['current_stage']=name; (outroot/'FULL_RERUN_STATUS.json').write_text(json.dumps(metadata,indent=2)+'\n')
        try:
            fn()
        except Exception as exc:
            metadata['status']='FAILED'; metadata['failed_stage']=name; metadata['error']=repr(exc); metadata['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); metadata['total_seconds']=time.time()-started
            (outroot/'FULL_RERUN_STATUS.json').write_text(json.dumps(metadata,indent=2)+'\n')
            raise
        metadata['stages'].append({'stage':name,'seconds':time.time()-t}); metadata.pop('current_stage',None); (outroot/'FULL_RERUN_STATUS.json').write_text(json.dumps(metadata,indent=2)+'\n')
    # Verify the release before computing anything.
    mark('package_verification',lambda: run([sys.executable,ROOT/'verify.py'],log))
    mark('regression_tests',lambda: run([sys.executable,'-m','pytest','-q',ROOT/'tests'],log))
    mark('P5.5_development_corpus',lambda: run_p55(outroot,log))
    mark('P5.6_sealed_holdout_generation',lambda: run_p56(outroot,log))
    mark('P6_development_and_preblind_freeze',lambda: run_p6_train(outroot,workers,log))
    mark('P6_sealed_holdout_evaluation',lambda: run_p6_blind(outroot,log))
    mark('P7B_outcome_blind_structural_screen',lambda: run_p7b(outroot,log))
    mark('P7_confirmatory_retention',lambda: run_p7(outroot,workers,log))
    mark('P8_measured_external_replay',lambda: run_p8(outroot,workers,log))
    mark('P9_leave_one_domain_out_transfer',lambda: run_p9(outroot,log))
    mark('P10_full_independent_validation',lambda: run_p10(outroot,'all',None,log))
    mark('reproduced_result_verification',lambda: run([sys.executable,C/'verify_reproduced_results.py','--run-root',outroot],log))
    metadata['status']='COMPLETE'; metadata['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); metadata['total_seconds']=time.time()-started
    (outroot/'FULL_RERUN_STATUS.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f"\nFULL PAPER-2 RERUN COMPLETE: {outroot}",flush=True)

ap=argparse.ArgumentParser()
ap.add_argument('stage',choices=['p55','p56','p6_train','p6_blind','p7b','p7','p8','p9','p10_verify','p10_engineering','p10_screen','p10_development','p10_blind','p10_confirmatory','p10_all','all_paper2'])
ap.add_argument('--workers',type=int,default=3)
ap.add_argument('--timing-repeats',type=int,default=None)
ap.add_argument('--run-id',default='FULL_RERUN',help='subdirectory of results/reproduced used by all_paper2')
a=ap.parse_args()
if a.workers<1: raise SystemExit('--workers must be >=1')

if a.stage=='all_paper2':
    full_reproduction(DEFAULT_O/a.run_id,a.workers)
else:
    O=DEFAULT_O
    if a.stage=='p55': run_p55(O)
    elif a.stage=='p56': run_p56(O)
    elif a.stage=='p6_train': run_p6_train(O,a.workers)
    elif a.stage=='p6_blind': run_p6_blind(O)
    elif a.stage=='p7b': run_p7b(O)
    elif a.stage=='p7': run_p7(O,a.workers)
    elif a.stage=='p8': run_p8(O,a.workers)
    elif a.stage=='p9': run_p9(O)
    elif a.stage=='p10_verify': run_p10(O,'verify')
    elif a.stage=='p10_engineering': run_p10(O,'engineering')
    elif a.stage=='p10_screen': run_p10(O,'screen',a.timing_repeats)
    elif a.stage=='p10_development': run_p10(O,'development',a.timing_repeats)
    elif a.stage=='p10_blind': run_p10(O,'blind',a.timing_repeats)
    elif a.stage=='p10_confirmatory': run_p10(O,'confirmatory',a.timing_repeats)
    elif a.stage=='p10_all': run_p10(O,'all',a.timing_repeats)
