"""Standalone schulwissen Compose verification, without a platform override."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
project = "sp-wissen-standalone-" + secrets.token_hex(5)
directory = ROOT / ".work" / project
directory.mkdir(mode=0o700)
(directory / "docker-compose.yml").write_bytes((ROOT / ".work/apps/schulwissen/docker-compose.yml").read_bytes())
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
key, password = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
envfile = directory / ".env"
envfile.write_text("\n".join([
    "SW_SECRET_KEY=" + key, "POSTGRES_PASSWORD=" + password,
    "SW_ALLOWED_HOSTS=localhost,127.0.0.1",
    "SW_OEFFENTLICHE_URL=http://127.0.0.1:" + str(port),
    "SW_COOKIE_SECURE=false", "SW_HSTS_TAGE=0", "SW_WORKER=2", "SW_PORT=" + str(port),
]) + "\n")
envfile.chmod(0o600)
base = [str(ROOT / ".work/docker-compose"), "-p", project, "--env-file", str(envfile),
        "-f", str(directory / "docker-compose.yml")]
log = []
def run(args):
    result = subprocess.run(base + args, text=True, capture_output=True, timeout=180)
    output = (result.stdout + result.stderr).replace(key, "<redacted>").replace(password, "<redacted>")
    log.append("$ " + " ".join(base + args) + "\n" + output + f"\nexit_code={result.returncode}")
    if result.returncode:
        raise RuntimeError("Standalone command failed; see redacted log")
    return result.stdout

try:
    run(["up", "-d", "--no-build", "--wait", "db"])
    run(["run", "--rm", "app", "python", "manage.py", "platform_migrate"])
    run(["up", "-d", "--no-build"])
    for attempt in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
                assert response.status == 200
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError("Standalone did not become ready")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/anmelden", timeout=3) as response:
        assert response.status == 200
    # Restart must not automatically execute migrations.
    run(["restart", "app"])
    for attempt in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/ready", timeout=2) as response:
                assert response.status == 200
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError("Standalone restart did not become ready")
    report = {"scope": "standalone Compose only, without platform network/override",
              "project": project, "explicitMigration": True, "ready": True,
              "productionLoginPage": True, "restartReady": True}
    (ROOT / "docs/implementation/evidence/schulwissen-standalone.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
finally:
    try:
        run(["down"])
    finally:
        (ROOT / "docs/implementation/evidence/schulwissen-standalone.log").write_text("\n\n".join(log) + "\n")
