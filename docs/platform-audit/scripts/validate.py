#!/usr/bin/env python3
"""Artifact and source-link consistency, not an application safety certification."""
from pathlib import Path
import ast,csv,json,re,urllib.parse,hashlib
D=Path(__file__).resolve().parents[1];R=Path('/tmp/schulplattform-audit/repos')
expected='schulwissen fahrradausbildung schulanmeldung SL-Journal kompetenz-manager leseflux schuleva gswb grundschultafel schulkasse abgen losverkauf schulhelfer zackboing'.split()
required='README.md repository-matrix.csv architecture.md integration-contract.md identity-migration.md server-sizing.md operations.md implementation-roadmap.md open-questions.md tests.md licenses.md benchmarks/README.md prototype/README.md'.split()
errors=[]
for f in required:
 if not (D/f).is_file():errors.append('missing '+f)
rows=list(csv.DictReader((D/'repository-matrix.csv').open()));record=json.loads((D/'evidence/repositories.json').read_text())
if set(r['repository'] for r in rows)!=set(expected) or len(rows)!=14:errors.append('matrix must contain exactly 14 repositories')
for r in rows:
 if not re.fullmatch('[a-f0-9]{40}',r['commit']):errors.append('invalid SHA '+r['repository'])
 p=D/'apps'/(r['repository'].lower()+'.md')
 if not p.is_file() or r['commit'] not in p.read_text():errors.append('report/commit '+r['repository'])
 if R.exists() and (R/r['repository']).exists():
  import subprocess
  actual=subprocess.check_output(['git','-C',str(R/r['repository']),'rev-parse','HEAD'],text=True).strip()
  if actual!=r['commit']:errors.append('checkout SHA drift '+r['repository'])
checked_links=0
for p in D.rglob('*.md'):
 for match in re.finditer(r'\]\(([^)]+)\)',p.read_text()):
  target=match[1]
  if target.startswith(('http://','https://','#','mailto:')):
   m=re.match(r'https://github.com/Bingenberger/([^/]+)/blob/([a-f0-9]{40})/(.*?)#L(\d+)(?:-L(\d+))?$',target)
   if m and R.exists():
    repo,sha,name,start,end=m.groups();source=R/repo/urllib.parse.unquote(name)
    if not source.exists():errors.append('missing code reference '+target)
    elif max(int(start),int(end or start))>len(source.read_text(errors='replace').splitlines()):errors.append('line outside file '+target)
    checked_links+=1
   continue
  if not (p.parent/urllib.parse.unquote(target.split('#')[0])).exists():errors.append(f'broken local link {p.relative_to(D)} {target}')
for p in D.rglob('*.py'):
 try:ast.parse(p.read_text(),filename=str(p))
 except SyntaxError as e:errors.append(str(e))
for p in D.rglob('*.json'):
 try:json.loads(p.read_text())
 except Exception as e:errors.append(f'{p}: {e}')
result={'repositories':len(rows),'reports':len(list((D/'apps').glob('*.md'))),'commit_bound_links_checked':checked_links,'required_files':len(required),'errors':errors,'passed':not errors}
(D/'evidence/completeness-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(bool(errors))
