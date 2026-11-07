"""Public RQ2 three-arm timing source contract; no host identity exposure."""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]/"results/rq2_three_arm_aws_20261107"

def test_three_arm_raw_and_median_source():
    result=json.loads((ROOT/"THREE_ARM_CORRECTED_ANALYSIS.json").read_text())
    forensic=json.loads((ROOT/"FORENSIC_VALIDATION_REPORT.json").read_text())
    assert result["coverage"]["hosts"]==4
    assert result["coverage"]["P7_independent_cases"]==45
    assert result["coverage"]["P8_independent_triplet_blocks"]==30
    assert forensic["anomalous_rows"]==0
    for panel,raw_n,med_n in (("P7",3240,540),("P8",2160,360)):
        raw=pd.read_csv(ROOT/f"{panel}_CORRECTED_RAW.csv")
        med=pd.read_csv(ROOT/f"{panel}_ATOMIC_MEDIANS.csv")
        assert len(raw)==raw_n and len(med)==med_n
        assert set(raw.host_id)==set(med.host_id)=={f"host_{i}" for i in range(4)}
        assert raw.learned_backends_semantic_parity_pass.all()
        assert raw.learned_backends_semantic_mismatch_count.eq(0).all()
        assert raw.arm_order.nunique()==6
        assert raw.groupby("arm_order").size().nunique()==1
        units=raw[["domain","seed"]].drop_duplicates().shape[0] if panel=="P7" else raw[["app","repetition"]].drop_duplicates().shape[0]
        assert units==(45 if panel=="P7" else 30)
        for name,den in (("optimized_vs_original","sklearn_external_wall_ms"),("optimized_vs_empirical","empirical_compatible_external_wall_ms")):
            observed=float(np.exp(np.log(med.direct_external_wall_ms/med[den]).mean()))
            expected=result[panel]["contrasts"][name]["geometric_mean_ratio"]
            assert np.isclose(observed,expected,atol=1e-12,rtol=0)
        assert not result[panel]["contrasts"]["optimized_vs_empirical"]["superiority_pass"]

def test_public_rq2_does_not_expose_original_ec2_ids():
    for p in ROOT.iterdir():
        if p.suffix in (".csv",".json"):
            assert not re.search(r"\bi-[0-9a-f]{17}\b",p.read_text()),p
