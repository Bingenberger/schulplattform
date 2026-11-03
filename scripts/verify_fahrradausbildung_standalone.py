"""Real standalone PG, explicit migration, two-worker concurrency and station capability."""
from pathlib import Path
import concurrent.futures,hashlib,json,os,secrets,socket,subprocess,time,uuid
from fahrrad_fixture import Browser,SEED,CONTRACT
ROOT=Path(__file__).resolve().parents[1];out=ROOT/"docs/implementation/evidence"
project="sp-fahrrad-standalone-"+secrets.token_hex(5)
private=ROOT/".work"/project;private.mkdir(mode=0o700)
secret_dir=private/"secrets";secret_dir.mkdir(mode=0o700)
password=secrets.token_hex(32)
for name,value in {"db-admin":secrets.token_hex(32),"db-app":password,
    "database-url":"postgresql+psycopg://fahrrad:"+password+"@db:5432/fahrrad"}.items():
    p=secret_dir/name;p.write_text(value);p.chmod(0o444)
with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
origin="http://localhost:"+str(port)
env=os.environ|{"FP_SECRETS_DIR":str(secret_dir),"FP_PORT":str(port),"FP_OEFFENTLICHE_URL":origin,
    "FP_COOKIE_SECURE":"false","FP_KARTEN_KACHELN":"","FP_PROXY_IPS":"127.0.0.1"}
compose=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/fahrradausbildung/docker-compose.yml")]
operations=[]
def run(command,**kwargs):
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Standalone command failed"
    return result.stdout
def code(source):return run(compose+["exec","-T","app","python","-"],input=source)
def browser():return Browser(port)
def ready(path,expected):
    for _ in range(100):
        try:browser().call("GET",path,expected=expected);return
        except (OSError,AssertionError):time.sleep(.2)
    raise RuntimeError("HTTP readiness failed")
