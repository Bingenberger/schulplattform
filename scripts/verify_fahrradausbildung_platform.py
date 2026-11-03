"""Seven-app local TLS, decoded station PDF QR, existing event/token preservation and rollback."""
import hashlib,json,os,secrets,sys,time,uuid
from pathlib import Path
from fahrrad_fixture import Browser,SEED
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.proxy import caddyfile
from schulplattform.domains import Domains,DomainError
from schulplattform.pilot_engine import PilotEngine
pilot=Pilot(ROOT/".work/pilot-v14");private=pilot.directory/"rad-fixtures";private.mkdir(mode=0o700,exist_ok=True)
def code(source):
    return pilot.command([str(pilot.compose),"-p",pilot.project+"-fahrradausbildung","-f",
        str(ROOT/".work/apps/fahrradausbildung/docker-compose.yml"),"-f",str(pilot.directory/"fahrradausbildung.yml"),
        "exec","-T","app","python","-"],input=source)
def browser(host):return Browser(pilot.config["port"],host,pilot.directory/"root.crt")
fixturefile=private/"fixture.json"
if fixturefile.exists():fixtures=json.loads(fixturefile.read_text())
else:
    fixtures=json.loads(code(SEED));fixturefile.write_text(json.dumps(fixtures));fixturefile.chmod(0o600)
first,second=fixtures
tokenfile=private/"station-token";tokenfile.write_text(first["token"]);tokenfile.chmod(0o444)
original=pilot.current_domains();checks=[];fault=False
eventfile=private/"event-id"
if not eventfile.exists():eventfile.write_text(str(uuid.uuid4()))
eventid=eventfile.read_text()
event={"event_id":eventid,"typ":"durchgang","startnummer":7,"nutzlast":{"durchgang_nr":1,"fehlende_items":[first["item"]]},
    "erfasst_am":"2026-11-03T12:00:00Z"}
def decode(pdf,origin):
    source="""import json,subprocess,sys
from pathlib import Path
from PIL import Image
from pyzbar.pyzbar import decode
Path('/tmp/qr.pdf').write_bytes(sys.stdin.buffer.read())
subprocess.run(['pdftoppm','-scale-to','1600','-png','/tmp/qr.pdf','/tmp/page'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
urls=[code.data.decode() for p in Path('/tmp').glob('page-*.png') for code in decode(Image.open(p))]
expected=sys.argv[1]+'/p/'+Path('/run/secrets/station-token').read_text()
assert urls==[expected]
print(json.dumps({'decodedPdfQrMatchesRuntimeOriginAndExistingToken':True}))
"""
    command=["docker","run","--rm","--read-only","--network","none","--cap-drop","ALL","--security-opt","no-new-privileges:true",
        "--memory","512m","--cpus","1","--pids-limit","64","--tmpfs","/tmp:size=64m,mode=1777",
        "-v",str(tokenfile)+":/run/secrets/station-token:ro","-i","fahrradausbildung-browser-tests:0.1.0-dev","python","-c",source,origin]
    import subprocess
    result=subprocess.run(command,input=pdf,capture_output=True,timeout=90)
    assert result.returncode==0,"QR decoding failed"
    return json.loads(result.stdout)
def verify(domains):
    host=domains["fahrradausbildung"]
    if fault and host=="rad-defekt.localhost":return False
    a,b,anonymous=browser(host),browser(host),browser(host)
    for _ in range(50):
        try:anonymous.call("GET","/health/ready");break
        except OSError:time.sleep(.2)
    origin="https://"+host+":"+str(pilot.config["port"])
    a.login(first["email"]);b.login(second["email"])
    assert a.cookie_options["fp_sitzung"]["secure"]
    a.page("/verwaltung/")
    b.call("GET","/verwaltung/strecken/"+str(first["track"]),expected=404)
    anonymous.call("GET","/verwaltung/",expected=303)
    a.form("/verwaltung/strecken/neu",{"name":"csrf-denied"},expected=403)
    cfg=anonymous.call("GET","/api/p/"+first["token"]+"/config")
    assert cfg["lauf_id"]==first["run"]
    assert anonymous.call("POST","/api/p/"+first["token"]+"/events",{"events":[event]})["akzeptiert"]==[eventid]
    assert anonymous.call("GET","/api/p/"+first["token"]+"/status")["offen"]==0
    assert anonymous.call("GET","/p/"+first["token"]+"/manifest.webmanifest")["start_url"]=="/p/"+first["token"]
    assert "manifest.webmanifest" in anonymous.page("/p/"+first["token"])
    pdf=a.call("GET","/verwaltung/laeufe/"+str(first["run"])+"/postenblaetter.pdf",
        headers={"X-Forwarded-Host":"forged.invalid","X-Forwarded-Proto":"http"})
    qr=decode(pdf,origin)
    a.form("/abmelden",{"csrf":a.csrf()});b.form("/abmelden",{"csrf":b.csrf()})
    checks.append({"domain":host,"secureCookie":True,"existingRunAndEventId":True,"publicStationAndPwa":True,
        "anonymousAdminCrossSchoolCsrfDenied":True,**qr})
    return True
