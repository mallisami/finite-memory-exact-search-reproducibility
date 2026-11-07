"""Cross-author archive and public GitHub byte exactness for selected authoritative files."""
import csv
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_selected_author_release_blob_identity():
    path=ROOT/"docs/AUTHOR_RELEASE_EXACT_SOURCE_CROSSWALK_20261107.csv"
    with path.open(newline="",encoding="utf-8") as fp:
        rows=list(csv.DictReader(fp))
    assert len(rows)==16
    assert len({r["repo_path"] for r in rows})==len(rows)
    for row in rows:
        file=ROOT/row["repo_path"]
        assert file.is_file(),row["repo_path"]
        data=file.read_bytes()
        assert len(data)==int(row["bytes"]),row["repo_path"]
        git_blob=b"blob "+str(len(data)).encode()+b"\x00"+data
        assert hashlib.sha1(git_blob).hexdigest()==row["git_blob_sha1"],row["repo_path"]
    assert next(r for r in rows if r["repo_path"]=="figures/data/paper_headline_summary.json")["classification"]=="current_corrected"
