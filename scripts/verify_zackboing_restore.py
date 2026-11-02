"""Local combined snapshot, empty-volume restore and restored-app HTTP proof."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import Pilot
from schulplattform.snapshot import checksum
from schulplattform.storage import exclusive

PYTHON = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
pilot = Pilot(ROOT / ".work/pilot-v3")
out = ROOT / "docs/implementation/evidence"
directory = pilot.directory / ("restore-" + secrets.token_hex(5))
directory.mkdir(mode=0o700)
operations = []

def run(command, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, **kwargs)
    operations.append({"command": command, "exitCode": result.returncode})
    if result.returncode:
        raise RuntimeError("Restore fixture command failed; see non-secret operation metadata")
    return result.stdout

def database_contract():
    source = """const db=require('./server/db');console.log(JSON.stringify({
version:db.pragma('user_version',{simple:true}),
users:db.prepare('select id,role from users order by id').all(),
quizzes:db.prepare('select id,user_id from quizzes order by id').all(),
foreignKeys:db.pragma('foreign_key_check'),registration:db.getSetting('registration_open')
}));db.close();"""
    return json.loads(pilot.compose_command("zackboing", "exec", "-T", "app", "node", "-e", source))

before = database_contract()
backend = pilot.inspect_service("zackboing", "app")
volume = next(item["Name"] for item in backend["Mounts"] if item["Destination"] == "/data")
project = "sp-zack-restore-" + secrets.token_hex(5)
restored_volume = project + "-data"
helper = ["docker", "run", "--rm", "--read-only", "--network", "none", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges:true", "--user", "10001:10001", "--memory", "512m",
          "--cpus", "1", "--pids-limit", "64", "--tmpfs", "/tmp:size=256m,mode=1777",
          "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/helper",
          "-v", str(ROOT / "schulplattform") + ":/helper/schulplattform:ro"]
archive = directory / "snapshot.tar"
with exclusive(pilot.directory / "state/installation.lock"):
    pending = pilot.quiz_control("prepare-stop")
    if pending["activeGames"]:
        pilot.quiz_control("cancel-stop")
        raise RuntimeError("Active games must finish before consistent snapshot")
    try:
        pilot.refresh_routes({"zackboing"})
        pilot.compose_command("zackboing", "stop", "--timeout", "130", "app")
        command = helper + ["-v", volume + ":/data:ro", PYTHON, "python", "-m", "schulplattform.snapshot",
                           "create", "/data", "--database", "zackboing.db", "--directory", "uploads"]
        fd = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, timeout=180)
        operations.append({"command": command, "exitCode": result.returncode})
        assert result.returncode == 0, "Combined snapshot failed"
    finally:
        pilot.compose_command("zackboing", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90", "app")
        pilot.quiz_control("cancel-stop")
        pilot.refresh_routes()
digest = checksum(archive)
run(["docker", "volume", "create", restored_volume])
# Docker's initial volume copy-up supplies the image's /data ownership, no root helper.
run(["docker", "run", "--rm", "--read-only", "--network", "none", "--cap-drop", "ALL",
     "--security-opt", "no-new-privileges:true", "-v", restored_volume + ":/data",
     "zackboing:0.1.0-dev", "node", "-e", "require('fs').accessSync('/data',require('fs').constants.W_OK)"])
restore_source = """import shutil,sys
from pathlib import Path
from schulplattform.snapshot import restore
path=Path('/tmp/snapshot.tar')
with path.open('wb') as stream:
    shutil.copyfileobj(sys.stdin.buffer,stream)
