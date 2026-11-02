"""Standalone Node-LTS container, actual game tests and restart without platform."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
project = "sp-zack-standalone-" + secrets.token_hex(5)
directory = ROOT / ".work" / project
directory.mkdir(mode=0o700)
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
env = os.environ | {"ZACKBOING_PORT": str(port), "ZACKBOING_PUBLIC_URL": "http://127.0.0.1:" + str(port)}
base = [str(ROOT / ".work/docker-compose"), "-p", project, "-f", str(ROOT / ".work/apps/zackboing/docker-compose.yml")]
operations = []
out = ROOT / "docs/implementation/evidence"

def run(argv, expected=0, timeout=180):
    result = subprocess.run(argv, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    operations.append({"command": argv, "exitCode": result.returncode})
    if result.returncode != expected:
        # Avoid logging arbitrary app output which might contain credentials.
        raise RuntimeError("Standalone command failed; inspect non-secret operation metadata")
    return result.stdout

def status(path, method="GET"):
    try:
        with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:" + str(port) + path, method=method),
                                    timeout=3) as response:
            return response.status
    except urllib.error.HTTPError as response:
        return response.code

def wait_live():
    for _ in range(60):
        try:
            if status("/health/live") == 200:
                return
        except OSError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Zackboing did not become live")

try:
    run(base + ["up", "-d", "--no-build"])
    wait_live()
    assert status("/health/ready") == 503
    run(base + ["run", "--rm", "--no-deps", "app", "node", "server/migrate.js"])
    assert status("/health/ready") == 200
    assert status("/api/admin/users") == 401
    assert status("/api/register", "POST") == 400
    assert status("/_platform/prepare-stop", "POST") == 403
    run(base + ["run", "--rm", "--no-deps", "-T", "app", "node", "server/bootstrap.js"], expected=1)
    pristine = run(base + ["exec", "-T", "app", "node", "-e",
        "const db=require('./server/db');console.log(db.getSetting('_bootstrap_hash')===undefined);db.close();"])
    assert pristine.strip() == "true"
    token = run(base + ["exec", "-T", "app", "node", "-e",
        "process.stdout.write(require('./server/bootstrap').issueBootstrap());"]).strip()
    token_file = directory / "bootstrap-token"
    token_file.write_text(token)
    token_file.chmod(0o444)
    command = ["docker", "run", "--rm", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--memory", "384m", "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:size=64m,mode=1777", "--network", project + "_default", "--network-alias", "fixture",
        "-e", "BASE_URL=http://app:3000", "-e", "ZACKBOING_TEST_BOOTSTRAP_FILE=/fixtures/bootstrap-token",
        "-v", str(token_file) + ":/fixtures/bootstrap-token:ro",
        "zackboing-tests:0.1.0-dev", "node", "test/run-fixtures.js"]
    result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=600)
    operations.append({"command": command, "exitCode": result.returncode})
    output = (result.stdout + result.stderr).replace(token, "<redacted>")
    (out / "zackboing-e2e.log").write_text("$ " + " ".join(command) + "\n" + output + f"\nexit_code={result.returncode}\n")
    if result.returncode:
        raise RuntimeError("Zackboing game tests failed; see redacted log")
    assert "NICHT AUSGEFÜHRT" not in output
    assert "<redacted>" in output  # capability fields are deliberately withheld in check details
    cid = run(base + ["ps", "-q", "app"]).strip()
    info = json.loads(run(["docker", "inspect", cid]))[0]
    assert info["Config"]["User"] == "10001:10001"
    assert info["HostConfig"]["ReadonlyRootfs"]
    assert info["State"]["OOMKilled"] is False
    run(base + ["restart", "app"])
    wait_live()
    assert status("/health/ready") == 200
    stable = json.loads(run(base + ["exec", "-T", "app", "node", "-e",
        "const db=require('./server/db');console.log(JSON.stringify({version:db.pragma('user_version',{simple:true}),users:db.prepare('select count(*) as n from users').get().n,registration:db.getSetting('registration_open')}));db.close();"]))
    assert stable["version"] == 1 and stable["users"] >= 2 and stable["registration"] == "0"
    report = {"project": project, "imageId": info["Image"], "noMigrationOnImport": True,
              "liveBeforeMigration": True, "readinessBlockedBeforeMigration": True,
              "explicitMigration": True, "bootstrapWithoutTerminalRejected": True,
              "privateControlNotPublic": True, "gameChecks": output.count("✅"),
              "noSkippedChecks": True, "restartKeepsUsersAndSchema": True, "nonRootReadOnly": True,
              "scope": "standalone Compose only, local fixtures, no platform override"}
    (out / "zackboing-standalone.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    try:
        run(base + ["down"])
    finally:
        (out / "zackboing-standalone-operations.json").write_text(json.dumps(operations, indent=2) + "\n")
