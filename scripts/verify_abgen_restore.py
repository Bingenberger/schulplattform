"""Consistent PostgreSQL 18 + native assets into an empty standalone environment."""
import json,os,secrets,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.postgres import Postgres
from schulplattform.snapshot import checksum
APP=ROOT/".work/apps/abgen"
private=Path((ROOT/".work/abgen-latest-fixture").read_text())
fixture=json.loads((private/"meta.json").read_text())
assert fixture["project"].startswith("sp-abgen-standalone-"),"Restore requires accepted isolated fixture"
project="sp-abgen-restore-"+secrets.token_hex(5)
directory=private/project;directory.mkdir(mode=0o700)
env=os.environ|fixture["env"]
source=[str(ROOT/".work/docker-compose"),"-p",fixture["project"],"-f",str(APP/"docker-compose.yml")]
operations=[];checks=[]
def run(command,**kwargs):
 r=subprocess.run(command,env=env,capture_output=True,timeout=180,**kwargs)
 operations.append({"command":command,"exitCode":r.returncode})
 if r.returncode:
  (directory/"failure.private.log").write_bytes(r.stdout+r.stderr)
  raise AssertionError("Restore command failed; private diagnostic retained")
 return r.stdout
def note(label):checks.append(label);print("PASS "+label,flush=True)
def wait_pg(command):
 for _ in range(100):
  info=json.loads(run(["docker","inspect",command]))[0]
  if info["State"].get("Health",{}).get("Status")=="healthy":return
  time.sleep(.2)
 raise AssertionError("Postgres readiness failed")
PYTHON="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
def helper(command,volume,mode,payload=None):
 return run(["docker","run","--rm","--read-only","--network","none","--user","10001:10001","--cap-drop","ALL",
  "--security-opt","no-new-privileges:true","--memory","512m","--pids-limit","64","--tmpfs","/tmp:size=64m,mode=1777",
  "-e","PYTHONPATH=/helper","-e","PYTHONDONTWRITEBYTECODE=1","-v",str(ROOT/"schulplattform")+":/helper/schulplattform:ro",
  "-v",volume+":/data:"+mode,"-i",PYTHON,"python","-c",command],input=payload)
def inventory(pg):
 names=pg.query("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('public','drizzle') ORDER BY 1").splitlines()
 assert all(__import__("re").fullmatch(r"(public|drizzle)\.[a-z_]+",name) for name in names)
 return {name:pg.query("SELECT count(*)||':'||md5(coalesce(string_agg(row_to_json(t)::text,E'\\n' ORDER BY row_to_json(t)::text),'')) FROM "+name+" t") for name in names}
assert not run(["docker","ps","-q","--filter","label=com.docker.compose.project="+fixture["project"]]).strip(),"Source must be stopped before coordinated snapshot"
run(source+["start","postgres"]);wait_pg(fixture["project"]+"-postgres-1")
pg=Postgres(["docker","exec",fixture["project"]+"-postgres-1"],"abgen","abgen")
before=inventory(pg)
metadata=pg.snapshot(directory/"database.dump")
archive=helper("from schulplattform.snapshot import create\nfrom pathlib import Path\nimport sys\np=Path('/data');create(p,sys.stdout.buffer,directories=[x.name for x in p.iterdir() if x.is_dir()],files=[x.name for x in p.iterdir() if x.is_file()])",fixture["assetVolume"],"ro")
(directory/"assets.tar").write_bytes(archive);(directory/"assets.tar").chmod(0o600)
digest=checksum(directory/"assets.tar")
run(source+["stop","postgres"])
with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
env|={"WEB_PORT":str(port),"WEB_ORIGIN":"http://127.0.0.1:"+str(port)}
target=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(APP/"docker-compose.yml")]
try:
 run(target+["up","-d","--no-build","postgres"]);wait_pg(project+"-postgres-1")
 destination=Postgres(["docker","exec","-i",project+"-postgres-1"],"abgen","abgen")
 destination.restore_into_empty(directory/"database.dump",metadata,directory)
 try:destination.restore_into_empty(directory/"database.dump",metadata,directory)
 except ValueError as error:assert "not empty" in str(error)
 else:raise AssertionError("Nonempty restore accepted")
 assert inventory(destination)==before
 assert destination.query("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")=="0"
 assert destination.query("SELECT count(*) FROM pg_roles WHERE rolname='abgen' AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole")=="1"
 note("all business rows, IDs, roles, schema history, shares, play codes, sessions and Yjs snapshots match empty PostgreSQL restore")
 run(target+["create","app"])
 info=json.loads(run(["docker","inspect",project+"-app-1"]))[0]
 volume=next(m["Name"] for m in info["Mounts"] if m["Destination"]=="/app/data/assets")
 helper("from schulplattform.snapshot import restore\nfrom pathlib import Path\nimport sys\np=Path('/tmp/archive.tar');p.write_bytes(sys.stdin.buffer.read());restore(p,Path('/data'),'"+digest+"')",volume,"rw",archive)
 verify=helper("from pathlib import Path\nimport hashlib,json\nprint(json.dumps({str(p.relative_to('/data')):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'uid':p.stat().st_uid} for p in Path('/data').rglob('*') if p.is_file()}))",volume,"ro")
 original=helper("from pathlib import Path\nimport hashlib,json\nprint(json.dumps({str(p.relative_to('/data')):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'uid':p.stat().st_uid} for p in Path('/data').rglob('*') if p.is_file()}))",fixture["assetVolume"],"ro")
 assert json.loads(verify)==json.loads(original)
 assert all(item["uid"]==10001 for item in json.loads(verify).values())
 note("native asset bytes and UID 10001 restored into separate empty volume")
 run(target+["up","-d","--no-build","app","pdf"])
 account=json.loads((private/"account.json").read_text())
 saved=json.loads((private/"contract-private.json").read_text())
 program="const fixture="+json.dumps(account|{"origin":env["WEB_ORIGIN"],"phase":"restore","saved":saved})+";\n"+(APP/"contract_tests/runtime.mjs").read_text()
 for _ in range(100):
  response=subprocess.run(["docker","exec",project+"-app-1","node","-e","fetch('http://127.0.0.1:3000/api/health/ready').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"],capture_output=True,timeout=10)
  if response.returncode==0:break
  time.sleep(.2)
 else:raise AssertionError("Restored app readiness failed")
 output=run(["docker","run","--rm","--init","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
  "--memory","512m","--cpus","1","--pids-limit","64","--network",project+"_default",
  "-v",fixture["env"]["ABGEN_SECRETS_DIR"]+"/database-url:/run/secrets/database_url:ro",
  "-i","abgen-tests:0.1.0-dev","node","--input-type=module","-"],input=program.encode())
 (ROOT/"docs/implementation/evidence/abgen-restored-http.log").write_bytes(output+b"exit_code=0\n")
 print(output.decode(),flush=True)
 note("restored native HTTP, denied accesses, child code, original share, asset bytes, collaboration and real PDF verified without migration or reseeding")
finally:run(target+["stop"])
report={"sourceProject":fixture["project"],"restoredProject":project,"database":metadata,"assetArchiveSha256":digest,
 "checks":checks,"operations":operations,"stopped":True,"freshDatabaseAndAssetVolumes":True,"businessTables":sorted(before)}
(ROOT/"docs/implementation/evidence/abgen-restore.json").write_text(json.dumps(report,indent=2)+"\n")
print("Empty standalone restore passed; isolated source and restore services stopped; volumes preserved")
