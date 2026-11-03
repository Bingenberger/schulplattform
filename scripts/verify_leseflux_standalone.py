"""Real standalone JSON API/SPA, explicit Prisma migration and revoked sessions."""
from pathlib import Path
import json,os,secrets,socket,subprocess,time
from datetime import datetime,timezone
from leseflux_fixture import Browser,ADMIN,CONTRACT
ROOT=Path(__file__).resolve().parents[1];out=ROOT/"docs/implementation/evidence"
project="sp-leseflux-standalone-"+secrets.token_hex(5)
private=ROOT/".work"/project;private.mkdir(mode=0o700);keys=private/"secrets";keys.mkdir(mode=0o700)
password=secrets.token_hex(32)
for name,value in {"db-admin":secrets.token_hex(32),"db-app":password,"jwt-key":secrets.token_urlsafe(48),
    "database-url":"postgresql://leseflux:"+password+"@postgres:5432/leseflux?connection_limit=5&pool_timeout=3&connect_timeout=3"}.items():
    p=keys/name;p.write_text(value);p.chmod(0o444)
with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
origin="http://localhost:"+str(port)
env=os.environ|{"LESEFLUX_SECRETS_DIR":str(keys),"LESEFLUX_PORT":str(port),"CORS_ORIGIN":origin,"COOKIE_SECURE":"false"}
compose=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/leseflux/docker-compose.yml")]
operations=[];checks=[]
def run(command,**kwargs):
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Standalone command failed"
    return result.stdout
def code(source):return run(compose+["exec","-T","app","node","-"],input=source)
def query(source):
    program="const {load}=require('./scripts/credentials.cjs');load(['DATABASE_URL']);const {PrismaClient}=require('@prisma/client');const p=new PrismaClient({log:[]});(async()=>{"+source+"})().finally(()=>p.$disconnect()).catch(()=>process.exitCode=1);"
    return code(program)
def browser():return Browser(port)
def wait(path,expected=200):
    for _ in range(100):
        try:browser().call("GET",path,expected=expected);return
        except (OSError,AssertionError):time.sleep(.2)
    raise RuntimeError("HTTP check failed: "+path)
