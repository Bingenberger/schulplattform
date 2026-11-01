#!/usr/bin/env python3
"""Read-only Docker/host metrics; explicit container names, no env/inspect secrets."""
import argparse,subprocess,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--containers',nargs='+',required=True);p.add_argument('--seconds',type=int,default=1800);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if any(not x.startswith('schulplattform-audit-') for x in a.containers):p.error('only isolated audit container names allowed')
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('w') as f:
 end=time.monotonic()+a.seconds
 while time.monotonic()<end:
  r=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*a.containers],text=True,capture_output=True)
  row={'time':time.time(),'docker_stats_exit':r.returncode,'containers':[json.loads(x) for x in r.stdout.splitlines() if x.startswith('{')], 'meminfo':Path('/proc/meminfo').read_text(),'diskstats':Path('/proc/diskstats').read_text(),'cpu':Path('/proc/stat').read_text(),'pressure':{k:Path('/proc/pressure',k).read_text() for k in ['cpu','memory','io']}}
  f.write(json.dumps(row)+'\n');f.flush();time.sleep(5)
