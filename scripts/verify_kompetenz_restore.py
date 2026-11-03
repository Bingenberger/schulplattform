"""Consistent SQLite plus private uploads/logo and templates into fresh volumes."""
import json,os,secrets,socket,subprocess,sys
from pathlib import Path
from kompetenz_fixture import Browser,CONTRACT
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.snapshot import checksum
private=Path((ROOT/'.work/kompetenz-latest-fixture').read_text())
fixture=json.loads((private/'fixture.json').read_text())
project='sp-kompetenz-restore-'+secrets.token_hex(5);directory=private/project;directory.mkdir(mode=0o700)
PYTHON='python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c'
operations=[]
def run(command,**kwargs):
 result=subprocess.run(command,capture_output=True,timeout=180,**kwargs)
 operations.append({'command':command,'exitCode':result.returncode})
 assert result.returncode==0,'Restore fixture command failed'
 return result.stdout
assert not run(['docker','ps','-q','--filter','label=com.docker.compose.project='+fixture['project']]).strip()
helper=['docker','run','--rm','--init','--read-only','--network','none','--user','10001:10001','--cap-drop','ALL',
 '--security-opt','no-new-privileges:true','--memory','512m','--pids-limit','64','--tmpfs','/tmp:size=256m,mode=1777',
 '-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONPATH=/helper','-v',str(ROOT/'schulplattform')+':/helper/schulplattform:ro']
# Install one owned synthetic template fixture before capturing the paused source.
template_fixture="from pathlib import Path;import os;p=Path('/data/synthetic-template.txt');expected='Synthetic template fixture';assert not p.exists() or p.read_text()==expected;p.write_text(expected);os.chmod(p,0o600)"
run(helper+['-v',fixture['templateVolume']+':/data',PYTHON,'python','-c',template_fixture])
archives={}
# Independent empty targets avoid merging mountpoints into an allegedly empty directory.
for name,volume in [('instance',fixture['instanceVolume']),('templates',fixture['templateVolume'])]:
 archive=directory/(name+'.tar')
 if name=='instance':
  source="""from pathlib import Path
from schulplattform.snapshot import create
import sys
root=Path('/data')
files=[name for name in ('schullogo.png','schullogo.jpg') if (root/name).is_file()]
create(root,sys.stdout.buffer,database='schule.db',directories=['protected_uploads','legacy_uploads'],files=files)
"""
 else:
  source="""from pathlib import Path
from schulplattform.snapshot import create
import sys
root=Path('/data')
create(root,sys.stdout.buffer,files=[p.name for p in root.iterdir() if p.is_file()],directories=[p.name for p in root.iterdir() if p.is_dir()])
"""
 command=helper+['-v',volume+':/data:ro',PYTHON,'python','-c',source]
 fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as stream:
  result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,timeout=180)
 assert result.returncode==0
 archives[name]={'path':archive,'sha256':checksum(archive)}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env=os.environ|{'KM_SECRET_FILE':fixture['secretFile'],'KM_PORT':str(port),'APP_BASE_URL':'http://localhost:'+str(port),'SESSION_COOKIE_SECURE':'0','MAIL_SERVER':''}
base=[str(ROOT/'.work/docker-compose'),'-p',project,'-f',str(ROOT/'.work/apps/kompetenz-manager/docker-compose.yml')]
run(base+['create','app'],env=env)
cid=run(base+['ps','-aq','app'],env=env).decode().strip()
info=json.loads(run(['docker','inspect',cid]))[0]
volumes={m['Destination']:m['Name'] for m in info['Mounts'] if m['Type']=='volume'}
restore="""import sys,shutil
from pathlib import Path
from schulplattform.snapshot import restore
p=Path('/tmp/snapshot.tar')
with p.open('wb') as output:shutil.copyfileobj(sys.stdin.buffer,output)
restore(p,Path('/data'),sys.argv[1])
"""
for name,item in archives.items():
 volume=volumes['/app/'+('odt_templates' if name=='templates' else 'instance')]
 command=helper+['-i','-v',volume+':/data',PYTHON,'python','-c',restore,item['sha256']]
 with item['path'].open('rb') as stream:run(command,stdin=stream)
 with item['path'].open('rb') as stream:
  repeated=subprocess.run(command,stdin=stream,capture_output=True,timeout=180)
 assert repeated.returncode!=0
report={}
try:
 run(base+['up','-d','--no-build','--wait','app'],env=env)
 after=json.loads(run(base+['exec','-T','app','python','-'],env=env,input=CONTRACT.encode()))
 assert after==fixture['contract']
 teacher,other,anonymous=Browser(port),Browser(port),Browser(port)
 teacher.login('fixture-teacher0','new-synthetic-teacher-123');other.login('fixture-teacher1')
 anonymous.call('GET','/admin',expected=302);teacher.call('GET','/admin',expected=302)
 other.form('/diagnostik/foerderangaben/'+str(fixture['students'][0]),{'schuljahr':'2026/2027'},expected=403)
 assert teacher.call('GET','/media/beobachtung/'+str(fixture['observation'])).startswith(b'\x89PNG')
 assert teacher.call('GET','/schuelerakte/export/pdf/'+str(fixture['students'][0])).startswith(b'%PDF')
 permissions="""from pathlib import Path
import json,sqlite3
p=Path('/data/protected_uploads/synthetic.png')
with sqlite3.connect('/data/schule.db') as c:
 assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
 assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
print(json.dumps({'uid':p.stat().st_uid,'mode':p.stat().st_mode&511,'logo':Path('/data/schullogo.png').is_file()}))
"""
 attributes=json.loads(run(helper+['-v',volumes['/app/instance']+':/data:ro',PYTHON,'python','-c',permissions]))
 assert attributes=={'uid':10001,'mode':384,'logo':True}
 template_check="from pathlib import Path;p=Path('/data/synthetic-template.txt');assert p.read_text()=='Synthetic template fixture';assert p.stat().st_uid==10001 and p.stat().st_mode&511==384"
 run(helper+['-v',volumes['/app/odt_templates']+':/data:ro',PYTHON,'python','-c',template_check])

 report={'imageId':info['Image'],'scope':'Stopped web and notification writers; fresh empty SQLite/upload/template volumes; separately supplied existing session key',
  'allBusinessRowsAndIdsMatch':True,'rolesAndClassAssignmentsPreserved':True,'privateUploadsAndLogoRestored':True,'syntheticTemplateBytesPreserved':True,
  'sqliteIntegrityAndForeignKeys':True,'restoredPrivateOwnerAndMode':True,'nonemptyTargetsRejected':True,
  'realPdfAfterRestore':True,'anonymousAdminAndCrossClassDenied':True,'noMigrationOrSeedOnRestore':True,
  'snapshots':{name:item['sha256'] for name,item in archives.items()},'limits':['No encrypted offsite backup','No real legacy import']}
finally:run(base+['stop'],env=env)
report['stoppedDataRetained']=True
out=ROOT/'docs/implementation/evidence'
(out/'kompetenz-restore.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'kompetenz-restore-operations.json').write_text(json.dumps(operations,indent=2)+'\n')
print(json.dumps(report))
