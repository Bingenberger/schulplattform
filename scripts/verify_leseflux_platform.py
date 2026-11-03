"""Eight-app local TLS, existing child cards, domain rollback and lifecycle."""
import hashlib,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
from leseflux_fixture import Browser,ADMIN,CONTRACT
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.proxy import caddyfile
from schulplattform.domains import Domains,DomainError
from schulplattform.pilot_engine import PilotEngine
pilot=Pilot(ROOT/".work/pilot-v18");private=pilot.directory/"lese-fixtures";private.mkdir(mode=0o700,exist_ok=True)
def code(source):return pilot.command([str(pilot.compose),"-p",pilot.project+"-leseflux","-f",
 str(ROOT/".work/apps/leseflux/docker-compose.yml"),"-f",str(pilot.directory/"leseflux.yml"),"exec","-T","app","node","-"],input=source)
def browser(host):return Browser(pilot.config["port"],host,pilot.directory/"root.crt")
original=pilot.current_domains();host=original["leseflux"]
fixturefile=private/"fixture.json"
if fixturefile.exists():fixture=json.loads(fixturefile.read_text())
else:
    code(ADMIN)
    admin=browser(host);admin.call("POST","/api/auth/login-teacher",{"email":"fixture-admin@example.invalid","password":"synthetic-admin-123"})
    teachers=[];classes=[]
    for i in range(2):
        email="platform-teacher"+str(i)+"@example.invalid"
        admin.call("POST","/api/admin/teachers",{"displayName":"Synthetic Teacher "+str(i),"email":email,"password":"synthetic-teacher-123"},expected=201)
        teacher=browser(host);teacher.call("POST","/api/auth/login-teacher",{"email":email,"password":"synthetic-teacher-123"})
        classes.append(teacher.call("POST","/api/teacher/classes",{"name":"Synthetic Class "+str(i),"schoolYear":"2026/27"},expected=201))
        teachers.append(email)
    first=browser(host);first.call("POST","/api/auth/login-teacher",{"email":teachers[0],"password":"synthetic-teacher-123"})
    child=first.call("POST","/api/teacher/students",{"displayName":"Synthetic Child","classId":classes[0]["id"],
        "parentalConsentDate":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")},expected=201)
    fixture={"teachers":teachers,"classes":classes,"child":child}
    fixturefile.write_text(json.dumps(fixture));fixturefile.chmod(0o600)
baseline=json.loads(code(CONTRACT));checks=[];fault=False
def verify(domains):
    host=domains["leseflux"]
    if fault and host=="lesen-defekt.localhost":return False
    teacher,other,kid,anonymous=[browser(host) for _ in range(4)]
    for _ in range(50):
        try:anonymous.call("GET","/health/ready");break
        except (OSError,AssertionError):time.sleep(.2)
    origin="https://"+host+":"+str(pilot.config["port"])
    credentials={"email":fixture["teachers"][0],"password":"synthetic-teacher-123"}
    anonymous.call("POST","/api/auth/login-teacher",credentials,expected=403,csrf=False)
    anonymous.call("POST","/api/auth/login-teacher",credentials,headers={"Origin":"https://foreign.invalid"},expected=403)
    logged=teacher.call("POST","/api/auth/login-teacher",credentials,headers={"Origin":origin,
        "X-Forwarded-Host":"forged.invalid","X-Forwarded-Proto":"http","X-Remote-User":"admin"})
    assert "token" not in logged and logged["user"]["role"]=="TEACHER"
    assert teacher.cookie_options["token"]=={"secure":True,"httponly":True,"samesite":"Strict"}
    other.call("POST","/api/auth/login-teacher",{"email":fixture["teachers"][1],"password":"synthetic-teacher-123"})
    other.call("GET","/api/teacher/classes/"+fixture["classes"][0]["id"],expected=404)
    anonymous.call("GET","/api/auth/me",expected=401)
    other.call("POST","/api/teacher/students",{"displayName":"Denied Synthetic Child","classId":fixture["classes"][0]["id"],
        "parentalConsentDate":"2026-11-03T12:00:00Z"},expected=404)
    child=fixture["child"]
    logged=kid.call("POST","/api/auth/login-child",{"qrToken":child["qrToken"]})
    assert logged["user"]["id"]==child["student"]["id"]
    kid.call("GET","/api/admin/teachers",expected=403)
    kid.call("POST","/api/auth/logout")
    logged=kid.call("POST","/api/auth/login-child-code",{"loginCode":child["loginCode"]})
    assert logged["user"]["id"]==child["student"]["id"]
    cards=teacher.call("GET","/api/teacher/classes/"+fixture["classes"][0]["id"]+"/qr-data")
    assert cards["students"][0]["loginCode"]==child["loginCode"]
    for client in (teacher,other,kid):client.call("POST","/api/auth/logout")
    checks.append({"domain":host,"secureCookie":True,"csrfAndForeignOriginDenied":True,
        "crossTeacherAndChildAdminDenied":True,"existingOpaqueQrAndPrintedCodePreserved":True})
    return True
def activate(domains):
    path=pilot.directory/"leseflux.yml"
    lines=["      CORS_ORIGIN: https://"+domains["leseflux"]+":"+str(pilot.config["port"])
        if line.startswith("      CORS_ORIGIN:") else line for line in path.read_text().splitlines()]
    with path.open("w") as stream:stream.write("\n".join(lines)+"\n");stream.flush();os.fsync(stream.fileno())
    pilot.compose_command("leseflux","up","-d","--no-build","--wait","--wait-timeout","90","app")
    config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()]).replace("admin localhost:2019","admin localhost:2019\n local_certs")
    with (pilot.directory/"Caddyfile").open("w") as stream:stream.write(config);stream.flush();os.fsync(stream.fileno())
    proxy=pilot.inspect_service("infra","proxy")["Id"]
    for action in ("validate","reload"):pilot.command(["docker","exec",proxy,"caddy",action,"--config","/etc/caddy/Caddyfile"])