restore(path,Path('/data'),sys.argv[1])
"""
command = helper + ["-i", "-v", restored_volume + ":/data", PYTHON, "python", "-c", restore_source, digest]
with archive.open("rb") as stream:
    run(command, stdin=stream)
# Repeating a restore into the now nonempty target must fail before writing.
with archive.open("rb") as stream:
    result = subprocess.run(command, stdin=stream, capture_output=True, timeout=180)
assert result.returncode != 0
operations.append({"action": "repeat-restore-nonempty", "exitCode": result.returncode})
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
override = directory / "restored.json"
override.write_text(json.dumps({"volumes": {"data": {"external": True, "name": restored_volume}}}))
env = os.environ | {"ZACKBOING_PORT": str(port), "ZACKBOING_PUBLIC_URL": "http://127.0.0.1:" + str(port)}
compose = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(ROOT / ".work/apps/zackboing/docker-compose.yml"),
           "-f", str(override)]
cookie = ""
def api(path, method="GET", data=None):
    headers = {"Cookie": cookie}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request("http://127.0.0.1:" + str(port) + path, method=method,
                                     headers=headers, data=json.dumps(data).encode() if data is not None else None)
    try:
        return urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        return error

try:
    run(compose + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "90"], env=env)
    assert api("/health/ready").status == 200
    assert api("/api/admin/users").status == 401
    login = api("/api/login", "POST", {"email": "tls-admin@example.invalid", "password": "synthetic-zack-password"})
    assert login.status == 200
    cookie = login.headers["Set-Cookie"].split(";")[0]
    assert json.load(login)["user"]["id"] == 1
    assert api("/api/admin/users").status == 200
    media = json.loads((out / "zackboing-platform.json").read_text())["mediaUrl"]
    media_bytes = api(media).read()
    expected = __import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    assert media_bytes == expected
    login = api("/api/login", "POST", {"email": "tls-teacher@example.invalid", "password": "synthetic-teacher-password"})
    assert login.status == 200
    cookie = login.headers["Set-Cookie"].split(";")[0]
    teacher = json.load(login)["user"]
    assert teacher["role"] == "teacher" and teacher["id"] == 2
    assert api("/api/admin/users").status == 403
    assert api("/api/register", "POST", {"email": "other@example.invalid", "name": "Other", "password": "synthetic-password"}).status == 403
    check = """const db=require('./server/db');console.log(JSON.stringify({
version:db.pragma('user_version',{simple:true}),users:db.prepare('select id,role from users order by id').all(),
quizzes:db.prepare('select id,user_id from quizzes order by id').all(),foreignKeys:db.pragma('foreign_key_check'),
registration:db.getSetting('registration_open')}));db.close();"""
    after = json.loads(run(compose + ["exec", "-T", "app", "node", "-e", check], env=env))
    assert before == after
    permissions = """const fs=require('fs');const p=['/data','/data/zackboing.db','/data/uploads'];console.log(JSON.stringify(p.map(x=>{const s=fs.statSync(x);return {uid:s.uid,gid:s.gid,mode:s.mode&511};})));"""
    modes = json.loads(run(compose + ["exec", "-T", "app", "node", "-e", permissions], env=env))
    assert all(x["uid"] == 10001 and x["gid"] == 10001 for x in modes)
    assert [x["mode"] for x in modes] == [0o700, 0o600, 0o700]
    report = {"scope": "local synthetic combined SQLite/media snapshot; no offsite backup",
              "archiveSha256": digest, "sourceImage": backend["Image"],
              "emptyNewVolume": True, "sqliteOnlineBackup": True, "writersStopped": True,
              "noMigrationOrBootstrapOnRestore": True, "restoredAppReady": True,
              "schemaRolesAndOwnershipPreserved": True, "database": before,
              "mediaSha256": hashlib.sha256(media_bytes).hexdigest(),
              "teacherAdminAccessDenied": True, "anonymousAdminDenied": True,
              "registrationStillClosed": True, "nonemptyRestoreRejected": True, "fileOwnership": modes}
    (out / "zackboing-restore.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    run(compose + ["down"], env=env) # keep the restored volume for review
    (out / "zackboing-restore-operations.json").write_text(json.dumps(operations, indent=2) + "\n")
