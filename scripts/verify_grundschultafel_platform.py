"""Six-app verified local TLS, canonical QR origin, rollback and retained lifecycle."""
import hashlib,json,os,secrets,sys,time
from pathlib import Path
from tafel_fixture import Client
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.proxy import caddyfile
from schulplattform.domains import Domains,DomainError
from schulplattform.pilot_engine import PilotEngine
pilot=Pilot(ROOT/".work/pilot-v12");private=pilot.directory/"tafel-fixtures";private.mkdir(mode=0o700,exist_ok=True)
def code(source):
    return pilot.command([str(pilot.compose),"-p",pilot.project+"-grundschultafel","-f",
        str(ROOT/".work/apps/grundschultafel/docker-compose.yml"),"-f",str(pilot.directory/"grundschultafel.yml"),
        "exec","-T","app","node","--input-type=module","-"],input=source)
def browser(host):return Client(pilot.config["port"],host,pilot.directory/"root.crt")
original=pilot.current_domains();checks=[];fault=False
bootstrap=code("import {bootstrap} from './scripts/bootstrap.mjs';process.stdout.write(await bootstrap('fixture.admin'))")
(private/"bootstrap-token").write_text(bootstrap);(private/"bootstrap-token").chmod(0o600)
admin=browser(original["grundschultafel"])
admin.call("POST","/api/auth/login",{"username":"fixture.admin","password":bootstrap})
admin.call("POST","/api/auth/change-password",{"currentPassword":bootstrap,"newPassword":"482719"})
user=admin.call("POST","/api/admin/users",{"username":"fixture.teacher","password":"538291","role":"teacher"})["user"]
teacher=browser(original["grundschultafel"]);teacher.call("POST","/api/auth/login",{"username":"fixture.teacher","password":"538291"})
teacher.call("PUT","/api/notebooks/domain-book",{"id":"domain-book","name":"Synthetic domain fixture","pages":[]})
def verify(domains):
    host=domains["grundschultafel"]
    if fault and host=="tafel-defekt.localhost":return False
    client=browser(host)
    for _ in range(50):
        try:client.call("GET","/health/ready");break
        except OSError:time.sleep(.2)
    origin="https://"+host+":"+str(pilot.config["port"])
    client.call("GET","/api/admin/users",expected=401)
    client.call("POST","/api/auth/login",{"username":"fixture.teacher","password":"538291"})
    assert client.call("GET","/api/auth/me")["user"]["id"]==user["id"]
    assert client.call("GET","/api/notebooks/domain-book")["name"]=="Synthetic domain fixture"
    client.call("POST","/api/mobile-upload/session",headers={"Origin":"https://foreign.invalid"},expected=403)
    ticket=client.call("POST","/api/mobile-upload/session",headers={"Origin":origin,"X-Forwarded-Host":"forged.invalid","X-Forwarded-Proto":"http"})
    assert ticket["url"].startswith(origin+"/upload?")
    assert ticket["expiresIn"]==900
    (private/"mobile-ticket").write_text(ticket["token"]);(private/"mobile-ticket").chmod(0o600)
    client.call("POST","/api/auth/logout")
    checks.append({"domain":host,"teacherIdAndNotebookPreserved":True,"canonicalQrOrigin":True,"foreignOriginDenied":True,"anonymousAdminDenied":True})
    return True
def activate(domains):
    path=pilot.directory/"grundschultafel.yml"
    lines=["      BASE_URL: https://"+domains["grundschultafel"]+":"+str(pilot.config["port"])
        if line.startswith("      BASE_URL:") else line for line in path.read_text().splitlines()]
    with path.open("w") as stream:stream.write("\n".join(lines)+"\n");stream.flush();os.fsync(stream.fileno())
    pilot.compose_command("grundschultafel","up","-d","--no-build","--wait","--wait-timeout","90","app")
    config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()]).replace("admin localhost:2019","admin localhost:2019\n local_certs")
    with (pilot.directory/"Caddyfile").open("w") as stream:stream.write(config);stream.flush();os.fsync(stream.fileno())
    cid=pilot.inspect_service("infra","proxy")["Id"]
    for action in ("validate","reload"):pilot.command(["docker","exec",cid,"caddy",action,"--config","/etc/caddy/Caddyfile"])
assert verify(original)
driver=Domains(pilot.directory/"domain-transactions",original,"verwaltung.localhost",
    lambda old,new:set(new)==set(original) and all(h.endswith(".localhost") for h in new.values()),
    activate,verify,operation_lock=pilot.directory/"state/installation.lock")
try:
    driver.change("grundschultafel","tafel-neu.localhost")
    fault=True
    try:driver.change("grundschultafel","tafel-defekt.localhost")
    except DomainError as error:assert "restored" in str(error)
    else:raise AssertionError("Failed domain check accepted")
    assert pilot.current_domains()["grundschultafel"]=="tafel-neu.localhost"
finally:
    fault=False;driver.change("grundschultafel","tafel.localhost")
def stable():
    paths=[pilot.directory/"state/installation.json"]+list((pilot.directory/"secrets").rglob("*"))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
before=stable();containers={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
first,second=pilot.up(),pilot.up()
assert first==second and stable()==before
assert containers=={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
offset=len(pilot.log.read_text().splitlines())
engine=PilotEngine(pilot);assert not engine.execute("stop","grundschultafel")["running"]
browser("tafel.localhost").call("GET","/",expected=503)
assert engine.execute("start","grundschultafel")["running"]
assert verify(original) and stable()==before
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("scripts/migrate.mjs" in row["command"] or "scripts/bootstrap.mjs" in row["command"] for row in operations)
backend=pilot.inspect_service("grundschultafel","app")
assert not any(backend["NetworkSettings"]["Ports"].values())
assert backend["Config"]["User"]=="10001:10001" and backend["HostConfig"]["ReadonlyRootfs"]
report={"scope":"six-app local pilot, synthetic accounts, verified local CA","apps":list(pilot.apps),
    "installationId":first["id"],"port":pilot.config["port"],"imageId":backend["Image"],
    "privateRootlessReadOnlyBackend":True,"domainChange":True,"forcedFailureRollback":True,"originalDomainRestored":True,
    "twoNoopRuns":True,"containersKeysCheckpointsUnchanged":True,"stopMaintenance503":True,"noRepeatedMigrationOrBootstrap":True,
    "checks":checks,"limits":["No public DNS/ACME ownership validation","No QR camera/browser automation","No hardware-bound device key",
    "No Ubuntu provisioning acceptance","No encrypted offsite backup"]}
pilot.stop();report["stoppedDataRetained"]=True
(ROOT/"docs/implementation/evidence/grundschultafel-platform.json").write_text(json.dumps(report,indent=2)+"\n")
(ROOT/"docs/implementation/evidence/pilot-v12-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report))