def activate(domains):
    path=pilot.directory/"fahrradausbildung.yml"
    lines=["      FP_OEFFENTLICHE_URL: https://"+domains["fahrradausbildung"]+":"+str(pilot.config["port"])
        if line.startswith("      FP_OEFFENTLICHE_URL:") else line for line in path.read_text().splitlines()]
    with path.open("w") as stream:stream.write("\n".join(lines)+"\n");stream.flush();os.fsync(stream.fileno())
    pilot.compose_command("fahrradausbildung","up","-d","--no-build","--wait","--wait-timeout","90","app")
    config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()]).replace("admin localhost:2019","admin localhost:2019\n local_certs")
    with (pilot.directory/"Caddyfile").open("w") as stream:stream.write(config);stream.flush();os.fsync(stream.fileno())
    proxy=pilot.inspect_service("infra","proxy")["Id"]
    for action in ("validate","reload"):pilot.command(["docker","exec",proxy,"caddy",action,"--config","/etc/caddy/Caddyfile"])
assert verify(original)
driver=Domains(pilot.directory/"domain-transactions",original,"verwaltung.localhost",
    lambda old,new:set(new)==set(original) and all(h.endswith(".localhost") for h in new.values()),
    activate,verify,operation_lock=pilot.directory/"state/installation.lock")
try:
    driver.change("fahrradausbildung","rad-neu.localhost")
    fault=True
    try:driver.change("fahrradausbildung","rad-defekt.localhost")
    except DomainError as error:assert "restored" in str(error)
    else:raise AssertionError("Invalid domain accepted")
    assert pilot.current_domains()["fahrradausbildung"]=="rad-neu.localhost"
finally:
    fault=False;driver.change("fahrradausbildung","rad.localhost")
def stable():
    paths=[pilot.directory/"state/installation.json"]+list((pilot.directory/"secrets").rglob("*"))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
before=stable();containers={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
one,two=pilot.up(),pilot.up()
assert one==two and stable()==before
assert containers=={a:pilot.inspect_service(a,"app")["Id"] for a in pilot.apps}
offset=len(pilot.log.read_text().splitlines())
engine=PilotEngine(pilot);assert not engine.execute("stop","fahrradausbildung")["running"]
browser("rad.localhost").call("GET","/p/"+first["token"],expected=503)
assert engine.execute("start","fahrradausbildung")["running"]
assert verify(original) and stable()==before
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("app.migrate" in row["command"] for row in operations)
assert code("from app.db import engine;from sqlalchemy import text\nwith engine().connect() as c:print(c.execute(text('SELECT count(*) FROM ereignis')).scalar_one())").strip()=="1"
backend=pilot.inspect_service("fahrradausbildung","app")
assert not any(backend["NetworkSettings"]["Ports"].values())
assert backend["Config"]["User"]=="10001:10001" and backend["HostConfig"]["ReadonlyRootfs"]
report={"scope":"seven-app local pilot, synthetic school data, verified local CA","apps":list(pilot.apps),
    "installationId":one["id"],"port":pilot.config["port"],"imageId":backend["Image"],
    "privateRootlessReadOnlyBackend":True,"domainChange":True,"forcedFailureRollback":True,"originalDomainRestored":True,
    "twoNoopRuns":True,"containersKeysCheckpointsUnchanged":True,"stopMaintenance503":True,"noRepeatedMigration":True,
    "oneIdempotentEventAfterAllTransitions":True,"checks":checks,
    "limits":["No public DNS/ACME validation","No production Ubuntu acceptance","No automatic transfer of offline browser IndexedDB between origins","No capacity measurement"]}
pilot.stop();report["stoppedDataRetained"]=True
(ROOT/"docs/implementation/evidence/fahrrad-platform.json").write_text(json.dumps(report,indent=2)+"\n")
(ROOT/"docs/implementation/evidence/pilot-v14-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report))
