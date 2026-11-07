"""PCR2 public reproducibility release contract tests."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={"Fig1.pdf","Fig2.pdf","Fig3.pdf","Fig4.pdf","Fig5.pdf","FigS1.pdf"}

def test_exclude_author_manuscripts_and_supplement():
    for p in ROOT.rglob("*"):
        if not p.is_file() or ".git" in p.parts:continue
        rel=p.relative_to(ROOT).as_posix()
        if rel.startswith("results/reproduced/"):continue
        assert p.suffix.lower() not in {".tex",".bib",".bbl",".docx",".ppt",".pptx"},rel
        if p.suffix.lower()==".pdf":
            assert all(word not in p.name.lower()
                for word in ("manuscript","online_resource","supplement")),rel

def test_frozen_figure_inventory():
    files={p.name for p in (ROOT/"figures/publication").iterdir() if p.is_file()}
    assert files==EXPECTED

def test_rebuild_five_publication_data_figures(tmp_path):
    run=subprocess.run([sys.executable,
        str(ROOT/"src/analysis/rebuild_publication_figures.py"),"--out",str(tmp_path)],
        cwd=ROOT,capture_output=True,text=True)
    assert run.returncode==0,run.stdout+"\n"+run.stderr
    assert {p.name for p in tmp_path.iterdir()}==EXPECTED-{"Fig1.pdf"}
    assert all(p.stat().st_size>1000 for p in tmp_path.iterdir())
