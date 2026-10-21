from __future__ import annotations
import argparse,csv,hashlib
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);a=ap.parse_args();root=Path(a.root);mf=root/'PACKAGE_SHA256SUMS.csv'
 rows=list(csv.DictReader(mf.open(newline='',encoding='utf-8')));bad=[]
 for r in rows:
  p=root/r['path']
  if not p.is_file():bad.append((r['path'],'missing'))
  elif sha(p)!=r['sha256']:bad.append((r['path'],'hash'))
 print(f'PACKAGE files verified: {len(rows)-len(bad)}/{len(rows)}')
 if bad:
  for x in bad:print('FAIL',*x)
  raise SystemExit(2)
if __name__=='__main__':main()
