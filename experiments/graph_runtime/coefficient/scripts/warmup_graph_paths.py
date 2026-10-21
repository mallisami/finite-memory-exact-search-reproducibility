#!/usr/bin/env python3
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'04_SOURCE'; EXT=SRC/'pcr_tx_extension'; sys.path.insert(0,str(SRC)); sys.path.insert(0,str(EXT))
from fast_p6_predictor import FrozenP6CoefficientPredictor
from pcr_tx_extension.certified_assignment.paper2_online_pilot import generate_replay_trace
from pcr_tx_extension.certified_assignment.pcr_graph_engine import run_graph_campaign_case
p=FrozenP6CoefficientPredictor(ROOT/'05_MODELS'/'p6_final_model.joblib',ROOT/'05_MODELS'/'p6_calibration.joblib'); w=json.load(open(ROOT/'06_FROZEN_INPUTS'/'PRIMARY_A_CALIBRATION.json'))['graph']['integer_weights']; trace=generate_replay_trace('generic',3301,iterations=40,destroy_size=12)
for pol in ['restart','empirical_pW','learned_pW','empirical_pC','learned_pC']:
    r=run_graph_campaign_case(domain='generic',seed=3301,trace=trace,policy_name=pol,slice_pops=32,budget_bytes=750000,predictor=p,compute_weights=w); print(pol,r.trajectory_hash,r.branch_pops_executed,round(r.end_to_end_wall_ns/1e6,3))
print('WARMUP_COMPLETE_NON_SAMPLE')
