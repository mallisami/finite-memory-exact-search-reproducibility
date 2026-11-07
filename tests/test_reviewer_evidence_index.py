"""Reviewer source authority: every published claim has exactly one canonical public path."""
import csv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"docs/REVIEWER_EVIDENCE_INDEX.csv"

def test_canonical_claim_evidence_inventory():
    with INDEX.open(newline="",encoding="utf-8") as fp:
        rows=list(csv.DictReader(fp))
    expected={"P6_HOLDOUT","P6_DEVELOPMENT","P7_RETENTION","P8_AWS_CURRENT",
              "P9_NESTED_CURRENT","P10_ORIGINAL","P10_SAME_CASE_REPEAT",
              "RQ2_THREE_ARM_P7","RQ2_THREE_ARM_P8","RQ2_GRAPH_PRIMARY",
              "P0_COEFFICIENT","RQ3_MDKP_VM90","RQ3_CORRECTION_NO_GO",
              "DSB_MEASURED_STATES","FIGURES_DATA","FIGURES_FROZEN"}
    assert len(rows)==len(expected)==16
    assert {row["claim_id"] for row in rows}==expected
    for row in rows:
        for col in ("canonical_source","required_secondary"):
            path=row[col]
            assert path and not path.startswith("/") and ".." not in Path(path).parts
            assert (ROOT/path).is_file(),(row["claim_id"],col,path)

def test_original_paper_and_online_resource_are_not_released():
    assert not list(ROOT.glob("*.docx"))
    assert not list(ROOT.glob("*.tex"))
    for f in ROOT.rglob("*.pdf"):
        if "results/reproduced/" in f.as_posix():
            continue
        assert not any(word in f.name.lower()
            for word in ("main_manuscript","online_resource","supplement",
                         "main_paper","camera_ready")),f

def test_current_vs_historical_and_sample_independence_not_aliased():
    with INDEX.open(newline="",encoding="utf-8") as fp:
        by={row["claim_id"]:row for row in csv.DictReader(fp)}
    assert "/aws_20261107/" in by["P8_AWS_CURRENT"]["canonical_source"]
    assert "/nested_20261107/" in by["P9_NESTED_CURRENT"]["canonical_source"]
    assert "/same_case_repeat/" in by["P10_SAME_CASE_REPEAT"]["canonical_source"]
    assert by["RQ3_CORRECTION_NO_GO"]["status"]=="development"
