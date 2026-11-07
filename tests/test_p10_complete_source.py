"""Original P10 development/blind execution and sealed same-case repeat."""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
P10=ROOT/"results/mdkp/p10_20261107"

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def test_original_p10_development_and_holdout_population():
    dev=P10/"original/development"
    blind=P10/"original/blind_holdout"
    train=pd.read_csv(dev/"p10_development_dataset.csv")
    oof=pd.read_csv(dev/"p10_oof_predictions.csv")
    test=pd.read_csv(blind/"p10_blind_dataset.csv")
    prediction=pd.read_csv(blind/"p10_blind_predictions.csv")
    spec=json.loads((dev/"P10_MODEL_SUMMARY.json").read_text())
    holdout=json.loads((blind/"P10_BLIND_METRICS.json").read_text())
    assert len(train)==len(oof)==5155
    assert len(test)==len(prediction)==2503
    assert train.seed.nunique()==spec["development_cases"]==30
    assert test.seed.nunique()==holdout["cases"]==15
    assert set(train.seed).isdisjoint(set(test.seed))
    for name in ("p10_final_model.joblib","p10_calibration.joblib",
                 "p10_history_model.joblib","p10_history_calibration.joblib"):
        assert (dev/name).stat().st_size>0

def test_p10_original_and_repeat_seals_and_source():
    config=ROOT/"experiments/mdkp/engineering_validation/P10_FROZEN_CONFIG.json"
    source=ROOT/"experiments/mdkp/p10_20261107/executed_source_snapshot/paper2_p10_independent_validation.py"
    expected_src={
        "04_CODE/independent_mdkp/allocation.py":ROOT/"src/independent_mdkp/allocation.py",
        "04_CODE/independent_mdkp/controller.py":ROOT/"src/independent_mdkp/controller.py",
        "04_CODE/independent_mdkp/core.py":ROOT/"src/independent_mdkp/core.py",
        "04_CODE/independent_mdkp/model.py":ROOT/"src/independent_mdkp/model.py",
        "04_CODE/scripts/paper2_p10_independent_validation.py":source
    }
    seeds=[]
    for folder in ("original","same_case_repeat"):
        dirname=P10/folder/"confirmatory"
        seal=json.loads((dirname/"P10_EXECUTION_SEAL.json").read_text())
        assert digest(config)==seal["config_sha256"]
        for original_name,sha in seal["source_sha256"].items():
            assert digest(expected_src[original_name])==sha,original_name
        for filename,sha in seal["result_sha256"].items():
            assert digest(dirname/filename)==sha,filename
        cases=pd.read_csv(dirname/"p10_confirmatory_runs.csv")
        times=pd.read_csv(dirname/"p10_timing_repeats.csv")
        assert len(cases)==180 and len(times)==540 and cases.seed.nunique()==45
        seeds.append(set(cases.seed))
    assert seeds[0]==seeds[1],"Timing repetition must not double independent sample size"
