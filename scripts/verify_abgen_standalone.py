"""Standalone acceptance: real PostgreSQL 18, hidden setup, Yjs and Chromium.
No production data, DNS, SMTP upstream, host package install or platform override.
"""
import json,os,pty,secrets,select,socket,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/".work/apps/abgen"
directory=ROOT/".work"/("sp-abgen-standalone-"+secrets.token_hex(5))
directory.mkdir(mode=0o700)
project=directory.name
with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
origin="http://127.0.0.1:"+str(port)
subprocess.run([str(ROOT/".venv/bin/python"),str(APP/"prepare_secrets.py")],cwd=directory,capture_output=True,check=True)
env=os.environ|{"ABGEN_SECRETS_DIR":str(directory/".private"),"WEB_PORT":str(port),"WEB_ORIGIN":origin}
base=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(APP/"docker-compose.yml")]
checks=[];operations=[]
account={"email":"synthetic-admin@example.invalid","name":"Synthetic Admin","password":secrets.token_urlsafe(24)}
(directory/"account.json").write_text(json.dumps(account));(directory/"account.json").chmod(0o600)
def note(label):checks.append(label);print("PASS "+label,flush=True)
def run(cmd,expected=0,**kwargs):
 r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180,**kwargs)
 operations.append({"command":cmd,"exitCode":r.returncode})
 if r.returncode!=expected:
  (directory/"failure.private.log").write_text(r.stdout+r.stderr)
  raise AssertionError("Fixture command failed; private diagnostic retained")
 return r.stdout
def http(path,status=200,method="GET",body=None):
 req=urllib.request.Request(origin+path,method=method,data=json.dumps(body).encode() if body is not None else None,
  headers={"Origin":origin,"Content-Type":"application/json","X-Abgen-Request":"1"})
 try:r=urllib.request.urlopen(req,timeout=4)
 except urllib.error.HTTPError as error:r=error
 assert r.code==status,"Unexpected HTTP acceptance status"
 return json.loads(r.read())
def wait(path="/api/health/ready",status=200):
 for _ in range(100):
  try:return http(path,status)
  except (OSError,AssertionError):time.sleep(.2)
 raise AssertionError("Readiness wait failed")
def setup():
 master,slave=pty.openpty()
 def terminal():os.setsid();__import__("fcntl").ioctl(0,__import__("termios").TIOCSCTTY,0)
 p=subprocess.Popen(["docker","exec","-it",project+"-app-1","node","apps/server/dist/setup.js",account["email"],account["name"]],
  stdin=slave,stdout=slave,stderr=slave,preexec_fn=terminal)
 os.close(slave);output=b"";sent=0;deadline=time.monotonic()+45
 try:
  while time.monotonic()<deadline:
   if select.select([master],[],[],.2)[0]:
    try:chunk=os.read(master,4096)
    except OSError:break
    if not chunk:break
    output+=chunk
    if sent<2 and [b"mindestens 12 Zeichen): ",b"Wiederholen: "][sent] in output:
     os.write(master,account["password"].encode()+b"\n");sent+=1
   if p.poll() is not None:break
  if p.poll() is None:p.kill()
  p.wait();assert account["password"].encode() not in output,"Password echoed"
  (directory/("setup-"+str(len(list(directory.glob("setup-*.private.log"))))+".private.log")).write_bytes(output)
  return p.returncode,sent
 finally:
  if p.poll() is None:p.kill();p.wait()
  os.close(master)
def query(sql,values=None):
 program="const {Pool}=require('./apps/server/node_modules/pg');const fs=require('fs');const p=new Pool({connectionString:fs.readFileSync('/run/secrets/database_url','utf8')});p.query("+json.dumps(sql)+","+json.dumps(values or [])+").then(r=>console.log(JSON.stringify(r.rows))).finally(()=>p.end());"
 return json.loads(run(base+["exec","-T","app","node","-"],input=program))
def contracts(phase):
 program="const fixture="+json.dumps(account|{"origin":origin,"phase":phase})+";\n"+(APP/"contract_tests/runtime.mjs").read_text()
 command=["docker","run","--rm","--init","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
  "--memory","512m","--cpus","1","--pids-limit","64","--network",project+"_default",
  "-v",str(directory/".private/database-url")+":/run/secrets/database_url:ro","-i","abgen-tests:0.1.0-dev","node","--input-type=module","-"]
 output=run(command,input=program)
 public=[]
 for line in output.splitlines():
  if line.startswith("FIXTURE_PRIVATE="):
   (directory/"contract-private.json").write_text(line.removeprefix("FIXTURE_PRIVATE="))
   (directory/"contract-private.json").chmod(0o600)
  else:public.append(line)
 output="\n".join(public)+"\n"
 (ROOT/("docs/implementation/evidence/abgen-"+phase+".log")).write_text(output+"exit_code=0\n")
 print(output,flush=True)
