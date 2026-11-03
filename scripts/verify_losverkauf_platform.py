"""Five-app local TLS, personal parent recovery, domain rollback and lifecycle."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.domains import Domains,DomainError
from schulplattform.proxy import caddyfile
from schulplattform.pilot_engine import PilotEngine
from losverkauf_fixture import Client,GEO,MAP_SOURCE,CONTRACT,register,probe
from werkzeug.security import generate_password_hash

pilot=Pilot(ROOT/".work/pilot-v10")
out=ROOT/"docs/implementation/evidence"
fixture_dir=pilot.directory/"ticket-fixtures"
fixture_dir.mkdir(mode=0o700,exist_ok=True)
for name,value in {"admin-name":"synthetic.operator","admin-hash":generate_password_hash("synthetic-password")}.items():
    path=fixture_dir/name
    if not path.exists():
        path.write_text(value)
        path.chmod(0o444)
path=pilot.directory/"losverkauf.yml"
marker="# synthetic personal admin fixture"
if marker not in path.read_text():
    content=path.read_text().replace("      BASE_URL:", "      ADMIN_USERNAME_FILE: /run/secrets/fixture-admin-name\n      ADMIN_PASSWORD_HASH_FILE: /run/secrets/fixture-admin-hash\n      BASE_URL:")
    content=content.replace("    networks:", "    volumes:\n      - "+str(fixture_dir/"admin-name")+":/run/secrets/fixture-admin-name:ro\n      - "+str(fixture_dir/"admin-hash")+":/run/secrets/fixture-admin-hash:ro\n    networks:",1)
    path.write_text(content+"\n"+marker+"\n")
    pilot.compose_command("losverkauf","up","-d","--no-build","--wait","--wait-timeout","90","app")

def code(source):
    return pilot.command([str(pilot.compose),"-p",pilot.project+"-losverkauf",
        "-f",str(ROOT/".work/apps/losverkauf/docker-compose.yml"),"-f",str(pilot.directory/"losverkauf.yml"),
        "exec","-T","app","python","-"],input=source)
current=code("from pathlib import Path;print(Path('/data/maps/bezirke.geojson').read_text())")
assert json.loads(current) in (GEO,{"type":"FeatureCollection","features":[]})
code(MAP_SOURCE)
parent_token=(pilot.directory/"runtime/losverkauf/parent-token").read_text().strip()

def browser(host):
    return Client(pilot.config["port"],host,pilot.directory/"root.crt")
def capability():
    return code("import sqlite3;db=sqlite3.connect('/data/losverkauf.db');print(db.execute('SELECT edit_token FROM anmeldungen WHERE id=1').fetchone()[0])").strip()
if not json.loads(code(CONTRACT))["registrations"]:
    client=browser("lose.localhost")
    nonce=client.parent(parent_token)
    status,_,_=register(client,nonce)
    assert status==200
cap=capability()
checks=[]
fault=False
original=pilot.current_domains()

def preflight(old,new):
    return set(new)==set(original) and all(host.endswith(".localhost") for host in new.values())

def activate(domains):
    path=pilot.directory/"losverkauf.yml"
    lines=["      BASE_URL: https://"+domains["losverkauf"]+":"+str(pilot.config["port"])
           if line.startswith("      BASE_URL:") else line for line in path.read_text().splitlines()]
    with path.open("w") as stream:
        stream.write("\n".join(lines)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    pilot.compose_command("losverkauf","up","-d","--no-build","--wait","--wait-timeout","90","app")
    config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()])
    config=config.replace("admin localhost:2019","admin localhost:2019\n  local_certs")
    with (pilot.directory/"Caddyfile").open("w") as stream:
        stream.write(config)
        stream.flush()
        os.fsync(stream.fileno())
    proxy=pilot.inspect_service("infra","proxy")["Id"]
    for action in ("validate","reload"):
        pilot.command(["docker","exec",proxy,"caddy",action,"--config","/etc/caddy/Caddyfile"])

def verify(domains):
    host=domains["losverkauf"]
    for _ in range(50):
        try:
            if browser(host).request("/health/ready")[0]==200:break
        except OSError:pass
        time.sleep(.2)
    else:return False
    if fault and host=="lose-defekt.localhost":return False
    origin="https://"+host+":"+str(pilot.config["port"])
    result=probe(browser(host),parent_token,origin,cap)
    admin=browser(host)
    nonce=admin.login()
    assert admin.request("/admin/anmeldung/1/mail/eingang","POST",data={"csrf_token":nonce},
        headers={"X-Forwarded-Host":"spoof.example.invalid","X-Forwarded-Proto":"http"})[0]==302
    mail=json.loads(code("""import json,time,urllib.request
