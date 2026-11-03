"""Combined SQLite/maps/private-mail restore into a new isolated empty volume."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
from schulplattform.snapshot import checksum
from losverkauf_fixture import Client,CONTRACT,probe

fixture_dir=Path((ROOT/".work/losverkauf-latest-fixture").read_text())
fixture=json.loads((fixture_dir/"fixture.json").read_text())
directory=fixture_dir/("restore-"+secrets.token_hex(5))
directory.mkdir(mode=0o700)
project="sp-lose-restore-"+secrets.token_hex(5)
volume=project+"-data"
operations=[]
PYTHON="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
helper=["docker","run","--rm","--read-only","--network","none","--cap-drop","ALL",
        "--security-opt","no-new-privileges:true","--user","10001:10001","--memory","512m","--cpus","1",
        "--pids-limit","64","--tmpfs","/tmp:size=256m,mode=1777","-e","PYTHONDONTWRITEBYTECODE=1",
        "-e","PYTHONPATH=/helper","-v",str(ROOT/"schulplattform")+":/helper/schulplattform:ro"]
def run(command,**kwargs):
    result=subprocess.run(command,capture_output=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Restore fixture command failed"
    return result.stdout
assert not run(["docker","ps","-q","--filter","label=com.docker.compose.project="+fixture["project"]]).strip()
archive=directory/"snapshot.tar"
command=helper+["-v",fixture["volume"]+":/data:ro",PYTHON,"python","-m","schulplattform.snapshot",
                "create","/data","--database","losverkauf.db","--directory","maps","--directory","mails"]
fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"wb") as stream:
    result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,timeout=180)
operations.append({"command":command,"exitCode":result.returncode})
assert result.returncode==0
digest=checksum(archive)
run(["docker","volume","create",volume])
# Copy-up supplies owner 10001 and empty image map; clear only that known seed file
# before restore. A preexisting or populated external volume is never accepted.
init="""from pathlib import Path
root=Path('/data')
assert sorted(p.name for p in root.iterdir())==['mails','maps']
assert list((root/'mails').iterdir())==[]
path=root/'maps/bezirke.geojson'
import json
assert json.loads(path.read_text())=={'type':'FeatureCollection','features':[]}
path.unlink()
(root/'maps').rmdir()
(root/'mails').rmdir()
assert not list(root.iterdir())
"""
run(["docker","run","--rm","--read-only","--network","none","--cap-drop","ALL",
     "--security-opt","no-new-privileges:true","-v",volume+":/data","losverkauf:0.1.0-dev","python","-c",init])
source="""import shutil,sys
from pathlib import Path
from schulplattform.snapshot import restore
path=Path('/tmp/snapshot.tar')
with path.open('wb') as stream: shutil.copyfileobj(sys.stdin.buffer,stream)
restore(path,Path('/data'),sys.argv[1])
"""
command=helper+["-i","-v",volume+":/data",PYTHON,"python","-c",source,digest]
with archive.open("rb") as stream:run(command,stdin=stream)
with archive.open("rb") as stream:
    repeated=subprocess.run(command,stdin=stream,capture_output=True,timeout=180)
assert repeated.returncode!=0
operations.append({"action":"nonempty-restore","exitCode":repeated.returncode})
with socket.socket() as listener:
    listener.bind(("127.0.0.1",0))
    port=listener.getsockname()[1]
override=directory/"restore.json"
override.write_text(json.dumps({"volumes":{"data":{"external":True,"name":volume}}}))
origin="http://127.0.0.1:"+str(port)
env=os.environ|{"LOSVERKAUF_SECRETS_DIR":fixture["secretDirectory"],"LOSVERKAUF_PORT":str(port),
                "BASE_URL":origin,"SMTP_HOST":"","TILE_URL":"","PROXY_IPS":""}
compose=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/losverkauf/docker-compose.yml"),"-f",str(override)]
out=ROOT/"docs/implementation/evidence"
try:
    run(compose+["up","-d","--no-build","--wait","--wait-timeout","90"],env=env)
    parent_token=(Path(fixture["secretDirectory"])/"parent-token").read_text().strip()
    checks=probe(Client(port),parent_token,origin,fixture["capability"])
    after=json.loads(run(compose+["exec","-T","app","python","-"],input=CONTRACT.encode(),env=env))
    assert after==fixture["contract"]
    files=json.loads(run(compose+["exec","-T","app","python","-"],input=b"""import hashlib,json,os
from pathlib import Path
files=list(Path('/data/mails').glob('*.eml'))
assert len(files)==1
paths=[Path('/data'),Path('/data/losverkauf.db'),Path('/data/maps'),Path('/data/mails'),files[0]]
print(json.dumps({'mailHash':hashlib.sha256(files[0].read_bytes()).hexdigest(),
'ownership':[{'uid':p.stat().st_uid,'gid':p.stat().st_gid,'mode':p.stat().st_mode&511} for p in paths]}))
""",env=env))
    assert files["mailHash"]==fixture["mailFile"]
    assert all(item["uid"]==10001 and item["gid"]==10001 for item in files["ownership"])
    assert [item["mode"] for item in files["ownership"]]==[0o700,0o600,0o700,0o700,0o600]
    report={"scope":"local synthetic combined SQLite/map/private-mail restore; original configuration and keys supplied",
            "imageId":fixture["imageId"],"archiveSha256":digest,"emptyNewVolume":True,
            "sqliteOnlineBackup":True,"sourceStopped":True,"noMigrationOrBootstrap":True,
            "schemaForeignKeysAndIds":True,"existingEditTokensPreserved":True,"outboxAndMailLogPreserved":True,
            "mapsAndPrivateMailPreserved":True,"nonemptyRestoreRejected":True,**files,**checks}
    (out/"losverkauf-restore.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
finally:
    run(compose+["down"],env=env)
    (out/"losverkauf-restore-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
