from certified_assignment.paper2_dataset_hardening import (
    P55_ALLOWED_FEATURES,
    P55_FORBIDDEN_FEATURES,
    P56_ALLOWED_FEATURES,
    P56_DROPPED_FEATURES,
    feature_firewall,
    feature_firewall_p56,
    generate_natural_case_events,
    split_for_seed,
)


def test_natural_events_and_compatibility_labels():
    events, summary = generate_natural_case_events(
        "workflow", 101, total_iterations=70,
        decision_iterations=(20, 30), future_horizon=20,
    )
    assert summary["controller_iterations"] == 70
    assert events
    for e in events:
        assert e.checkpoint_bytes > 0
        assert e.future_compatible_count <= e.future_count
        assert e.future_compatible_recurrence in (0, 1)
        assert e.future_recurred in (0, 1)
        assert e.future_incompatible_only in (0, 1)
        if e.future_compatible_recurrence:
            assert e.realized_future_saved_branch_pops == e.invested_branch_pops


def test_p55_firewall_and_group_split():
    fw = feature_firewall()
    assert fw["target"] == "future_compatible_recurrence"
    assert "future_compatible_recurrence" in P55_FORBIDDEN_FEATURES
    assert not set(P55_ALLOWED_FEATURES).intersection(P55_FORBIDDEN_FEATURES)
    assert split_for_seed(101) == "train"
    assert split_for_seed(1010) == "validation"
    assert split_for_seed(1515) == "test"


def test_p56_firewall_is_23_features_and_removes_dead_duplicates():
    fw = feature_firewall_p56()
    assert len(P56_ALLOWED_FEATURES) == 23
    assert set(P56_DROPPED_FEATURES) == {
        "current_recurrent", "leaves_evaluated", "best_gain_at_checkpoint",
        "partial_branches_expanded", "residual_opportunity",
    }
    assert not set(P56_DROPPED_FEATURES).intersection(P56_ALLOWED_FEATURES)
    assert fw["allowed_model_features"] == list(P56_ALLOWED_FEATURES)
    assert not set(P56_ALLOWED_FEATURES).intersection(P55_FORBIDDEN_FEATURES)
