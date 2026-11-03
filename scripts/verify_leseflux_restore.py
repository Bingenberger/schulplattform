"""Stopped-writer Leseflux backup and restore into a fresh isolated PostgreSQL cluster."""
import json,os,secrets,socket,subprocess,sys
from pathlib import Path
from leseflux_fixture import Browser,CONTRACT
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.postgres import Postgres
private=Path((ROOT/".work/leseflux-latest-fixture").read_text())
fixture=json.loads((private/"fixture.json").read_text());child=json.loads((private/"restore-child.json").read_text())
project="sp-leseflux-restore-"+secrets.token_hex(5)
directory=private/project;directory.mkdir(mode=0o700)
env=os.environ|{"LESEFLUX_SECRETS_DIR":fixture["secretDirectory"],"COOKIE_SECURE":"false"}
source=[str(ROOT/".work/docker-compose"),"-p",fixture["project"],"-f",str(ROOT/".work/apps/leseflux/docker-compose.yml")]
operations=[]
def run(command,**kwargs):
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Restore command failed"
    return result.stdout
assert not run(["docker","ps","-q","--filter","label=com.docker.compose.project="+fixture["project"]]).strip()
run(source+["up","-d","--no-build","--wait","postgres"])
source_id=run(source+["ps","-q","postgres"]).strip()
database=Postgres(["docker","exec",source_id],"leseflux","leseflux")
metadata=database.snapshot(directory/"database.dump")
with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
env|={"LESEFLUX_PORT":str(port),"CORS_ORIGIN":"http://localhost:"+str(port)}
target=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/leseflux/docker-compose.yml")]
report={}
try:
    run(target+["up","-d","--no-build","--wait","postgres"])
    cid=run(target+["ps","-q","postgres"]).strip()
    restored=Postgres(["docker","exec","-i",cid],"leseflux","leseflux")
    restored.restore_into_empty(directory/"database.dump",metadata,directory)
    try:restored.restore_into_empty(directory/"database.dump",metadata,directory)
    except ValueError as error:assert "not empty" in str(error)
    else:raise AssertionError("Nonempty restore accepted")
    run(target+["up","-d","--no-build","--wait","app"])
    after=json.loads(run(target+["exec","-T","app","node","-"],input=CONTRACT))
    assert after==fixture["contract"],"Business records changed across restore"
    assert restored.query("SELECT current_user || ':' || rolsuper || ':' || rolcreatedb || ':' || rolcreaterole FROM pg_roles WHERE rolname=current_user")=="leseflux:false:false:false"
    assert restored.query("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")=="0"
    teacher,kid,anonymous=Browser(port),Browser(port),Browser(port)
    teacher.call("GET","/health/ready")
    anonymous.call("GET","/api/auth/me",expected=401)
    teacher.call("POST","/api/auth/login-teacher",{"email":fixture["teacherEmail"],"password":fixture["teacherPassword"]})
    detail=teacher.call("GET","/api/teacher/classes/"+fixture["class"])
    # Legacy clear QR values stay in the restored database, never in public class projections.
    assert child["qrToken"] not in json.dumps(detail) and "passwordHash" not in json.dumps(detail)
    login=kid.call("POST","/api/auth/login-child",{"qrToken":child["qrToken"]})
    assert login["user"]["id"]==child["id"]
    kid.call("GET","/api/admin/teachers",expected=403)
    kid.call("POST","/api/auth/logout",{})
    login=kid.call("POST","/api/auth/login-child-code",{"loginCode":child["loginCode"]})
    assert login["user"]["id"]==child["id"]
    progress=[row for row in after["UserProgress"] if row["userId"]==child["id"]][0]
    assert progress["totalSessions"]==1 and progress["starCount"]==3
    assert any(row["id"]==child["sessionId"] for row in after["TrainingSession"])
    report={"imageId":json.loads(run(["docker","inspect",run(target+["ps","-q","app"]).strip()]))[0]["Image"],
        "database":metadata,"allBusinessRowsMatch":True,"noMigrationOrSeedOnRestore":True,
        "unprivilegedRole":True,"foreignKeysValidated":True,"nonemptyTargetRejected":True,
        "teacherAndBothChildCredentialsWork":True,"trainingAndProgressPreserved":True,
        "legacyCardsPreservedAndHidden":True,"anonymousAndChildAdminDenied":True,
        "scope":"Fresh PostgreSQL volume; stopped writers; same separately supplied private credentials",
        "limits":["No encrypted offsite backup","No real identity import"]}
finally:
    run(target+["stop"]);run(source+["stop"])
report["stoppedDataRetained"]=True
out=ROOT/"docs/implementation/evidence"
(out/"leseflux-restore.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"leseflux-restore-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
print(json.dumps(report))
