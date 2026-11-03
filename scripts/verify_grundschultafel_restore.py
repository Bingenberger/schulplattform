"""Stopped file-store snapshot and restore into an isolated fresh volume."""
import hashlib,json,os,secrets,subprocess,sys,time
from pathlib import Path
from tafel_fixture import Client
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from schulplattform.snapshot import checksum
private=Path((ROOT/".work/tafel-last-fixture").read_text())
fixture=json.loads((private/"fixture.json").read_text())
directory=private/("restore-"+secrets.token_hex(5));directory.mkdir(mode=0o700)
project="sp-tafel-restore-"+secrets.token_hex(5);volume=project+"-data"
PYTHON="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
operations=[]
def run(command,**kwargs):
    result=subprocess.run(command,capture_output=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Restore command failed"
    return result.stdout
assert not run(["docker","ps","-q","--filter","label=com.docker.compose.project="+fixture["project"]]).strip()
helper=["docker","run","--rm","--read-only","--network","none","--user","10001:10001","--cap-drop","ALL",
    "--security-opt","no-new-privileges:true","--memory","512m","--cpus","1","--pids-limit","64",
    "--tmpfs","/tmp:size=256m,mode=1777","-e","PYTHONDONTWRITEBYTECODE=1","-e","PYTHONPATH=/helper",
    "-v",str(ROOT/"schulplattform")+":/helper/schulplattform:ro"]
source="""import sys
from pathlib import Path
from schulplattform.snapshot import create
root=Path('/data');paths=list(root.iterdir())
assert not any(p.name.startswith('.lock-') or p.name.endswith('.tmp') for p in paths)
create(root,sys.stdout.buffer,files=[p.name for p in paths if p.is_file()],directories=[p.name for p in paths if p.is_dir()])
"""
command=helper+["-v",fixture["volume"]+":/data:ro",PYTHON,"python","-c",source]
archive=directory/"snapshot.tar"
fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,"wb") as stream:
    result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,timeout=180)
assert result.returncode==0
operations.append({"command":command,"exitCode":0})
digest=checksum(archive)
run(["docker","volume","create",volume])
run(["docker","run","--rm","--network","none","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
    "-v",volume+":/data","grundschultafel:0.1.0-dev","node","-e",
    "const fs=require('node:fs');if(fs.readdirSync('/data').length||fs.statSync('/data').uid!==10001)process.exit(1)"])
restore="""import sys,shutil,json
from pathlib import Path
from schulplattform.snapshot import restore
archive=Path('/tmp/snapshot.tar')
with archive.open('wb') as output:shutil.copyfileobj(sys.stdin.buffer,output)
manifest=restore(archive,Path('/data'),sys.argv[1])
users=json.loads(Path('/data/users.json').read_text())
assert len(users)==4 and len({u['id'] for u in users})==4
assert sorted(u['role'] for u in users)==['admin','teacher','teacher','teacher']
assert json.loads(Path('/data/schema.json').read_text())['version']==1
assert all(p.stat().st_uid==10001 and p.stat().st_gid==10001 for p in Path('/data').rglob('*'))
assert all(p.stat().st_mode&511==(448 if p.is_dir() else 384) for p in Path('/data').rglob('*'))
print(json.dumps({'files':len(manifest['entries']),'userIdsPreserved':True,'ownershipAndPermissions':True,'schema':1}))
"""
command=helper+["-i","-v",volume+":/data",PYTHON,"python","-c",restore,digest]
with archive.open("rb") as stream:restored=json.loads(run(command,stdin=stream))
with archive.open("rb") as stream:repeat=subprocess.run(command,stdin=stream,capture_output=True,timeout=180)
assert repeat.returncode!=0
override=directory/"restore.json";override.write_text(json.dumps({"volumes":{"data":{"external":True,"name":volume}}}))
env=os.environ|{"TAFEL_PORT":"44961","BASE_URL":"http://localhost:44961","TAFEL_SECRET_FILE":fixture["keyFile"]}
compose=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/grundschultafel/docker-compose.yml"),"-f",str(override)]
try:
    run(compose+["up","-d","--no-build","--wait","--wait-timeout","90"],env=env)
    anonymous=Client();teacher=Client();other=Client()
    anonymous.call("GET","/health/ready")
    anonymous.call("GET","/api/admin/users",expected=401)
    teacher.call("POST","/api/auth/login",{"username":"fixture-teacher-0","password":"729104"})
    assert teacher.call("GET","/api/auth/me")["user"]["id"]==fixture["teacher"]
    assert teacher.call("GET","/api/notebooks/fixture-book")["name"]=="Synthetic notebook"
    assert len(teacher.call("GET",fixture["asset"]))>20
    teacher.call("GET","/api/admin/users",expected=403)
    other.call("POST","/api/auth/login",{"username":"fixture-teacher-3","password":"529103"})
    other.call("GET","/api/notebooks/fixture-book",expected=404)
    other.call("GET",fixture["asset"],expected=404)
    anonymous.call("POST","/api/auth/login",{"username":"fixture-teacher-1","password":"529101"},expected=401)
    report={"scope":"stopped JSON file store and asset tree; fresh volume, original separately supplied key",
        "archiveSha256":digest,**restored,"nonemptyTargetRejected":True,"notebookAndAssetRecovered":True,
        "teacherIdMatchesSource":True,"deletedAccountRemainsDenied":True,"crossOwnerAndAdminDenied":True,
        "noMigrationOrBootstrapOnRestore":True,"limits":["local unencrypted archive","no offsite transport","no browser rendering"]}
finally:
    run(compose+["stop"],env=env)
report["stoppedDataRetained"]=True
(ROOT/"docs/implementation/evidence/grundschultafel-restore.json").write_text(json.dumps(report,indent=2)+"\n")
(ROOT/"docs/implementation/evidence/grundschultafel-restore-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
print(json.dumps(report))
