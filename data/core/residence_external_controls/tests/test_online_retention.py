from pathlib import Path
import pickle

from certified_assignment.anytime_gap_certified_repair import initialize_anytime_repair
from certified_assignment.destroy_repair_analysis import build_destroy_repair_cache
from certified_assignment.domain_instances import make_domain_case
from certified_assignment.matched_lns_policies import PersistentCheckpointEntry
from certified_assignment.paper2_online_pilot import (
    FrozenP6Predictor,
    OnlineStepPolicy,
    StoredCheckpoint,
    generate_replay_trace,
    run_online_replay,
)


def _evidence_root() -> Path:
    return Path(__file__).resolve().parents[2] / "02_Authoritative_Experimental_Evidence"


def test_replay_trace_is_deterministic():
    a = generate_replay_trace("workflow", 2121, iterations=25, destroy_size=8)
    b = generate_replay_trace("workflow", 2121, iterations=25, destroy_size=8)
    assert a == b


def test_empirical_selector_respects_budget():
    tr = generate_replay_trace("microservice", 2323, iterations=40, destroy_size=8)
    k = run_online_replay("microservice", 2323, tr, policy_name="keep_all", slice_pops=4)
    budget = max(k.max_checkpoint_size_bytes, int(round(0.5 * max(1, k.peak_bytes))))
    e = run_online_replay(
        "microservice", 2323, tr, policy_name="empirical_compatible",
        slice_pops=4, budget_bytes=budget, budget_fraction=0.5,
    )
    assert e.peak_bytes <= budget


def test_frozen_p6_model_loads_and_learned_policy_respects_budget():
    tr = generate_replay_trace("workflow", 2424, iterations=25, destroy_size=8)
    k = run_online_replay("workflow", 2424, tr, policy_name="keep_all", slice_pops=2)
    budget = max(k.max_checkpoint_size_bytes, int(round(0.5 * max(1, k.peak_bytes))))
    pred = FrozenP6Predictor(_evidence_root())
    r = run_online_replay(
        "workflow", 2424, tr, policy_name="learned", slice_pops=2,
        budget_bytes=budget, budget_fraction=0.5, predictor=pred,
    )
    assert r.peak_bytes <= budget
    assert r.model_scoring_ms > 0.0


def test_accepted_noop_does_not_invalidate_dormant_states():
    case = make_domain_case("generic", 24, 6, seed=3131)
    policy = OnlineStepPolicy("keep_all", slice_pops=2, budget_bytes=None)
    keys = [tuple(range(0, 8)), tuple(range(8, 16))]
    for i, key in enumerate(keys, start=1):
        cache = build_destroy_repair_cache(case.instance, case.placement, key)
        cp = initialize_anytime_repair(case.instance, case.placement, key, prebuilt_cache=cache)
        entry = PersistentCheckpointEntry(checkpoint=cp, next_slice_ms=0.0, created_iteration=i)
        blob = pickle.dumps(entry, protocol=pickle.HIGHEST_PROTOCOL)
        policy.memory.records[key] = StoredCheckpoint(
            key=key, blob=blob, size_bytes=len(blob), cumulative_pops=0,
            probability=1.0, expected_value=0.0, created_iteration=i,
            last_scored_iteration=i,
        )
    before = set(policy.memory.records)
    policy.notify_after_decision(
        instance=case.instance, nodes=keys[0], accepted=True, iteration=3,
        objective_before=1.0, objective_after=1.0,
        placement=case.placement.copy(), changed_nodes=(),
    )
    assert set(policy.memory.records) == before
