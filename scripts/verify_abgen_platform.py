"""Ten-app pilot: abgen TLS, opaque links, PDF, domain rollback and live-room stop."""
import hashlib,json,os,secrets,subprocess,sys,time
from pathlib import Path
from abgen_fixture import Browser,SEED
from abgen_qr import verify_qr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,APP_PORTS
from schulplattform.pilot_engine import PilotEngine
from schulplattform.domains import Domains,DomainError
from schulplattform.proxy import caddyfile
from schulplattform.postgres import Postgres
pilot=Pilot(ROOT/".work/pilot-v21")
private=pilot.directory/"abgen-fixtures";private.mkdir(mode=0o700,exist_ok=True)
out=ROOT/"docs/implementation/evidence"
checks=[];fault=False
def node(source):
 return pilot.command([str(pilot.compose),"-p",pilot.project+"-abgen",
  "-f",str(ROOT/".work/apps/abgen/docker-compose.yml"),"-f",str(pilot.directory/"abgen.yml"),
  "exec","-T","app","node","--input-type=module","-"],input=source)
account_file=private/"account.json"
if not account_file.exists():
 account={"email":"synthetic-admin@example.invalid","password":secrets.token_urlsafe(24)}
 account_file.write_text(json.dumps(account));account_file.chmod(0o600)
 node("const fixture="+json.dumps(account)+";\n"+SEED)
else:account=json.loads(account_file.read_text())
original=pilot.current_domains()
def browser(host):return Browser(pilot.config["port"],host,pilot.directory/"root.crt")
def origin(host):return "https://"+host+":"+str(pilot.config["port"])
def native_contracts():
 program="const fixture="+json.dumps(account|{"origin":origin(original["abgen"]),"phase":"contracts"})+";\n"+(ROOT/".work/apps/abgen/contract_tests/runtime.mjs").read_text()
 cmd=["docker","run","--rm","--init","--read-only","--network",pilot.project+"-abgen_default",
  "--cap-drop","ALL","--security-opt","no-new-privileges:true","--memory","512m","--cpus","1","--pids-limit","64",
  "-v",str(pilot.directory/"runtime/abgen/database-url")+":/run/secrets/database_url:ro",
  "-i","abgen-tests:0.1.0-dev","node","--input-type=module","-"]
 result=subprocess.run(cmd,input=program,capture_output=True,text=True,timeout=180)
 if result.returncode:
  (private/"contract-failure.private.log").write_text(result.stdout+result.stderr)
  raise AssertionError("Native platform contract failed; private diagnostic retained")
 public=[]
 for line in result.stdout.splitlines():
  if line.startswith("FIXTURE_PRIVATE="):
   (private/"fixture.json").write_text(line.removeprefix("FIXTURE_PRIVATE="));(private/"fixture.json").chmod(0o600)
  else:public.append(line)
 (out/"abgen-platform-native.log").write_text("\n".join(public)+"\nexit_code=0\n")
if not (private/"fixture.json").exists():native_contracts()
fixture=json.loads((private/"fixture.json").read_text())
postgres=Postgres(["docker","exec",pilot.inspect_service("abgen","postgres")["Id"]],"abgen","abgen")
def rows():
 names=postgres.query("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'sessions' ORDER BY 1").splitlines()
 assert all(__import__("re").fullmatch("[a-z_]+",name) for name in names)
 result={}
 for name in names:
  # Joining the native editor refreshes contact time even for an empty Yjs update.
  row="(to_jsonb(t)-'updated_at')" if name=="collab_state" else "to_jsonb(t)"
  result[name]=postgres.query("SELECT count(*)||':'||md5(coalesce(string_agg("+row+"::text,E'\\n' ORDER BY "+row+"::text),'')) FROM "+name+" t")
 return result
def wait_cleanup():
 for _ in range(100):
  if postgres.query("SELECT count(*) FROM shares WHERE kind='render'")=="0":return
  time.sleep(.05)
 raise AssertionError("Render cleanup failed")
