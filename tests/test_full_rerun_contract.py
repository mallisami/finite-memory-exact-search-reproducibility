from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_full_runner_has_complete_chain_and_clean_p6_firewall():
    txt=(ROOT/'src/run_experiments.py').read_text()
    assert "'all_paper2'" in txt
    assert "P56_FEATURE_FIREWALL.json" in txt
    assert "paper2_p6_freeze_preblind.py" in txt
    assert "--predictor-base" in txt
    expected=['P5.5_development_corpus','P5.6_sealed_holdout_generation','P6_development_and_preblind_freeze','P6_sealed_holdout_evaluation','P7B_outcome_blind_structural_screen','P7_confirmatory_retention','P8_measured_external_replay','P9_leave_one_domain_out_transfer','P10_full_independent_validation','reproduced_result_verification']
    for item in expected: assert item in txt

def test_p6_model_feature_contract_matches_clean_firewall_and_manuscript():
    fw55=json.loads((ROOT/'data/core/graph_development/P55_FEATURE_FIREWALL.json').read_text())
    fw=json.loads((ROOT/'data/core/graph_holdout/P56_FEATURE_FIREWALL.json').read_text())
    allowed55=set(fw55['allowed_model_features']); allowed=set(fw['allowed_model_features'])
    dropped=set(fw['dropped_from_p55'])
    assert len(allowed55)==28 and len(allowed)==23 and len(dropped)==5
    assert allowed55 - dropped == allowed
    spec=json.loads((ROOT/'data/core/predictor_development/P6_SELECTED_MODEL_SPEC.json').read_text())
    assert set(spec['features']).issubset(allowed)
    assert spec['feature_family']=='H+D' and spec['model_family']=='logistic'
    for forbidden in fw['forbidden_future_or_oracle_fields']:
        assert forbidden not in allowed
    required={'recent_moved_node_overlap_10','recent_adjacent_move_count_10','recent_moved_node_overlap_20','recent_adjacent_move_count_20'}
    incorrect={'recent_moved_nodes_mean_10','recent_moved_nodes_mean_20','accepted_moves_since_context','objective_delta_since_context'}
    for f in required: assert f in allowed
    for f in incorrect: assert f not in allowed
