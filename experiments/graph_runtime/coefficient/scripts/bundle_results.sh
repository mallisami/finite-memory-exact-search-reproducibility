#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then echo "usage: $0 <result_dir> <bundle_name>" >&2; exit 2; fi
DIR="$1"; NAME="$2"; test -d "$DIR"
python - "$DIR" <<'INNERPY'
import hashlib,sys,json
from pathlib import Path
p=Path(sys.argv[1]); rows=[]
for f in sorted(x for x in p.rglob('*') if x.is_file()):
 h=hashlib.sha256(f.read_bytes()).hexdigest(); rows.append({'path':str(f.relative_to(p)),'sha256':h,'bytes':f.stat().st_size})
(p/'RESULT_MANIFEST_SHA256.json').write_text(json.dumps(rows,indent=2)+'\n')
INNERPY
tar -C "$(dirname "$DIR")" -czf "${NAME}.tar.gz" "$(basename "$DIR")"
sha256sum "${NAME}.tar.gz" > "${NAME}.tar.gz.sha256"
echo "Created ${NAME}.tar.gz"
