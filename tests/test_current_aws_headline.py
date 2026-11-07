"""Forbid publication-summary regression to the superseded pre-AWS P8 data."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def test_corrected_aws_headline_rederived_from_retained_rows():
    headline=json.loads((ROOT/"figures/data/paper_headline_summary.json").read_text())
    rows=pd.read_csv(ROOT/"results/measured_replay/aws_20261107/p8_external_runs.csv")
    analysis=json.loads((ROOT/"results/measured_replay/aws_20261107/P8_AWS_TRIPLET_BLOCK_REANALYSIS.json").read_text())
    assert len(rows)==360 and rows.sequence.nunique()==90
    wide=rows.pivot(index="sequence",columns="policy",values="branch_pops_executed")
    learned_saved=float((wide["restart"]-wide["learned"]).mean())
    increment=float((wide["empirical_compatible"]-wide["learned"]).mean())
    assert np.isclose(learned_saved,24.38888888888889,atol=1e-12)
    assert np.isclose(increment,1.9111111111111112,atol=1e-12)
    assert np.isclose(headline["work_saving"]["external_pops_per_sequence"],learned_saved,atol=1e-12)
    assert np.isclose(headline["p8_aws_derived_incremental_saved_pops_per_sequence"],increment,atol=1e-12)
    source=analysis["endpoints"]["learned_objective_improvement_vs_restart"]
    assert np.isclose(headline["objective"]["external_mean_effect"],source["mean"],atol=1e-15)
    assert np.allclose(headline["objective"]["triplet_block_ci"],source["triplet_block_bootstrap_95_ci"],atol=1e-15)
    assert np.allclose(headline["objective"]["cell_stratified_sensitivity_ci"],
                       source["cell_stratified_sensitivity_95_ci"],atol=1e-15)
    assert not np.isclose(learned_saved,24.72222222222222,atol=1e-3)

def test_current_p8_publication_files_cannot_be_confused_with_historical():
    assert (ROOT/"figures/data/p8_aws_triplet_block_work_saving_20261107.csv").is_file()
    assert (ROOT/"figures/data/p8_aws_app_regime_heterogeneity_20261107.csv").is_file()
    assert (ROOT/"docs/NOVEMBER_2026_SOURCE_ALIGNMENT.md").is_file()
