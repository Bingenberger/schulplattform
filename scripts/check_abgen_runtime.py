"""Offline native unit suites, using direct Vitest entry points and bounded writable caches."""
import argparse,json,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
projects=['packages/model','packages/generators','packages/text','packages/render','apps/server','apps/web']
parser=argparse.ArgumentParser()
parser.add_argument('--workspace',choices=projects)
args=parser.parse_args()
selected=[args.workspace] if args.workspace else projects
program="""import {spawnSync} from 'node:child_process';
for(const project of PROJECTS){
 console.log('Workspace: '+project);
 const result=spawnSync(process.execPath,['/app/node_modules/vitest/vitest.mjs','run','--configLoader=native','--maxWorkers=2','--no-cache'],
 {cwd:'/app/'+project,stdio:'inherit',env:process.env});
 if(result.status!==0)process.exit(result.status??1);
}
""".replace('PROJECTS',json.dumps(selected))
command=['docker','run','--rm','--init','--read-only','--network','none','--cap-drop','ALL',
 '--security-opt','no-new-privileges:true','--memory','2048m','--cpus','2','--pids-limit','256',
 '--tmpfs','/tmp:size=256m,mode=1777','--tmpfs','/app/node_modules/.vitest-cache:size=128m,uid=10001,gid=10001,mode=700',
 '-e','CI=true','-e','XDG_DATA_HOME=/tmp/xdg-data','-e','XDG_CACHE_HOME=/tmp/xdg-cache',
 '-i','abgen-tests:0.1.0-dev','node','--input-type=module','-']
image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','abgen-tests:0.1.0-dev'],text=True).strip()
result=subprocess.run(command,input=program,capture_output=True,text=True,timeout=900)
name='abgen-functional.log' if not args.workspace else 'abgen-workspace-'+args.workspace.replace('/','-')+'.log'
target=root/('docs/implementation/evidence/'+name if result.returncode==0 else '.work/abgen-unit-failure.private.log')
target.write_text('imageId='+image+'\n$ '+' '.join(command)+'\n'+result.stdout+result.stderr+'\nexit_code='+str(result.returncode)+'\n')
plain=re.sub(r'\x1b\[[0-9;]*m','',result.stdout+result.stderr)
counts=re.findall(r'Tests\s+(\d+) passed',plain)
print(json.dumps({'imageId':image,'workspaces':selected,'passedByWorkspace':counts,'exitCode':result.returncode}))
if result.returncode:print(plain[-4500:])
raise SystemExit(result.returncode)
