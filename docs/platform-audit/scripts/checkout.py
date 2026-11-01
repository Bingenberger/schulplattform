#!/usr/bin/env python3
"""Fetch the audited commits into new isolated directories; never overwrite."""
import argparse,json,subprocess,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True)
rows=json.loads((Path(__file__).resolve().parents[1]/'evidence/repositories.json').read_text())
for r in rows:
 dest=a.root/r['repo']
 if dest.exists():
  actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
  if actual!=r['sha']:raise SystemExit(f'{dest}: unexpected SHA; not modified')
  print(r['repo'],'already at audited SHA');continue
 private=r['repo']=='schulanmeldung';url=f"git@github.com:Bingenberger/{r['repo']}.git" if private else f"https://github.com/Bingenberger/{r['repo']}.git"
 env=os.environ|{'GIT_TERMINAL_PROMPT':'0'}
 if private:env['GIT_SSH_COMMAND']='ssh -F /dev/null -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes'
 subprocess.run(['git','init',str(dest)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(dest),'remote','add','origin',url],check=True)
 subprocess.run(['git','-C',str(dest),'fetch','--depth=1','origin',r['sha']],env=env,check=True)
 subprocess.run(['git','-C',str(dest),'checkout','--detach',r['sha']],check=True)
 print(r['repo'],r['sha'])