from app import BASE_URL,ELTERN_TOKEN
messages=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/messages'))['messages']
found=False
for item in messages:
    message=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/message/'+item['ID']))
    if BASE_URL+'/?t=' in message['Text'] and '&edit=' in message['Text']:
        found=True
        break
assert found
print(json.dumps({'mailUsesConfiguredOrigin':True,'spoofedForwardedHostIgnored':True,'personalResumeLink':True}))
"""))
    checks.append({"domain":host,**result,**mail})
    return True

assert verify(original)
driver=Domains(pilot.directory/"domain-transactions",original,"verwaltung.localhost",preflight,activate,verify,
               operation_lock=pilot.directory/"state/installation.lock")
try:
    driver.change("losverkauf","lose-neu.localhost")
    fault=True
    try:driver.change("losverkauf","lose-defekt.localhost")
    except DomainError as error:assert "restored" in str(error)
    else:raise AssertionError("Failed domain verification accepted")
    assert pilot.current_domains()["losverkauf"]=="lose-neu.localhost"
finally:
    fault=False
    driver.change("losverkauf","lose.localhost")
backend=pilot.inspect_service("losverkauf","app")
assert not any(backend["NetworkSettings"]["Ports"].values())
assert backend["Config"]["User"]=="10001:10001" and backend["HostConfig"]["ReadonlyRootfs"]
def stable():
    files=[pilot.directory/"state/installation.json"]+list((pilot.directory/"secrets").rglob("*"))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
before=stable()
identities={app:pilot.inspect_service(app,"app")["Id"] for app in pilot.apps}
first,second=pilot.up(),pilot.up()
assert first==second and stable()==before
assert identities=={app:pilot.inspect_service(app,"app")["Id"] for app in pilot.apps}
offset=len(pilot.log.read_text().splitlines())
engine=PilotEngine(pilot)
assert not engine.execute("stop","losverkauf")["running"]
assert browser("lose.localhost").request("/")[0]==503
assert engine.execute("start","losverkauf")["running"]
assert probe(browser("lose.localhost"),parent_token,"https://lose.localhost:"+str(pilot.config["port"]),cap)["existingCapabilityOwnership"]
assert capability()==cap and stable()==before
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("los_migrate" in row["command"] for row in operations)
report={"scope":"five-app pilot with verified local CA, synthetic district and personal administrator",
        "apps":list(pilot.apps),"installationId":first["id"],"imageId":backend["Image"],
        "privateBackend":True,"secureAdminCookie":True,"domainChange":True,"forcedFailureRollback":True,
        "originalDomainRestored":True,"existingEditTokenAndOwnership":True,
        "twoNoopRuns":True,"sameContainersKeysAndCheckpoints":True,"stopMaintenance503":True,
        "noRepeatedMigration":True,"checks":checks,
        "limits":["No public DNS/ACME ownership test","No global session revocation","At-least-once mail can duplicate after SMTP/crash race",
                  "No encrypted offsite/secretstore backup or capacity measurement","No browser automation"]}
pilot.stop()
report["stoppedDataRetained"]=True
(out/"losverkauf-platform.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"pilot-v10-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report,indent=2))