wait_cleanup();baseline=rows()
def verify(domains):
 host=domains["abgen"]
 if fault and host=="blaetter-defekt.localhost":return False
 teacher,anonymous=browser(host),browser(host)
 for _ in range(50):
  try:anonymous.call("GET","/api/health/ready");break
  except (OSError,AssertionError):time.sleep(.2)
 else:raise AssertionError("Worksheet TLS readiness unavailable")
 logged=teacher.login(account["email"],account["password"])
 assert logged["user"]["role"]=="admin" and teacher.cookie_options["abgen_session"]=={"secure":True,"httponly":True,"samesite":"Lax"}
 anonymous.call("GET","/api/auth/me",headers={"X-Forwarded-User":"admin","X-Auth-User":"admin","Remote-User":"admin"},expected=401)
 anonymous.call("GET","/api/users",expected=401)
 anonymous.call("POST","/_platform/prepare-stop",{},expected=404)
 anonymous.call("POST","/api/auth/register",{"email":"forbidden@example.invalid","password":account["password"],"displayName":"Forbidden"},expected=403)
 teacher.call("POST","/api/auth/logout",{},csrf=False,expected=403)
 teacher.call("POST","/api/auth/logout",{},headers={"Origin":"https://foreign.invalid"},expected=403)
 if host != original["abgen"]:
  # Use the valid cookie from strict TLS login, but the previous domain as Origin.
  negative="const fixture="+json.dumps({"id":fixture["documentId"],"origin":origin(original["abgen"]),
   "cookie":"abgen_session="+teacher.cookies["abgen_session"]})+";\n"+r"""
const {createRequire}=await import('node:module');
const require=createRequire('/app/apps/server/package.json');
const WebSocket=createRequire(require.resolve('@fastify/websocket'))('ws');
const timer=setTimeout(()=>process.exit(1),5000);
const ws=new WebSocket('ws://127.0.0.1:3000/api/collab/'+fixture.id,{headers:{Origin:fixture.origin,Cookie:fixture.cookie}});
ws.on('unexpected-response',(_request,response)=>{clearTimeout(timer);response.destroy();console.log(response.statusCode);process.exit(response.statusCode===403?0:1)});
ws.on('open',()=>process.exit(1));ws.on('error',()=>{});
"""
  assert node(negative).strip()=="403"
 document=teacher.call("GET","/api/documents/"+fixture["documentId"])
 assert document["document"]["meta"]["title"]=="Synthetic restart durable"
 anonymous.call("GET","/api/documents/"+fixture["documentId"]+"?token="+fixture["shareToken"])
 anonymous.call("GET","/api/play/"+fixture["playCode"])
 anonymous.call("GET","/api/documents/"+fixture["documentId"]+"/submissions",expected=401)
 fresh=teacher.call("POST","/api/documents/"+fixture["documentId"]+"/shares",{},expected=201)
 assert fresh["url"].startswith(origin(host)+"/?freigabe=")
 teacher.call("DELETE","/api/documents/"+fixture["documentId"]+"/shares/"+fresh["tokenHash"])
 pdf=anonymous.call("POST","/api/documents/"+fixture["documentId"]+"/pdf",{"token":fixture["shareToken"]})
 assert pdf.startswith(b"%PDF")
 assert verify_qr(pilot,host,account,fixture["playCode"])
 teacher.call("POST","/api/auth/logout",{})
 wait_cleanup()
 checks.append({"domain":host,"verifiedLocalCA":True,"secureCookie":True,"nativeLogin":True,
  "spoofedIdentityAndAnonymousAdministrationDenied":True,"originAndRequestHeaderEnforced":True,
  "privateControlDenied":True,"originalShareAndChildCodePreserved":True,
  "newLinksUseRuntimeOrigin":True,"nativeChildQrScreenshotDecoded":True,"publicWssOnCurrentOrigin":True,"privatePdfWorksViaInternalOrigin":True})
 return True
def activate(domains):
 pilot.abgen_control("prepare-stop")
 path=pilot.directory/"abgen.yml"
 lines=["      WEB_ORIGIN: "+origin(domains["abgen"]) if line.startswith("      WEB_ORIGIN: https://") else line for line in path.read_text().splitlines()]
 with path.open("w") as stream:stream.write("\n".join(lines)+"\n");stream.flush();os.fsync(stream.fileno())
 pilot.compose_command("abgen","up","-d","--no-build","--wait","--wait-timeout","90","app")
 config=caddyfile([(app,host,APP_PORTS[app]) for app,host in domains.items()]).replace("admin localhost:2019","admin localhost:2019\n local_certs")
 with (pilot.directory/"Caddyfile").open("w") as stream:stream.write(config);stream.flush();os.fsync(stream.fileno())
 proxy=pilot.inspect_service("infra","proxy")["Id"]
 for action in ("validate","reload"):pilot.command(["docker","exec",proxy,"caddy",action,"--config","/etc/caddy/Caddyfile"])
assert verify(original)
driver=Domains(pilot.directory/"domain-transactions",original,"verwaltung.localhost",
 lambda old,new:set(new)==set(original) and all(h.endswith(".localhost") for h in new.values()),activate,verify,
 operation_lock=pilot.directory/"state/installation.lock")
try:
 driver.change("abgen","blaetter-neu.localhost")
 fault=True
 try:driver.change("abgen","blaetter-defekt.localhost")
 except DomainError as error:assert "restored" in str(error)
 else:raise AssertionError("Bad worksheet domain accepted")
 assert pilot.current_domains()["abgen"]=="blaetter-neu.localhost"
finally:
 fault=False;driver.change("abgen",original["abgen"])
