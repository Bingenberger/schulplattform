"""Restore a stopped standalone fixture through the generic SQLite snapshot engine."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from schulplattform.snapshot import checksum
from schulhelfer_fixture import Client, CONTRACT, probe

fixture_dir = Path((ROOT / ".work/schulhelfer-latest-fixture").read_text())
fixture = json.loads((fixture_dir / "fixture.json").read_text())
directory = fixture_dir / ("restore-" + secrets.token_hex(5))
directory.mkdir(mode=0o700)
project = "sp-helfer-restore-" + secrets.token_hex(5)
volume = project + "-data"
operations = []
PYTHON = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
helper = ["docker", "run", "--rm", "--read-only", "--network", "none", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges:true", "--user", "10001:10001", "--memory", "512m",
          "--cpus", "1", "--pids-limit", "64", "--tmpfs", "/tmp:size=256m,mode=1777",
          "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/helper",
          "-v", str(ROOT / "schulplattform") + ":/helper/schulplattform:ro"]

def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, timeout=180, **kwargs)
    operations.append({"command": command, "exitCode": result.returncode})
    assert result.returncode == 0, "Restore fixture command failed"
    return result.stdout

# The source Compose was stopped by the standalone verifier. Refuse live writers.
containers = json.loads(run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=" + fixture["project"],
                             "--format", "{{json .ID}}"]).decode() or '""')
assert not containers
archive = directory / "snapshot.tar"
command = helper + ["-v", fixture["volume"] + ":/data:ro", PYTHON, "python", "-m", "schulplattform.snapshot",
                    "create", "/data", "--database", "app.db"]
fd = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "wb") as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE, timeout=180)
operations.append({"command": command, "exitCode": result.returncode})
assert result.returncode == 0
digest = checksum(archive)
run(["docker", "volume", "create", volume])
run(["docker", "run", "--rm", "--read-only", "--network", "none", "--cap-drop", "ALL",
     "--security-opt", "no-new-privileges:true", "-v", volume + ":/app/data",
     "schulhelfer:0.1.0-dev", "python", "-c", "import os;assert os.access('/app/data',os.W_OK)"])
source = """import shutil,sys
from pathlib import Path
from schulplattform.snapshot import restore
path=Path('/tmp/snapshot.tar')
with path.open('wb') as stream: shutil.copyfileobj(sys.stdin.buffer,stream)
restore(path,Path('/data'),sys.argv[1])
"""
command = helper + ["-i", "-v", volume + ":/data", PYTHON, "python", "-c", source, digest]
with archive.open("rb") as stream:
    run(command, stdin=stream)
with archive.open("rb") as stream:
    rejected = subprocess.run(command, stdin=stream, capture_output=True, timeout=180)
assert rejected.returncode != 0
operations.append({"action": "nonempty-restore", "exitCode": rejected.returncode})
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
override = directory / "restore.json"
override.write_text(json.dumps({"volumes": {"data": {"external": True, "name": volume}}}))
env = os.environ | {"SCHULHELFER_SECRET_FILE": fixture["key"], "SCHULHELFER_PORT": str(port),
                    "BASE_URL": "http://127.0.0.1:" + str(port)}
compose = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(ROOT / ".work/apps/schulhelfer/docker-compose.yml"),
           "-f", str(override)]
out = ROOT / "docs/implementation/evidence"
try:
    run(compose + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "90"], env=env)
    checks = probe(Client(port), env["BASE_URL"], fixture["parentPath"])
    assert Client(port).request("/s/invalid-synthetic-capability")[0] == 404
    contract = json.loads(run(compose + ["exec", "-T", "app", "python", "-"], input=CONTRACT.encode(), env=env))
    assert contract == fixture["database"]
    ownership_source = """import os,json
print(json.dumps([{'uid':os.stat(p).st_uid,'gid':os.stat(p).st_gid,'mode':os.stat(p).st_mode&511} for p in ['/app/data','/app/data/app.db']]))
"""
    ownership = json.loads(run(compose + ["exec", "-T", "app", "python", "-"], input=ownership_source.encode(), env=env))
    assert ownership == [{"uid": 10001, "gid": 10001, "mode": 0o700}, {"uid": 10001, "gid": 10001, "mode": 0o600}]
    report = {"scope": "local synthetic standalone SQLite restore with original test configuration/key",
              "imageId": fixture["imageId"], "archiveSha256": digest,
              "emptyNewVolume": True, "sqliteOnlineBackup": True, "sourceStopped": True,
              "schemaAndForeignKeys": True, "idsBookingsAndAdminOwnershipPreserved": True,
              "noMigrationOrBootstrap": True, "invalidParentLinkDenied": True,
              "nonemptyRestoreRejected": True, "fileOwnership": ownership, **checks}
    (out / "schulhelfer-restore.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    run(compose + ["down"], env=env)
    (out / "schulhelfer-restore-operations.json").write_text(json.dumps(operations, indent=2) + "\n")
