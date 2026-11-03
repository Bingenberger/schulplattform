"""Stopped-writer schulwissen PostgreSQL/media restore followed by real HTTP."""
import hashlib,json,os,secrets,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import quote
from schulwissen_fixture import Browser,SEED
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from schulplattform.pilot import Pilot,INFRASTRUCTURE
from schulplattform.pilot_engine import PilotEngine
from schulplattform.postgres import Postgres
from schulplattform.snapshot import checksum
pilot=Pilot(ROOT/".work/pilot-v21")
directory=pilot.directory/"schulwissen-restore-fixtures"/secrets.token_hex(5)
directory.mkdir(parents=True,mode=0o700);directory.parent.chmod(0o700)
project="sp-wissen-http-restore-"+secrets.token_hex(5)
fixture={"prefix":"restore-"+secrets.token_hex(5),"password":secrets.token_urlsafe(24)}
(directory/"credentials.json").write_text(json.dumps(fixture));(directory/"credentials.json").chmod(0o600)
operations=[];checks=[]
def run(command,**kwargs):
 result=subprocess.run(command,capture_output=True,timeout=180,**kwargs)
 operations.append({"command":command,"exitCode":result.returncode})
 if result.returncode:
  (directory/"failure.private.log").write_bytes(result.stdout+result.stderr)
  raise AssertionError("Restore command failed; private diagnostic retained")
 return result.stdout
def note(value):checks.append(value);print("PASS "+value,flush=True)
def inventory(database):
 names=database.query("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1").splitlines()
 assert all(__import__("re").fullmatch("[a-z_]+",name) for name in names)
 return {name:database.query("SELECT count(*)||':'||md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) FROM "+name+" t") for name in names}
PYTHON="python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
def helper(source,volume,mode,input=None):
 return run(["docker","run","--rm","--read-only","--network","none","--user","10001:10001","--cap-drop","ALL",
  "--security-opt","no-new-privileges:true","--memory","512m","--pids-limit","64","--tmpfs","/tmp:size=64m,mode=1777",
  "-e","PYTHONPATH=/helper","-e","PYTHONDONTWRITEBYTECODE=1","-v",str(ROOT/"schulplattform")+":/helper/schulplattform:ro",
  "-v",volume+":/data:"+mode,"-i",PYTHON,"python","-c",source],input=input)
with socket.socket() as listener:listener.bind(("127.0.0.1",0));port=listener.getsockname()[1]
password=secrets.token_urlsafe(48)
for name,value in {"db-app":password,"db-admin":secrets.token_urlsafe(48),
 "database-url":"postgresql://schulwissen:"+password+"@db:5432/schulwissen"}.items():
 file=directory/name;file.write_text(value);file.chmod(0o444)
