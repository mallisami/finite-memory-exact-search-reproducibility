"""PCR2 reviewer publication contract: author-derived builder, no manuscript files."""
from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"Fig1.pdf", "Fig2.pdf", "Fig3.pdf", "Fig4.pdf", "Fig5.pdf", "FigS1.pdf"}
REBUILT = EXPECTED - {"Fig1.pdf"}
PORTED = {
    "src/analysis/rebuild_publication_figures.py":
        "e81e294bcdd4e54ac15178e39e498716e1551ae37e47536ffa9ccd384dc8113c",
    "src/analysis/rebuild_Fig4_AWS_author.py":
        "b7a9980217a0849902bb96e22123e8337580830c2022cbb3c2f84eb1bdb8dc9d",
}

def test_exclude_manuscript_and_online_resource():
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("results/reproduced/"):
            continue
        assert p.suffix.lower() not in {".tex", ".bib", ".bbl", ".docx", ".ppt", ".pptx"}, rel
        if p.suffix.lower() == ".pdf":
            assert not any(s in p.name.lower()
                           for s in ("manuscript", "online_resource", "supplement")), rel

def test_exact_frozen_figure_inventory():
    directory = ROOT / "figures/publication"
    assert {p.name for p in directory.iterdir() if p.is_file()} == EXPECTED
    assert all((directory / name).stat().st_size > 1000 for name in EXPECTED)

def test_ported_author_code_is_byte_frozen():
    for path, expected in PORTED.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path

def test_original_author_source_rebuilds_five_figures():
    # The original builder intentionally owns its safe derived-output path.
    run = subprocess.run(
        [sys.executable, str(ROOT / "src/analysis/rebuild_publication_figures.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    directory = ROOT / "results/reproduced/publication_figures"
    assert {p.name for p in directory.iterdir() if p.is_file()} == REBUILT
    assert all((directory / name).stat().st_size > 1000 for name in REBUILT)
    for name in ("p6_ablation_fold_ranges.csv", "p7_retention_summary.csv",
                 "p9_nested_family_heldout_metrics.csv",
                 "dsb_measurement_independence_audit.json"):
        assert (ROOT / "results/reproduced/publication_data" / name).is_file(), name
