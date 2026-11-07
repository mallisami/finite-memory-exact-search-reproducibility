"""PCR2 rejected RQ3 diagnostic files are reproducible, distinct from official VM90."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

D=Path(__file__).resolve().parents[1]/"results/mdkp/rejected_rq3_diagnostics_20261106"

def test_reconstructed_cpu_label_reliability_gate():
    gate=json.loads((D/"RECONSTRUCTION_AND_CORRECTION_GATE.json").read_text())
    summary=json.loads((D/"matched_cpu_repeatability_summary.json").read_text())
    by=pd.read_csv(D/"matched_cpu_repeatability_by_checkpoint.csv")
    raw=pd.read_csv(D/"matched_cpu_repeatability_raw.csv")
    assert gate["historical_dataset"]["rows"]==1948
    assert gate["new_reconstruction"]["rows"]==1875
    assert gate["new_reconstruction"]["administratively_censored"]==117
    assert len(by)==40 and len(raw)==280 and raw.groupby(["seed","created_iteration"]).size().eq(7).all()
    zero=by[by.saved_nodes.eq(0)]
    assert len(zero)==36 and int(zero.sign_reliable_6of7.sum())==13
    assert np.isclose(13/36,gate["cost_measurement_reliability_probe"]["stable_sign_fraction"])
    assert summary["zero_node_checkpoints"]==36
    assert not gate["scientific_gates"]["eligible_to_fit_and_adopt_new_net_cpu_value_model"]

def test_rejected_loso_remains_no_go_not_new_independent_confirmation():
    report=json.loads((D/"RESULT_SUMMARY.json").read_text())
    oof=pd.read_csv(D/"OOF_PREDICTIONS.csv")
    policy=pd.read_csv(D/"POLICY_RUNS_BY_SEED.csv")
    inputs=pd.read_csv(D/"INPUT_RECONSTRUCTED_DIAGNOSTIC.csv")
    assert report["decision"]=="NO_GO"
    assert len(inputs)==report["counts"]["input_rows"]==1875
    assert len(oof)==2*report["counts"]["eligible"]==3454
    assert len(policy)==100 and policy.seed.nunique()==25
    assert set(oof.policy)=={"historical_label_LOSO","corrected_quality_censor_LOSO"}
    assert report["seed_ratio_corrected_vs_historical"]["geometric_mean"]>1
    assert report["seed_ratio_corrected_vs_historical"]["bootstrap95"][1]>1
    assert not report["gate"]["no_objective_regression"]
    assert report["official_VM90_results"].startswith("unchanged")
