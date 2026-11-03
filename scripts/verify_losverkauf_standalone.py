"""Standalone ticket-sale HTTP, fixed worker, durable restart and local sink."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
from schulplattform.pilot import INFRASTRUCTURE
from losverkauf_fixture import Client,GEO,MAP_SOURCE,CONTRACT,register,probe
from werkzeug.security import generate_password_hash

project="sp-lose-standalone-"+secrets.token_hex(5)
directory=ROOT/".work"/project
directory.mkdir(mode=0o700)
secret_dir=directory/"secrets"
secret_dir.mkdir(mode=0o700)
values={"session-key":secrets.token_urlsafe(48),"parent-token":secrets.token_urlsafe(48),
        "admin-name":"synthetic.operator","admin-hash":generate_password_hash("synthetic-password")}
for name,value in values.items():
    path=secret_dir/name
    path.write_text(value)
    path.chmod(0o444)
with socket.socket() as listener:
    listener.bind(("127.0.0.1",0))
    port=listener.getsockname()[1]
origin="http://127.0.0.1:"+str(port)
env=os.environ|{"LOSVERKAUF_SECRETS_DIR":str(secret_dir),"LOSVERKAUF_PORT":str(port),"BASE_URL":origin,
                "SMTP_HOST":"mailpit","SMTP_PORT":"1025","SMTP_SICHERHEIT":"keine","SMTP_USER":"",
                "SMTP_PASSWORD_FILE":"","TILE_URL":"","PROXY_IPS":""}
base=[str(ROOT/".work/docker-compose"),"-p",project,"-f",str(ROOT/".work/apps/losverkauf/docker-compose.yml")]
out=ROOT/"docs/implementation/evidence"
sink=project+"-mail"
operations=[]
paused=False

def run(command,**kwargs):
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180,**kwargs)
    operations.append({"command":command,"exitCode":result.returncode})
    assert result.returncode==0,"Standalone fixture command failed"
    return result.stdout

def code(source):
    return run(base+["exec","-T","app","python","-"],input=source)

def wait_live():
    for _ in range(60):
        try:
            if Client(port).request("/health/live")[0]==200:return
        except OSError: pass
        time.sleep(.2)
    raise RuntimeError("Application not live")

def wait_queue(expected):
    source="""import json,time,sqlite3
for _ in range(200):
    with sqlite3.connect('/data/losverkauf.db') as db:
        rows=db.execute('SELECT id,status,attempts FROM mail_outbox ORDER BY id').fetchall()
    if len(rows)==EXPECTED and all(row[1]=='sent' for row in rows):break
    time.sleep(.1)
assert len(rows)==EXPECTED and all(row[1]=='sent' for row in rows)
print(json.dumps({'jobs':len(rows),'retried':any(row[2]>1 for row in rows)}))
""".replace("EXPECTED",str(expected))
    return json.loads(code(source))

try:
    run(base+["up","-d","--no-build"])
    wait_live()
    assert Client(port).request("/health/ready")[0]==503
    code(MAP_SOURCE)
    run(base+["run","--rm","--no-deps","app","python","-m","los_migrate"])
    assert Client(port).request("/healthz")[0]==200
    run(["docker","run","-d","--name",sink,"--network",project+"_default","--network-alias","mailpit",
         "--read-only","--user","10001:10001","--cap-drop","ALL","--security-opt","no-new-privileges:true",
         "--memory","128m","--cpus","0.5","--pids-limit","64","--tmpfs","/tmp:size=64m,mode=1777",INFRASTRUCTURE["mailpit"]])
    client=Client(port)
    nonce=client.parent(values["parent-token"])
    status,body,_=register(client,nonce)
    assert status==200
    capability=json.loads(body)["edit_token"]
    wait_queue(1)
    result=probe(Client(port),values["parent-token"],origin,capability)
    mail=json.loads(code("""import json,urllib.request