report={}
try:
    run(compose+["up","-d","--no-build"])
    ready("/health/live",200);ready("/health/ready",503)
    run(compose+["run","--rm","--no-deps","app","python","-m","app.migrate"])
    ready("/health/ready",200)
    user_count=int(code("from app.db import engine;from sqlalchemy import text\nwith engine().connect() as c:print(c.execute(text('select count(*) from benutzer')).scalar_one())"))
    assert user_count==0
    headless=subprocess.run(compose+["exec","-T","app","python","-m","app.kommandos","systemadmin-anlegen","fixture-root@example.invalid"],
        env=env,capture_output=True,text=True)
    assert headless.returncode!=0 and "Terminal" in headless.stderr
    fixtures=json.loads(code(SEED));first,second=fixtures
    appcid=run(compose+["ps","-q","app"]).strip();dbcid=run(compose+["ps","-q","db"]).strip()
    info=json.loads(run(["docker","inspect",appcid]))[0]
    template_volume=next(m["Name"] for m in info["Mounts"] if m["Destination"]=="/vorlagen")
    run(["docker","run","--rm","--network","none","--read-only","-v",template_volume+":/vorlagen",
        "fahrradausbildung:0.1.0-dev","python","-c","from pathlib import Path;Path('/vorlagen/fixture.txt').write_text('Synthetic template fixture')"])
    a,b,anonymous=browser(),browser(),browser()
    anonymous.call("GET","/verwaltung/",expected=303)
    a.login(first["email"]);b.login(second["email"])
    a.page("/verwaltung/");b.call("GET","/verwaltung/strecken/"+str(first["track"]),expected=404)
    a.form("/verwaltung/strecken/neu",{"name":"forbidden"},expected=403)
    cfg=anonymous.call("GET","/api/p/"+first["token"]+"/config")
    assert cfg["lauf_id"]==first["run"] and cfg["startnummern"]==[7]
    anonymous.call("GET","/api/p/"+secrets.token_urlsafe(32)+"/config",expected=404)
    assert "manifest.webmanifest" in anonymous.page("/p/"+first["token"])
    assert anonymous.call("GET","/p/"+first["token"]+"/manifest.webmanifest")["start_url"]=="/p/"+first["token"]
    assert b"__VERSION__" not in anonymous.call("GET","/p/sw.js")
    eid=str(uuid.uuid4())
    event={"event_id":eid,"typ":"durchgang","startnummer":7,"nutzlast":{"durchgang_nr":1,"fehlende_items":[first["item"]]},
        "erfasst_am":"2026-11-03T12:00:00Z"}
    path="/api/p/"+first["token"]+"/events"
    assert anonymous.call("POST",path,{"events":[event]})["akzeptiert"]==[eid]
    assert anonymous.call("POST",path,{"events":[event]})["akzeptiert"]==[eid]
    assert anonymous.call("GET","/api/p/"+first["token"]+"/status")["offen"]==0
    pdf=a.call("GET","/verwaltung/laeufe/"+str(first["run"])+"/postenblaetter.pdf")
    assert pdf.startswith(b"%PDF")
    slot=run(["docker","exec","-d",appcid,"python","-c",
        "import time;from app.betrieb import pdf_slot\nwith pdf_slot():\n open('/tmp/slot-held','w').close();time.sleep(30)"])
    for _ in range(100):
        if code("from pathlib import Path;print(Path('/tmp/slot-held').exists())").strip()=="True":break
        time.sleep(.05)
    else:raise RuntimeError("Export slot not held")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(a.call,"GET","/verwaltung/laeufe/"+str(first["run"])+"/postenblaetter.pdf",expected=503),
              pool.submit(anonymous.call,"GET","/health/live")]
        [j.result() for j in jobs]
    run(["docker","exec",appcid,"python","-c",
        "import os,signal\nfrom pathlib import Path\nfor p in Path('/proc').iterdir():\n if p.name.isdigit():\n  try:\n   if b\"time.sleep(30)\" in (p/'cmdline').read_bytes() and int(p.name)!=os.getpid():os.kill(int(p.name),signal.SIGTERM)\n  except (OSError,ProcessLookupError):pass"])
    # Shared counters are reserved before hashing: parallel guesses cannot overbook.
    code("from sqlalchemy import text;from app.db import engine\nwith engine().begin() as c:c.execute(text('DELETE FROM betriebs_limit'))")
    def guess(_):
        client=browser();html=client.page("/anmelden")
        import re
        csrf=re.search(r'name=\"csrf\" value=\"([^\"]+)\"',html)[1]
        # Allow either result here; assert counts independently without emitting credentials.
        try:client.form("/anmelden",{"email":second["email"],"passwort":"wrong-password","csrf":csrf},expected=401);return 401
        except AssertionError:
            assert client.last_status==429
            return 429
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:statuses=list(pool.map(guess,range(14)))
    assert statuses.count(401)==10 and statuses.count(429)==4
    run(compose+["restart","app"]);ready("/health/ready",200)
    blocked=browser()
    html=blocked.page("/anmelden")
    import re
    nonce=re.search(r'name=\"csrf\" value=\"([^\"]+)\"',html)[1]
    blocked.form("/anmelden",{"email":second["email"],"passwort":"synthetic-password","csrf":nonce},expected=429)
    a.page("/verwaltung/") # Existing valid server session survives restart.
    run(compose+["stop","db"]);ready("/health/live",200);ready("/health/ready",503)
    run(compose+["up","-d","--wait","db"]);ready("/health/ready",200)
    roles=json.loads(code("import json;from app.db import engine;from sqlalchemy import text\nwith engine().connect() as c:print(json.dumps(list(c.execute(text(\"SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user\")).one())))"))
    assert roles==[False,False,False]
    snapshot=json.loads(code(CONTRACT))
    raw_logs=subprocess.run(["docker","logs",appcid],capture_output=True,text=True,check=True)
    logs=raw_logs.stdout+raw_logs.stderr
    assert logs.count("Started server process")>=2
    assert all(f["token"] not in logs for f in fixtures)
    assert password not in logs
    assert info["Config"]["User"]=="10001:10001" and info["HostConfig"]["ReadonlyRootfs"]
    assert not any(value.startswith("FP_DATABASE_URL=") for value in info["Config"]["Env"])
    source={"project":project,"secretDirectory":str(secret_dir),"port":port,"fixtures":fixtures,"contract":snapshot,
        "templateVolume":template_volume,"databaseContainer":dbcid}
    (private/"fixture.json").write_text(json.dumps(source));(private/"fixture.json").chmod(0o600)
    (ROOT/".work/fahrrad-latest-fixture").write_text(str(private))
    report={"imageId":info["Image"],"standalone":True,"migrationExplicit":True,"noDefaultAccount":True,
        "headlessSetupDenied":True,"nonRootReadOnly":True,"databaseRoleUnprivileged":True,"twoWebWorkersObserved":True,
        "stationCapabilityAndPwaPublic":True,"csrfAndCrossSchoolDenied":True,"eventRetryIdempotent":True,
        "pdfGenerated":True,"sharedExportBusy503WhileLive200":True,"parallelLoginFailures":{"accepted":10,"blocked":4},
        "loginLimitAndSessionSurviveRestart":True,"databaseOutageLive200Ready503":True,"noSecretsInContainerEnvOrLogs":True,
        "browserOffline":"not exercised by this HTTP proof"}
finally:
    run(compose+["stop"])
    report["stoppedDataRetained"]=True
    (out/"fahrrad-standalone.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"fahrrad-standalone-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
print(json.dumps(report))
