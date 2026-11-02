"""Real standalone Compose with synthetic public booking, mail sink and parallel requests."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schulhelfer_fixture import Client, SEED, CONTRACT, probe
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import INFRASTRUCTURE

project = "sp-helfer-standalone-" + secrets.token_hex(5)
directory = ROOT / ".work" / project
directory.mkdir(mode=0o700)
key = directory / "session-key"
key.write_text(secrets.token_urlsafe(48))
key.chmod(0o444)
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
env = os.environ | {"SCHULHELFER_PORT": str(port), "SCHULHELFER_SECRET_FILE": str(key),
                    "BASE_URL": "http://127.0.0.1:" + str(port),
                    "SMTP_HOST": "mailpit", "SMTP_PORT": "1025", "SMTP_STARTTLS": "false",
                    "SMTP_USE_TLS": "false", "SMTP_USER": "", "SMTP_PASS_FILE": "",
                    "PROXY_IPS": ""}
base = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(ROOT / ".work/apps/schulhelfer/docker-compose.yml")]
operations = []
out = ROOT / "docs/implementation/evidence"
sink_name = project + "-mail"
def run(command, expected=0, **kwargs):
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180, **kwargs)
    operations.append({"command": command, "exitCode": result.returncode})
    assert result.returncode == expected, "Standalone fixture command failed; no application payload printed"
    return result.stdout

def script(source):
    return run(base + ["exec", "-T", "app", "python", "-"], input=source)

def live():
    for _ in range(60):
        try:
            if Client(port).request("/health/live")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Standalone did not become live")

try:
    run(base + ["up", "-d", "--no-build"])
    live()
    assert Client(port).request("/health/ready")[0] == 503
    assert Client(port).request("/")[0] == 503
    run(base + ["run", "--rm", "--no-deps", "app", "python", "-m", "app.migrate"])
    assert Client(port).request("/health/ready")[0] == 200
    run(base + ["run", "--rm", "--no-deps", "-T", "app", "python", "-m", "app.setup_admin"], expected=1)
    run(["docker", "run", "-d", "--name", sink_name, "--network", project + "_default", "--network-alias", "mailpit",
         "--read-only", "--user", "10001:10001", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
         "--memory", "128m", "--cpus", "0.5", "--pids-limit", "64", "--tmpfs", "/tmp:size=64m,mode=1777",
         INFRASTRUCTURE["mailpit"]])
    script(SEED)
    client = Client(port)
    status, page, _ = client.request("/e/1/book", "POST",
        {"name": "Synthetic Parent", "email": "parent@example.invalid", "klasse_id": 1, "shift_ids": [1], "privacy_accepted": 1})
    assert status == 200
    match = re.search(rb'/s/([A-Za-z0-9_-]{30,})', page)
    assert match
    parent = "/s/" + match[1].decode()
    assert (env["BASE_URL"] + parent).encode() in page
    results = probe(client, env["BASE_URL"], parent)
    mail_check = """import json,time,urllib.request
for attempt in range(50):
    messages=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/messages'))['messages']
    if messages: break
    time.sleep(.1)
assert messages
message=json.load(urllib.request.urlopen('http://mailpit:8025/api/v1/message/'+messages[0]['ID']))
from app.config import settings
assert settings.BASE_URL+'/s/' in message['Text']
print(json.dumps({'mailSinkDelivered':True,'mailLinkUsesBaseUrl':True}))
"""
    results.update(json.loads(script(mail_check)))
    # A fresh independent shift proves actual parallel booking rather than testing an already-full shift.
    script("""from app.database import SessionLocal
from app.models import Shift
from datetime import datetime
with SessionLocal() as db:
    db.add(Shift(station_id=1,start_time=datetime(2050,6,1,12),duration_min=60,required_count=1,sort_order=1));db.commit()
""")
    def book(index):
        return Client(port).request("/e/1/book", "POST",
            {"name": "Synthetic Parallel", "email": "parallel" + str(index) + "@example.invalid",
             "klasse_id": 1, "shift_ids": [2], "privacy_accepted": 1})[0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(book, range(8)))
    assert statuses == [200] * 8
    counts = json.loads(script("""import json