from app import BASE_URL
messages=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/messages'))['messages']
assert messages
message=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/message/'+messages[0]['ID']))
assert BASE_URL+'/?t=' in message['Text'] and '&edit=' in message['Text']
print(json.dumps({'mailSinkDelivered':True,'individualResumeLink':True}))
"""))
    def book(index):
        browser=Client(port)
        nonce=browser.parent(values["parent-token"])
        return register(browser,nonce,"two","Synthetic Parallel "+str(index))[0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses=list(pool.map(book,range(8)))
    assert statuses.count(200)==1 and statuses.count(409)==7
    wait_queue(2)
    administrator=Client(port)
    nonce=administrator.login()
    assert administrator.request("/admin/bezirk/two","POST",data={"csrf_token":nonce,"max_override":"2"})[0]==302
    run(["docker","pause",sink])
    paused=True
    browser=Client(port)
    nonce=browser.parent(values["parent-token"])
    assert register(browser,nonce,"two","Synthetic Restart")[0]==200
    time.sleep(.5)
    assert Client(port).request("/health/ready")[0]==200
    jobs=json.loads(code("import sqlite3,json;db=sqlite3.connect('/data/losverkauf.db');print(json.dumps(db.execute('SELECT id,status FROM mail_outbox ORDER BY id').fetchall()))"))
    assert len(jobs)==3 and jobs[-1][1] in ("pending","sending")
    run(base+["restart","app"])
    wait_live()
    assert Client(port).request("/health/ready")[0]==200
    run(["docker","unpause",sink])
    paused=False
    recovered=wait_queue(3)
    # File-mode mail is an independent private persistent-directory fixture.
    file_hash=json.loads(code("""import json,hashlib
from pathlib import Path
import mail
mail.SMTP_HOST=''
assert mail.senden(['synthetic@example.invalid'],'Synthetic archive','Synthetic private mail fixture',Path('/data/mails')) is None
files=list(Path('/data/mails').glob('*.eml'))
assert len(files)==1 and files[0].stat().st_mode&511==384
print(json.dumps({'mailFileSha256':hashlib.sha256(files[0].read_bytes()).hexdigest()}))
"""))
    contract=json.loads(code(CONTRACT))
    cid=run(base+["ps","-q","app"]).strip()
    info=json.loads(run(["docker","inspect",cid]))[0]
    assert info["Config"]["User"]=="10001:10001" and info["HostConfig"]["ReadonlyRootfs"] and info["HostConfig"]["Init"]
    logs=subprocess.run(["docker","logs",cid],capture_output=True,text=True,timeout=30)
    combined=logs.stdout+logs.stderr
    assert all(value not in combined for value in (values["session-key"],values["parent-token"],capability))
    volume=next(item["Name"] for item in info["Mounts"] if item["Destination"]=="/data")
    fixture={"project":project,"volume":volume,"secretDirectory":str(secret_dir),"capability":capability,
             "contract":contract,"mailFile":file_hash["mailFileSha256"],"imageId":info["Image"]}
    (directory/"fixture.json").write_text(json.dumps(fixture))
    (ROOT/".work/losverkauf-latest-fixture").write_text(str(directory))
    report={"scope":"standalone Compose without platform override; local synthetic map and SMTP sink",
            "imageId":info["Image"],"preMigrationReady503":True,"explicitMigration":True,
            "parallelRequests":8,"oneAccepted":True,"sevenConflict409":True,
            "pendingJobSurvivesWorkerRestart":True,"smtpOutageReady200":True,"recoveredJobs":recovered["jobs"],
            "nonRootReadOnly":True,"capabilitiesAbsentFromLogs":True,**result,**mail,**file_hash}
    (out/"losverkauf-standalone.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
finally:
    if paused: subprocess.run(["docker","unpause",sink],capture_output=True,timeout=30)
    subprocess.run(["docker","rm","-f",sink],capture_output=True,timeout=30)
    run(base+["down"])
    (out/"losverkauf-standalone-operations.json").write_text(json.dumps(operations,indent=2)+"\n")