def note(name):checks.append(name);print("PASS",name,flush=True)
report={}
try:
    run(compose+["up","-d","--no-build"])
    wait("/health/live");wait("/health/ready",503)
    browser().call("POST","/api/auth/login-teacher",{"email":"fixture-admin@example.invalid","password":"invalid123"},expected=503)
    run(compose+["run","--rm","--no-deps","app","node","scripts/platform-migrate.cjs"])
    wait("/health/ready")
    assert query("console.log(await p.user.count())").strip()=="0"
    headless=subprocess.run(compose+["exec","-T","app","node","scripts/setup-admin.cjs","fixture-admin@example.invalid","Synthetic"],
        env=env,capture_output=True,text=True)
    assert headless.returncode!=0 and not headless.stdout.strip()
    adminid=json.loads(code(ADMIN))["id"]
    run(compose+["run","--rm","--no-deps","app","node","scripts/content.cjs"])
    assert query("console.log(await p.user.count())").strip()=="1"
    query("await p.sessionTemplate.update({where:{id:'standard-12-min'},data:{name:'Synthetic preserved template'}});")
    run(compose+["run","--rm","--no-deps","app","node","scripts/content.cjs"])
    assert query("console.log((await p.sessionTemplate.findUnique({where:{id:'standard-12-min'}})).name)").strip()=="Synthetic preserved template"
    note("live independent of schema; explicit migration; no default accounts; headless setup refused; content preserves accounts/templates")
    anonymous,admin,teacher,other,child=browser(),browser(),browser(),browser(),browser()
    anonymous.call("GET","/api/auth/me",expected=401)
    credentials={"email":"fixture-admin@example.invalid","password":"synthetic-admin-123"}
    anonymous.call("POST","/api/auth/login-teacher",credentials,expected=403,csrf=False)
    anonymous.call("POST","/api/auth/login-teacher",credentials,headers={"Origin":"https://foreign.invalid"},expected=403)
    logged=admin.call("POST","/api/auth/login-teacher",credentials,headers={"Origin":origin})
    assert "token" not in logged and logged["user"]["id"]==adminid
    assert admin.cookie_options["token"]["httponly"] and admin.cookie_options["token"]["samesite"].lower()=="strict"
    for index in range(2):
        admin.call("POST","/api/admin/teachers",{"displayName":"Synthetic Teacher "+str(index),
            "email":"fixture-teacher"+str(index)+"@example.invalid","password":"synthetic-teacher-123"},expected=201)
    teacher.call("POST","/api/auth/login-teacher",{"email":"fixture-teacher0@example.invalid","password":"synthetic-teacher-123"})
    other.call("POST","/api/auth/login-teacher",{"email":"fixture-teacher1@example.invalid","password":"synthetic-teacher-123"})
    ownclass=teacher.call("POST","/api/teacher/classes",{"name":"Synthetic Class A","schoolYear":"2026/27"},expected=201)
    secondclass=other.call("POST","/api/teacher/classes",{"name":"Synthetic Class B","schoolYear":"2026/27"},expected=201)
    other.call("GET","/api/teacher/classes/"+ownclass["id"],expected=404)
    teacher.call("GET","/api/admin/teachers",expected=403)
    create={"displayName":"Synthetic Child","classId":ownclass["id"],"parentalConsentDate":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
    other.call("POST","/api/teacher/students",create,expected=404)
    unassigned=dict(create);unassigned.pop("classId")
    teacher.call("POST","/api/teacher/students",unassigned,expected=400)
    without_consent=dict(create);without_consent.pop("parentalConsentDate")
    teacher.call("POST","/api/teacher/students",without_consent,expected=400)
    created=teacher.call("POST","/api/teacher/students",create,expected=201)
    student=created["student"];qr=created["qrToken"];login_code=created["loginCode"]
    secretfile=private/"child-capabilities.json";secretfile.write_text(json.dumps({"qrToken":qr,"loginCode":login_code}));secretfile.chmod(0o600)
    other.call("GET","/api/teacher/students/"+student["id"],expected=404)
    child.call("POST","/api/auth/login-child",{"qrToken":qr})
    child.call("GET","/api/admin/teachers",expected=403)
    child.call("GET","/api/training/my-progress")
    started=child.call("POST","/api/training/start",{})
    assert started
    detail=teacher.call("GET","/api/teacher/students/"+student["id"])
    assert detail["qrTokenRaw"] is None
    assert query("console.log(await p.user.count({where:{qrTokenRaw:{not:null}}}))").strip()=="0"
    note("CSRF/foreign Origin denied; roles and class/student ownership enforced; consent required; QR child login and training start work")
    stale=browser();stale.cookies=child.cookies.copy()
    child.call("POST","/api/auth/logout")
    stale.call("GET","/api/auth/me",expected=401)
    child.call("POST","/api/auth/login-child-code",{"loginCode":login_code})
    saved=child.cookies.copy()
    (private/"child-cookies.json").write_text(json.dumps(saved));(private/"child-cookies.json").chmod(0o600)
    run(compose+["restart","app"]);wait("/health/ready")
    child.call("GET","/api/auth/me")
    regenerated=teacher.call("POST","/api/teacher/students/"+student["id"]+"/regenerate-qr")
    child.call("GET","/api/auth/me",expected=401)
    anonymous.call("POST","/api/auth/login-child",{"qrToken":qr},expected=401)
    newqr=regenerated["qrToken"]
    child.call("POST","/api/auth/login-child",{"qrToken":newqr})
    secretfile.write_text(json.dumps({"qrToken":qr,"newQrToken":newqr,"loginCode":login_code}))
    assert query("console.log(await p.authSession.count())").strip().isdigit()
    note("logout and QR rotation revoke JWTs server-side; original session survives ordinary restart")
    now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    import_row={"vorname":"Synthetic Import","antonCode":"synthetic-"+secrets.token_hex(10)}
    (private/"anton-capability").write_text(import_row["antonCode"]);(private/"anton-capability").chmod(0o600)
    teacher.call("POST","/api/teacher/students/import-anton",{"defaultClassId":ownclass["id"],"rows":[import_row]},expected=400)
    teacher.call("POST","/api/teacher/students/import-anton",{"defaultClassId":secondclass["id"],"parentalConsentDate":now,"rows":[import_row]},expected=404)
    imported=teacher.call("POST","/api/teacher/students/import-anton",{"defaultClassId":ownclass["id"],"parentalConsentDate":now,"rows":[import_row]})
    assert imported["imported"]==1
    audit=query("console.log(JSON.stringify(await p.auditLog.findMany({where:{action:'student.import_anton'}})))")
    assert import_row["antonCode"] not in audit and "parentalConsentDate" in audit
    note("bulk import requires consent and owned target class; no QR capabilities in audit or new raw-token columns")
    admin.call("PATCH","/api/admin/teachers/"+teacher.call("GET","/api/auth/me")["id"],{"password":"new-synthetic-teacher-123"})
    teacher.call("GET","/api/auth/me",expected=401)
    teacher.call("POST","/api/auth/login-teacher",{"email":"fixture-teacher0@example.invalid","password":"new-synthetic-teacher-123"})
    teacher.call("DELETE","/api/teacher/students/"+student["id"])
    child.call("GET","/api/auth/me",expected=401)
    note("password reset and child deletion revoke sessions, including child with training history")
    # Retain a complete reading/quiz record for the independent restore proof.
    template=teacher.call("POST","/api/teacher/session-templates",{"name":"Synthetic short reading","visibility":"PRIVATE",
        "blocks":[{"type":"FADING","targetDurationSec":30}]},expected=201)
    teacher.call("PATCH","/api/teacher/classes/"+ownclass["id"]+"/template",{"sessionTemplateId":template["id"]})
    keeper=teacher.call("POST","/api/teacher/students",{"displayName":"Synthetic Restore Child","classId":ownclass["id"],
        "parentalConsentDate":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")},expected=201)
    learner=browser();learner.call("POST","/api/auth/login-child",{"qrToken":keeper["qrToken"]})
    reading=learner.call("POST","/api/training/start",{})
    assert len(reading["exercises"])==1 and reading["exercises"][0]["type"]=="FADING"
    exercise=reading["exercises"][0]
    answers=json.loads(query("console.log(JSON.stringify(await p.textQuestion.findMany({where:{textId:"+json.dumps(exercise["text"]["id"])+"}})))"))
    payload={"responses":[{"questionId":row["id"],"selectedIndex":row["correctIndex"],"responseTimeMs":500} for row in answers],
        "durationMs":35000}
    learner.call("POST","/api/training/exercise/"+exercise["runId"]+"/finish",payload)
    finished=learner.call("POST","/api/training/finish",{"sessionId":reading["sessionId"],"totalDurationMs":35000})
    assert finished["starsEarned"]==3
    assert learner.call("GET","/api/training/my-progress")["totalSessions"]==1
    (private/"restore-child.json").write_text(json.dumps({"id":keeper["student"]["id"],"qrToken":keeper["qrToken"],
        "loginCode":keeper["loginCode"],"sessionId":reading["sessionId"]}));(private/"restore-child.json").chmod(0o600)
    note("complete reading exercise, correct quiz answers and training progress retained for restore")
    # Synthetic legacy QR plaintext must be preserved by migration, but never exposed by projections.
    query("await p.user.update({where:{id:"+json.dumps(keeper["student"]["id"])+"},data:{qrTokenRaw:"+json.dumps(keeper["qrToken"])+"}});")
    public_class=teacher.call("GET","/api/teacher/classes/"+ownclass["id"])
    assert keeper["qrToken"] not in json.dumps(public_class)
    assert all("passwordHash" not in user and "qrTokenRaw" not in user and "qrTokenHash" not in user for user in public_class["students"])
    updated=teacher.call("PATCH","/api/teacher/students/"+keeper["student"]["id"]+"/template",{"sessionTemplateId":None})
    assert "qrTokenRaw" not in updated and "passwordHash" not in updated
    run(compose+["run","--rm","--no-deps","app","node","scripts/platform-migrate.cjs"])
    assert query("console.log((await p.user.findUnique({where:{id:"+json.dumps(keeper["student"]["id"])+"}})).qrTokenRaw)").strip()==keeper["qrToken"]
    note("legacy QR and IDs preserved by migration; class/detail/template projections withhold legacy raw tokens and password hashes")


    for path in ["/.env","/prisma/schema.prisma","/node_modules/prisma/build/index.js"]:
        anonymous.call("GET",path,expected=404)
    html=anonymous.call("GET","/").decode()
    assert "fonts.googleapis" not in html
    anonymous.call("POST","/api/auth/login-child",b"x"*(2*1024*1024+1),headers={"Content-Type":"application/json"},expected=413)
    note("SPA served locally; private filesystem routes denied; oversized JSON refused")
    # Restore an explicitly altered migration inventory; never accept drift silently.
    migration=query("console.log(JSON.stringify(await p.$queryRawUnsafe('SELECT migration_name,checksum FROM \"_prisma_migrations\" ORDER BY migration_name LIMIT 1')))").strip()
    marker=json.loads(migration)[0]
    query("await p.$executeRawUnsafe('UPDATE \"_prisma_migrations\" SET checksum=$1 WHERE migration_name=$2','0'.repeat(64),"+json.dumps(marker["migration_name"])+");")
    wait("/health/ready",503)
    query("await p.$executeRawUnsafe('UPDATE \"_prisma_migrations\" SET checksum=$1 WHERE migration_name=$2',"+json.dumps(marker["checksum"])+","+json.dumps(marker["migration_name"])+");")
    wait("/health/ready")
    run(compose+["stop","postgres"]);wait("/health/live");wait("/health/ready",503)
    run(compose+["up","-d","--wait","postgres"]);wait("/health/ready")
    note("migration checksum drift and DB outage fail readiness while liveness remains available")
    appcid=run(compose+["ps","-q","app"]).strip()
    info=json.loads(run(["docker","inspect",appcid]))[0]
    assert info["Config"]["User"]=="10001:10001" and info["HostConfig"]["ReadonlyRootfs"]
    assert not any(value.startswith(("DATABASE_URL=","JWT_SECRET=")) for value in info["Config"]["Env"])
    rawlogs=subprocess.run(["docker","logs",appcid],capture_output=True,text=True,check=True)
    logs=rawlogs.stdout+rawlogs.stderr
    assert all(value not in logs for value in [password,qr,newqr,import_row["antonCode"],(keys/"jwt-key").read_text()])
    contract=json.loads(code(CONTRACT))
    fixture={"project":project,"secretDirectory":str(keys),"contract":contract,"class":ownclass["id"],
        "admin":adminid,"teacherEmail":"fixture-teacher0@example.invalid","teacherPassword":"new-synthetic-teacher-123","restoreChild":keeper["student"]["id"]}
    (private/"fixture.json").write_text(json.dumps(fixture));(private/"fixture.json").chmod(0o600)
    (ROOT/".work/leseflux-latest-fixture").write_text(str(private))
    report={"imageId":info["Image"],"standalone":True,"privateFileCredentials":True,"nonRootReadOnly":True,
        "checks":checks,"limits":["No production migration or identity import","No offsite backup","No real child data"]}
finally:
    run(compose+["stop"])
    report["stoppedDataRetained"]=True
    (out/"leseflux-standalone.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"leseflux-standalone-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
print(json.dumps(report))