from app.database import SessionLocal
from app.models import Booking
from sqlalchemy import select,func
with SessionLocal() as db:
    print(json.dumps({'parallelBookings':db.execute(select(func.count()).select_from(Booking).where(Booking.shift_id==2)).scalar_one()}))
"""))
    assert counts["parallelBookings"] == 1
    results.update({"parallelRequests": 8, "parallelCapacity": 1, **counts})
    settled = script("""import json,time
from sqlalchemy import select,func
from app.database import SessionLocal
from app.models import EmailLog
for _ in range(600):
    with SessionLocal() as db:
        total=db.execute(select(func.count()).select_from(EmailLog)).scalar_one()
    if total>=9: break
    time.sleep(.1)
assert total>=9
print('settled')
""")
    assert settled.strip() == "settled"
    # Loss of SMTP must leave liveness/readiness healthy and produce a failed mail record.
    run(["docker", "stop", sink_name])
    assert Client(port).request("/wiederherstellen", "POST", {"email": "parent@example.invalid"})[0] == 200
    assert Client(port).request("/health/ready")[0] == 200
    failures = json.loads(script("""import json,time
from sqlalchemy import select,func
from app.database import SessionLocal
from app.models import EmailLog
for _ in range(50):
    with SessionLocal() as db:
        failed=db.execute(select(func.count()).select_from(EmailLog).where(EmailLog.success==False)).scalar_one()
    if failed: break
    time.sleep(.1)
print(json.dumps({'failedMailRecorded':bool(failed)}))
"""))
    assert failures["failedMailRecorded"]
    results.update({"smtpOutageDoesNotFailReadiness": True, **failures})
    # Recovery rotated the private capability. Read it privately for the restart/restore check.
    parent = "/s/" + script("""from sqlalchemy import select
from app.database import SessionLocal
from app.models import Participant
with SessionLocal() as db:
    print(db.execute(select(Participant.token).where(Participant.id==1)).scalar_one())
""").strip()
    before = json.loads(script(CONTRACT))
    run(base + ["restart", "app"])
    live()
    assert Client(port).request("/health/ready")[0] == 200
    assert Client(port).request(parent)[0] == 200
    assert json.loads(script(CONTRACT)) == before
    cid = run(base + ["ps", "-q", "app"]).strip()
    info = json.loads(run(["docker", "inspect", cid]))[0]
    assert info["Config"]["User"] == "10001:10001" and info["HostConfig"]["ReadonlyRootfs"]
    assert info["HostConfig"]["Init"] is True and not info["State"]["OOMKilled"]
    captured = subprocess.run(["docker", "logs", cid], capture_output=True, text=True, timeout=30)
    assert captured.returncode == 0
    logs = captured.stdout + captured.stderr
    assert parent[3:] not in logs and key.read_text() not in logs
    volume = next(item["Name"] for item in info["Mounts"] if item["Destination"] == "/app/data")
    (directory / "fixture.json").write_text(json.dumps({"project": project, "volume": volume, "parentPath": parent,
        "key": str(key), "database": before, "imageId": info["Image"]}))
    (ROOT / ".work/schulhelfer-latest-fixture").write_text(str(directory))
    report = {"scope": "standalone Compose without platform override; synthetic fixtures only",
        "imageId": info["Image"], "preMigrationBlocked": True, "explicitMigration": True,
        "setupWithoutTerminalRejected": True, "nonRootReadOnly": True, "initEnabled": True,
        "restartPreservesData": True, "noCapabilitiesInAccessLogs": True, **results}
    (out / "schulhelfer-standalone.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    subprocess.run(["docker", "rm", "-f", sink_name], capture_output=True, timeout=30)
    run(base + ["down"])
    (out / "schulhelfer-standalone-operations.json").write_text(json.dumps(operations, indent=2) + "\n")