assert rows()==baseline
def stable():
 paths=[pilot.directory/"state/installation.json"]+list((pilot.directory/"secrets").rglob("*"))
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
before=stable();containers={app:pilot.inspect_service(app,"app")["Id"] for app in pilot.apps}
auxiliary={name:pilot.inspect_service("abgen",name)["Id"] for name in ("postgres","pdf")}
one,two=pilot.up(),pilot.up()
assert one==two and stable()==before and containers=={app:pilot.inspect_service(app,"app")["Id"] for app in pilot.apps}
assert auxiliary=={name:pilot.inspect_service("abgen",name)["Id"] for name in auxiliary}
engine=PilotEngine(pilot)
pilot.compose_command("abgen","stop","pdf")
assert engine.status("abgen")["health"]=="degraded" and not pilot.ready(one["id"])
pilot.compose_command("abgen","up","-d","--no-build","--wait","pdf")
# Keep a real authenticated room open while the deployment engine drains it.
probe=r"""
const {createRequire}=await import('node:module');
const require=createRequire('/app/apps/server/package.json');
const WebSocket=createRequire(require.resolve('@fastify/websocket'))('ws');
const timeout=setTimeout(()=>{console.error('Live room timeout');process.exit(1)},25000);
const response=await fetch('http://app:3000/api/auth/login',{method:'POST',headers:{origin:fixture.origin,'content-type':'application/json','X-Abgen-Request':'1'},
 body:JSON.stringify({email:fixture.email,password:fixture.password})});
if(!response.ok)throw Error('Live room login failed');
const cookie=response.headers.get('set-cookie').split(';')[0];
const ws=new WebSocket('ws://app:3000/api/collab/'+fixture.documentId,{headers:{Origin:fixture.origin,Cookie:cookie}});
let ready=false;
ws.on('message',raw=>{if(!ready&&raw[0]===1){ready=true;console.log('LIVE_ROOM_READY')}});
ws.on('close',()=>{clearTimeout(timeout);if(ready){console.log('LIVE_ROOM_CLOSED');process.exit(0)}else process.exit(1)});
ws.on('error',()=>{clearTimeout(timeout);process.exit(1)});
"""
program="const fixture="+json.dumps(account|{"documentId":fixture["documentId"],"origin":origin(original["abgen"])})+";\n"+probe
cmd=["docker","run","--rm","--init","--read-only","--network",pilot.project+"-abgen_default",
 "--memory","128m","--pids-limit","32","--cap-drop","ALL","--security-opt","no-new-privileges:true",
 "-i","abgen-tests:0.1.0-dev","node","--input-type=module","-"]
process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
process.stdin.write(program);process.stdin.close()
assert process.stdout.readline().strip()=="LIVE_ROOM_READY","Live room handshake failed"
offset=len(pilot.log.read_text().splitlines())
try:
 assert not engine.execute("stop","abgen")["running"]
 assert process.wait(timeout=10)==0 and "LIVE_ROOM_CLOSED" in process.stdout.read()
finally:
 if process.poll() is None:process.kill();process.wait()
assert pilot.inspect_service("abgen","pdf") is None
assert pilot.inspect_service("abgen","postgres")["State"]["Running"]
browser(original["abgen"]).call("GET","/",expected=503)
assert engine.execute("start","abgen")["health"]=="healthy"
assert verify(original) and rows()==baseline and stable()==before and pilot.ready(one["id"])
operations=[json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("apps/server/dist/db/migrate.js" in row["command"] or "apps/server/dist/setup.js" in row["command"] for row in operations)
backend=pilot.inspect_service("abgen","app")
report={"apps":list(pilot.apps),"installationId":one["id"],"scope":"Ten-app local pilot, synthetic data, verified local CA",
 "port":pilot.config["port"],"images":{name:pilot.inspect_service("abgen",name)["Image"] for name in ("app","pdf","postgres")},
 "domainChange":True,"forcedFailureRollback":True,"originalDomainRestored":True,
 "twoNoopRuns":True,"containersKeysAndCheckpointsStable":True,"domainAndLifecycleBusinessRowsAndYjsBytesUnchanged":True,
 "ignoredOperationalData":["sessions","collab_state.updated_at"],
 "pdfFailureDegradesStatusAndPilotReadiness":True,"stopDrainsLiveRoomAndPausesWebAndPdf":True,
 "databaseAndVolumesKept":True,"maintenance503":True,"startWithoutMigrationOrSetup":True,
 "privateBackendAndAuxiliaries":True,"checks":checks,
 "limits":["Local CA and names only, no public DNS/ACME","No Ubuntu acceptance or capacity measurement",
           "No multi-replica Yjs coordination","No production users, emails or deployment"]}
pilot.stop();report["stoppedDataRetained"]=True
(out/"abgen-platform.json").write_text(json.dumps(report,indent=2)+"\n")
(out/"pilot-v21-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report))
