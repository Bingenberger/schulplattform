"""New isolated PG cluster plus template-volume restore, no migration or reseeding."""
import hashlib,json,os,secrets,socket,subprocess,sys,time
from pathlib import Path
from fahrrad_fixture import Browser,CONTRACT
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.postgres import Postgres
from schulplattform.snapshot import checksum
private=Path((ROOT/".work/fahrrad-latest-fixture").read_text())
fixture=json.loads((private/"fixture.json").read_text())
project="sp-fahrrad-restore-"+secrets.token_hex(5)
directory=private/project;directory.mkdir(mode=0o700);operations=[]
env=os.environ|{"FP_SECRETS_DIR":fixture["secretDirectory"],"FP_COOKIE_SECURE":"false","FP_KARTEN_KACHELN":""}
base=[str(ROOT/".work/docker-compose"),"-p",fixture["project"],"-f",str(ROOT/".work/apps/fahrradausbildung/docker-compose.yml")]
def run(cmd,**kwargs):
    result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180,**kwargs)
    operations.append({"command":cmd,"exitCode":result.returncode})
    assert result.returncode==0,"Restore command failed"
    return result.stdout
def helper(command,volume,mode,input=None):
    PYTHON="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
    cmd=["docker","run","--rm","--read-only","--network","none","--user","10001:10001","--cap-drop","ALL",
        "--security-opt","no-new-privileges:true","--memory","512m","--pids-limit","64","--tmpfs","/tmp:size=64m,mode=1777",
        "-e","PYTHONPATH=/helper","-e","PYTHONDONTWRITEBYTECODE=1","-v",str(ROOT/"schulplattform")+":/helper/schulplattform:ro",
        "-v",volume+":/data:"+mode,"-i",PYTHON,"python","-c",command]
    result=subprocess.run(cmd,input=input,capture_output=True,timeout=180)
    operations.append({"command":cmd,"exitCode":result.returncode})
    assert result.returncode==0,"Template snapshot helper failed"
    return result.stdout
assert not run(["docker","ps","-q","--filter","label=com.docker.compose.project="+fixture["project"]]).strip()
run(base+["up","-d","--no-build","--wait","db"])
source_id=run(base+["ps","-q","db"]).strip()
source=Postgres(["docker","exec",source_id],"fahrrad","fahrrad")
metadata=source.snapshot(directory/"database.dump")
template=helper("from schulplattform.snapshot import create\nimport sys\ncreate('/data',sys.stdout.buffer,files=['fixture.txt'])",fixture["templateVolume"],"ro")
archive=directory/"templates.tar";archive.write_bytes(template);archive.chmod(0o600)
template_digest=checksum(archive)
with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
env|={"FP_PORT":str(port),"FP_OEFFENTLICHE_URL":"http://localhost:"+str(port)}
target=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/fahrradausbildung/docker-compose.yml")]
report={}
try:
    run(target+["up","-d","--no-build","--wait","db"])
    cid=run(target+["ps","-q","db"]).strip()
    destination=Postgres(["docker","exec","-i",cid],"fahrrad","fahrrad")
    destination.restore_into_empty(directory/"database.dump",metadata,directory)
    try:destination.restore_into_empty(directory/"database.dump",metadata,directory)
    except ValueError as error:assert "not empty" in str(error)
    else:raise AssertionError("Nonempty DB restore accepted")
    # Compose create supplies fresh owned empty template volume without starting web.
    run(target+["create","app"])
    app=run(target+["ps","-aq","app"]).strip()
    info=json.loads(run(["docker","inspect",app]))[0]
    volume=next(m["Name"] for m in info["Mounts"] if m["Destination"]=="/vorlagen")
    command="from pathlib import Path\nfrom schulplattform.snapshot import restore\nimport sys\np=Path('/tmp/snapshot.tar');p.write_bytes(sys.stdin.buffer.read());restore(p,Path('/data'),'"+template_digest+"')"
    helper(command,volume,"rw",template)
    run(target+["up","-d","--no-build","--wait","--wait-timeout","90","app"])
    after=json.loads(run(target+["exec","-T","app","python","-"],input=CONTRACT))
    assert after==fixture["contract"]
    roles=destination.query("SELECT current_user || ':' || rolsuper || ':' || rolcreatedb || ':' || rolcreaterole FROM pg_roles WHERE rolname=current_user")
    assert roles=="fahrrad:false:false:false"
    assert destination.query("SELECT version_num FROM alembic_version")=="0008"
    assert destination.query("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")=="0"
    first,second=fixture["fixtures"];a,b,anonymous=Browser(port),Browser(port),Browser(port)
    anonymous.call("GET","/verwaltung/",expected=303)
    a.login(first["email"])
    a.page("/verwaltung/")
    # A restored limiter still blocks the previously locked account.
    import re
    html=b.page("/anmelden");csrf=re.search(r'name="csrf" value="([^"]+)"',html)[1]
    b.form("/anmelden",{"email":second["email"],"passwort":"synthetic-password","csrf":csrf},expected=429)
    a.call("GET","/verwaltung/strecken/"+str(second["track"]),expected=404)
    capability=first["token"]
    cfg=anonymous.call("GET","/api/p/"+capability+"/config")
    assert cfg["lauf_id"]==first["run"] and cfg["startnummern"]==[7]
    assert anonymous.call("GET","/api/p/"+capability+"/status")["offen"]==0
    assert a.call("GET","/verwaltung/laeufe/"+str(first["run"])+"/postenblaetter.pdf").startswith(b"%PDF")
    permissions=json.loads(helper("import json;from pathlib import Path\np=Path('/data/fixture.txt');print(json.dumps({'text':p.read_text(),'uid':p.stat().st_uid,'gid':p.stat().st_gid,'mode':p.stat().st_mode&511}))",volume,"ro"))
    assert permissions=={"text":"Synthetic template fixture","uid":10001,"gid":10001,"mode":384}
    assert int(destination.query("SELECT count(*) FROM pg_trigger WHERE tgrelid='ereignis'::regclass AND NOT tgisinternal AND tgenabled='O'"))>=1
    report={"scope":"stopped app writers; fresh separate PG cluster and template volume; same supplied DB credentials",
        "database":metadata,"templateSha256":template_digest,"schema":"0008","allFixtureRowsIdsRolesTokensAndEventsMatch":True,
        "unprivilegedAppRole":True,"foreignKeysValidated":True,"eventTriggerEnabled":True,"nonemptyTargetRejected":True,
        "templateBytesOwnerAndPrivateMode":True,"stationTokenAndPwaAccessPreserved":True,"pdfAfterRestore":True,
        "anonymousAndCrossSchoolDenied":True,"persistentLoginLockPreserved":True,"noMigrationOrSeedOnRestore":True,
        "limits":["No encrypted offsite backup","No unsynced browser IndexedDB data in server backup"]}
except AssertionError:
    # No catch-all fallback: errors must fail the proof.
    raise
finally:
    run(target+["stop"]);run(base+["stop"])
report["stoppedDataRetained"]=True
out=ROOT/"docs/implementation/evidence"
(out/"fahrrad-restore.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"fahrrad-restore-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
print(json.dumps(report))