(directory/"init-postgres.sh").write_bytes((pilot.directory/"init-postgres.sh").read_bytes())
override=directory/"restore.yml"
override.write_text(f"""
services:
  db:
    restart: "no"
    environment: !override
      POSTGRES_USER: postgres
      POSTGRES_DB: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/admin_password
    secrets: [admin_password, app_db_password]
    volumes: !override
      - pgdaten:/var/lib/postgresql/data
      - {directory}/init-postgres.sh:/docker-entrypoint-initdb.d/01-app.sh:ro
  app:
    restart: "no"
    env_file: !reset []
    environment: !override
      SW_SECRET_KEY_FILE: /run/secrets/session_key
      SW_DATABASE_URL_FILE: /run/secrets/database_url
      SW_ALLOWED_HOSTS: localhost,127.0.0.1
      SW_OEFFENTLICHE_URL: http://127.0.0.1:{port}
      SW_COOKIE_SECURE: "false"
      SW_HSTS_TAGE: "0"
      SW_WORKER: "2"
      SW_MEDIEN_VERZEICHNIS: /medien
      FORWARDED_ALLOW_IPS: 127.0.0.1
    secrets: [session_key, database_url]
    ports: !override ["127.0.0.1:{port}:8000"]
secrets:
  admin_password:
    file: {directory}/db-admin
  app_db_password:
    file: {directory}/db-app
  session_key:
    file: {pilot.directory}/runtime/wissen-key
  database_url:
    file: {directory}/database-url
""")
base=[str(pilot.compose),"-p",project,"-f",str(ROOT/".work/apps/schulwissen/docker-compose.yml"),"-f",str(override)]
env=os.environ|{"POSTGRES_PASSWORD":"unused-overridden-private-files"}
def compose(*args):return run(base+list(args),env=env)
report={}
try:
 if not PilotEngine(pilot).status("schulwissen")["running"]:PilotEngine(pilot).execute("start","schulwissen")
 backend=pilot.inspect_service("schulwissen","app")
 source=Postgres(["docker","exec",pilot.inspect_service("schulwissen","db")["Id"]],"schulwissen","schulwissen")
 source_volume=next(m["Name"] for m in backend["Mounts"] if m["Destination"]=="/medien")
 data=json.loads(pilot.command(["docker","exec","-i",backend["Id"],"python","-"],
  input="fixture="+repr(fixture)+"\n"+SEED))
 (directory/"fixture.json").write_text(json.dumps(data));(directory/"fixture.json").chmod(0o600)
 source_browser=Browser(pilot.config["port"],pilot.current_domains()["schulwissen"],pilot.directory/"root.crt")
 source_browser.login(data["users"][1]["email"],fixture["password"])
 media="/medien/"+quote(data["mediaPath"],safe="/")
 expected=b"Synthetic private attachment bytes\n"
 assert source_browser.call("GET",media)==expected
 (directory/"http-cookies.private.json").write_text(json.dumps(source_browser.cookies));(directory/"http-cookies.private.json").chmod(0o600)
 PilotEngine(pilot).execute("stop","schulwissen")
 before=inventory(source);metadata=source.snapshot(directory/"database.dump")
 archive=helper("from pathlib import Path\nfrom schulplattform.snapshot import create\nimport sys\np=Path('/data');create(p,sys.stdout.buffer,directories=[x.name for x in p.iterdir() if x.is_dir()],files=[x.name for x in p.iterdir() if x.is_file()])",source_volume,"ro")
 (directory/"media.tar").write_bytes(archive);(directory/"media.tar").chmod(0o600)
 digest=checksum(directory/"media.tar")
 note("source web writers stopped; consistent PostgreSQL and private media captured together")
 compose("up","-d","--no-build","--wait","db")
 target_id=compose("ps","-q","db").decode().strip()
 target=Postgres(["docker","exec","-i",target_id],"schulwissen","schulwissen")
 target.restore_into_empty(directory/"database.dump",metadata,directory)
 try:target.restore_into_empty(directory/"database.dump",metadata,directory)
 except ValueError as error:assert "not empty" in str(error)
 else:raise AssertionError("Nonempty restore accepted")
 assert inventory(target)==before
 assert target.query("SELECT count(*) FROM pg_constraint WHERE contype='f' AND NOT convalidated")=="0"
 assert target.query("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner <> 'schulwissen'")=="0"
 assert target.query("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user")=="f"
 note("empty database restore preserves every table row, session, role/owner ID and validated foreign key; nonempty target rejected")
 compose("create","--no-build","app")
 app_id=compose("ps","-aq","app").decode().strip()
 app_info=json.loads(run(["docker","inspect",app_id]))[0]
 target_volume=next(m["Name"] for m in app_info["Mounts"] if m["Destination"]=="/medien")
 helper("from pathlib import Path\nfrom schulplattform.snapshot import restore\nimport sys\np=Path('/tmp/media.tar');p.write_bytes(sys.stdin.buffer.read());restore(p,Path('/data'),'"+digest+"')",target_volume,"rw",archive)
 verify_media="from pathlib import Path\nimport hashlib,json\nprint(json.dumps({str(p.relative_to('/data')):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'uid':p.stat().st_uid} for p in Path('/data').rglob('*') if p.is_file()}))"
 assert json.loads(helper(verify_media,source_volume,"ro"))==json.loads(helper(verify_media,target_volume,"ro"))
 note("private media restored byte-identically into an independent empty volume owned by UID 10001")
 compose("up","-d","--no-build","--wait","--wait-timeout","90","app")
 restored=Browser(port);restored.cookies=source_browser.cookies.copy()
 assert b"html" in restored.call("GET","/").lower()
 assert restored.call("GET",media)==expected
 note("restored database-backed session works with separately preserved signing key before any new target login")
 admin,teacher,other,anonymous=[Browser(port) for _ in range(4)]
 for client,index in [(admin,0),(teacher,1),(other,2)]:client.login(data["users"][index]["email"],fixture["password"])
 path="/d/"+data["documentSlug"]
 assert b"Synthetic protected restore document" in teacher.call("GET",path)
 assert b"Synthetic preserved knowledge" in teacher.call("GET",path+"/S-01")
 assert teacher.call("GET",media)==expected
 other.call("GET",path,expected=404);other.call("GET",media,expected=404)
 teacher.call("GET",path+"/export/json",expected=403)
 assert "Synthetic preserved knowledge" in json.dumps(admin.call("GET",path+"/export/json"))
 pdf=admin.call("GET",path+"/export/pdf");assert pdf.startswith(b"%PDF")
 anonymous.call("GET",media,expected=302);anonymous.call("GET","/",expected=302)
 teacher.form("/abmelden",csrf=False,expected=403)
 teacher.form("/abmelden",origin="https://foreign.invalid",expected=403)
 copied=Browser(port);copied.cookies=teacher.cookies.copy()
 teacher.form("/abmelden");copied.call("GET","/",expected=302)
 note("real HTTP role/document/area/media denials, login, JSON/PDF export, CSRF/Origin and copied-cookie logout revocation passed")
 app_info=json.loads(run(["docker","inspect",app_id]))[0]
 assert app_info["Config"]["User"]=="schulwissen" and app_info["HostConfig"]["ReadonlyRootfs"]
 assert not json.loads(run(["docker","inspect",target_id]))[0]["HostConfig"]["PortBindings"]
 report={"scope":"Synthetic schulwissen PostgreSQL plus media restore into empty independent storage; real loopback HTTP",
  "sourcePilot":pilot.project,"restoreProject":project,"imageId":app_info["Image"],"database":metadata,
  "mediaArchiveSha256":digest,"allTablesIdenticalBeforeHttp":True,"businessTables":sorted(before),
  "existingSessionAndSigningKeyPreserved":True,"originalUserRoleOwnershipAndDocumentIdsPreserved":True,
  "mediaByteExact":True,"rootlessReadOnly":True,"realPdfAndJsonExport":True,"nativeDeniedAccessesPreserved":True,
  "noTargetMigrationOrBootstrap":True,"checks":checks,
  "limits":["Synthetic fixture, no real school inventory","Private loopback HTTP, no target TLS/ACME",
            "No encrypted offsite transport or RPO/RTO acceptance"]}
finally:
 compose("stop");pilot.stop()
if report:
 report["sourceAndTargetStoppedDataRetained"]=True
 (ROOT/"docs/implementation/evidence/schulwissen-http-restore.json").write_text(json.dumps(report,indent=2)+"\n")
 (ROOT/"docs/implementation/evidence/schulwissen-http-restore-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
 (ROOT/".work/schulwissen-latest-restore").write_text(str(directory))
 print(json.dumps(report))