def local(path):
 program="fetch('http://127.0.0.1:3000"+path+"',{method:'POST',headers:{'X-Abgen-Request':'1'}}).then(async r=>{if(!r.ok)process.exitCode=1;console.log(await r.text())});"
 return json.loads(run(base+["exec","-T","app","node","-e",program]))
try:
 run(base+["up","-d","--no-build","postgres","app","pdf"]);wait("/api/health/live");wait(status=503)
 run(base+["exec","-T","app","node","apps/server/dist/db/migrate.js"])
 run(base+["exec","-T","app","node","apps/server/dist/db/migrate.js"]);wait()
 assert query("SELECT count(*)::int AS count FROM users")[0]["count"]==0
 assert http("/api/auth/register",403,"POST",{"email":account["email"],"displayName":account["name"],"password":account["password"]})
 run(base+["exec","-T","app","node","apps/server/dist/setup.js",account["email"],account["name"]],expected=1)
 assert setup()==(0,2);assert setup()[0]!=0
 note("explicit idempotent migration; no default accounts; hidden personal terminal setup; public/repeat/headless setup refused")
 contracts("contracts")
 run(["docker","kill","--signal","KILL",project+"-app-1"]);run(base+["start","app"]);wait()
 contracts("restart")
 note("durable collaborative documents survive abrupt API termination")
 before=json.loads(run(["docker","inspect",project+"-app-1"]))[0]
 run(base+["stop","postgres"]);wait(status=503);http("/api/health/live")
 after=json.loads(run(["docker","inspect",project+"-app-1"]))[0]
 assert after["State"]["Running"] and before["RestartCount"]==after["RestartCount"]
 run(base+["start","postgres"]);wait()
 note("database outage gives readiness 503 while liveness and process remain available; recovery without bootstrap")
 run(base+["stop","pdf"]);assert http("/api/health")["pdf"]=="nicht erreichbar";http("/api/health/ready")
 run(base+["start","pdf"])
 for _ in range(100):
  if http("/api/health")["pdf"]=="ok":break
  time.sleep(.2)
 else:raise AssertionError("PDF recovery failed")
 note("PDF outage is visible without marking database-only API readiness failed")
 hash_=query("SELECT hash FROM drizzle.__drizzle_migrations ORDER BY id LIMIT 1")[0]["hash"]
 query("UPDATE drizzle.__drizzle_migrations SET hash='synthetic-drift' WHERE hash=$1",[hash_]);wait(status=503)
 run(base+["exec","-T","app","node","apps/server/dist/db/migrate.js"],expected=1)
 query("UPDATE drizzle.__drizzle_migrations SET hash=$1 WHERE hash='synthetic-drift'",[hash_]);wait()
 note("migration drift blocks business readiness and explicit migration without overwriting history")
 drained=local("/_platform/prepare-stop");assert drained=={"pendingUpdates":0,"pendingBytes":0,"draining":True}
 note("private local stop drains collaboration before services stop")
 info=json.loads(run(["docker","inspect",project+"-app-1",project+"-pdf-1",project+"-postgres-1"]))
 for item in info[:2]:
  assert item["Config"]["User"]=="10001:10001" and item["HostConfig"]["ReadonlyRootfs"]
 assert not info[1]["HostConfig"]["PortBindings"] and not info[2]["HostConfig"]["PortBindings"]
 assert all(mount["Destination"]!="/run/secrets/database_url" for mount in info[1]["Mounts"])
 volume=next(m["Name"] for m in info[0]["Mounts"] if m["Destination"]=="/app/data/assets")
 note("rootless read-only app/PDF; PDF has no database credential; only loopback app port is published")
 metadata={"project":project,"directory":str(directory),"port":port,"env":{k:env[k] for k in ["ABGEN_SECRETS_DIR","WEB_PORT","WEB_ORIGIN"]},"assetVolume":volume}
 (directory/"meta.json").write_text(json.dumps(metadata,indent=2))
 (ROOT/".work/abgen-latest-fixture").write_text(str(directory))
finally:
 run(base+["stop"])
report={"project":project,"checks":checks,"operations":operations,"stopped":True,"volumesPreserved":True,
 "images":json.loads((ROOT/"docs/implementation/evidence/abgen-images.json").read_text())}
(ROOT/"docs/implementation/evidence/abgen-standalone.json").write_text(json.dumps(report,indent=2)+"\n")
print("Standalone acceptance passed; isolated fixture stopped; private credentials and volumes retained")
