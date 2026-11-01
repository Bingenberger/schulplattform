#!/usr/bin/env python3
"""Collect reproducible source metadata without copying app data or secrets."""
import argparse, json, re, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repos',type=Path,default=Path('/tmp/schulplattform-audit/repos'));a=p.parse_args()
out=Path(__file__).resolve().parents[1]/'evidence';out.mkdir(exist_ok=True)
result={}
for repo in json.loads((out/'repositories.json').read_text()):
 root=a.repos/repo['repo'];entry={'sha':repo['sha'],'packages':{},'runtime_files':{},'license_files':[],'instruction_files':[],'features':{}}
 for f in sorted(root.rglob('*')):
  if not f.is_file() or any(x in f.parts for x in ['.git','.venv','node_modules','__pycache__']):continue
  rel=f.relative_to(root).as_posix()
  if f.name in ['AGENTS.md','CLAUDE.md']:entry['instruction_files'].append(rel)
  if re.search(r'(?i)licen[sc]e|copyright|ofl|notice',f.name):entry['license_files'].append(rel)
  if f.name=='package.json':
   d=json.loads(f.read_text());entry['packages'][rel]={k:d[k] for k in ['name','version','engines','packageManager','scripts','dependencies','devDependencies','license'] if k in d}
  if f.name in ['requirements.txt','requirements-dev.txt','pyproject.toml','.nvmrc']:
   entry['runtime_files'][rel]=f.read_text()
  if f.suffix not in ['.py','.ts','.js','.prisma','.sql'] or any(x in f.parts for x in ['static','public','frontend','tests','test','e2e']):continue
  if f.stat().st_size>200000:continue
  for i,s in enumerate(f.read_text(errors='replace').splitlines(),1):
   for category,regex in {'oidc':r'(?i)oidc|openid|saml','mail':r'(?i)smtplib|smtp_|MAIL_SERVER','storage':r'(?i)journal_mode|sqlite3.connect|DATABASE_URL|provider = "postgresql"','jobs':r'(?i)subprocess.run|BackgroundScheduler|chromium.launch|socket.on\(','browser_storage':r'(?i)indexedDB|localStorage|serviceWorker','external':r'https://(?:www.googleapis|pix\.|tile\.|api\.)'}.items():
    if re.search(regex,s):entry['features'].setdefault(category,[]).append({'file':rel,'line':i})
 result[repo['repo']]=entry
(out/'source-inventory.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(f'{len(result)} repositories inventoried')