assert verify(original)
driver=Domains(pilot.directory/"domain-transactions",original,"verwaltung.localhost",
 lambda old,new:set(new)==set(original) and all(h.endswith(".localhost") for h in new.values()),
 activate,verify,operation_lock=pilot.directory/"state/installation.lock")
try:
    driver.change("leseflux","lesen-neu.localhost")
    fault=True
    try:driver.change("leseflux","lesen-defekt.localhost")
    except DomainError as error:assert "restored" in str(error)
    else:raise AssertionError("Invalid domain accepted")
    assert pilot.current_domains()["leseflux"]=="lesen-neu.localhost"
finally:
    fault=False;driver.change("leseflux","lesen.localhost")
def stable():
    paths=[pilot.directory/"state/installation.json"]+list((pilot.directory/"secrets").rglob("*"))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
before=stable();containers={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
one,two=pilot.up(),pilot.up()
assert one==two and stable()==before
assert containers=={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
offset=len(pilot.log.read_text().splitlines())
engine=PilotEngine(pilot);assert not engine.execute("stop","leseflux")["running"]
browser("lesen.localhost").call("GET","/login",expected=503)
assert engine.execute("start","leseflux")["running"]
assert verify(original) and stable()==before and json.loads(code(CONTRACT))==baseline
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("platform-migrate.cjs" in row["command"] or "content.cjs" in row["command"] for row in operations)
backend=pilot.inspect_service("leseflux","app")
assert not any(backend["NetworkSettings"]["Ports"].values())
assert backend["Config"]["User"]=="10001:10001" and backend["HostConfig"]["ReadonlyRootfs"]
report={"scope":"Eight-app local pilot with synthetic school data and verified local CA","apps":list(pilot.apps),
 "installationId":one["id"],"port":pilot.config["port"],"imageId":backend["Image"],
 "privateRootlessReadOnlyBackend":True,"domainChange":True,"forcedFailureRollback":True,"originalDomainRestored":True,
 "twoNoopRuns":True,"containersKeysCheckpointsUnchanged":True,"stopMaintenance503":True,
 "noRepeatedMigrationOrContentSeed":True,"allBusinessRowsUnchanged":True,"checks":checks,
 "limits":["No public DNS/ACME validation","No Ubuntu acceptance","No camera scan or printed QR decoding","No capacity measurement"]}
pilot.stop();report["stoppedDataRetained"]=True
(ROOT/"docs/implementation/evidence/leseflux-platform.json").write_text(json.dumps(report,indent=2)+"\n")
(ROOT/"docs/implementation/evidence/pilot-v18-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report))
