"""Verify a third pilot app with real TLS, QR and browser-origin WebSockets."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.deployment import Gate, signed_request
from schulplattform.pilot import Pilot
from schulplattform.pilot_engine import PilotEngine

pilot = Pilot(ROOT / ".work/pilot-v3")
fixtures = pilot.directory / "contract-fixtures"
fixtures.mkdir(mode=0o700, exist_ok=True)
certificate = fixtures / "root.crt"
if not certificate.exists():
    certificate.write_bytes((pilot.directory / "root.crt").read_bytes())
    certificate.chmod(0o444)
else:
    assert certificate.read_bytes() == (pilot.directory / "root.crt").read_bytes()
token_file = fixtures / "bootstrap-token"
if token_file.exists():
    token = token_file.read_text().strip()
else:
    token = pilot.compose_command("zackboing", "exec", "-T", "app", "node", "-e",
        "process.stdout.write(require('./server/bootstrap').issueBootstrap());").strip()
    token_file.write_text(token)
    token_file.chmod(0o444)
proxy = pilot.inspect_service("infra", "proxy")
address = proxy["NetworkSettings"]["Networks"][pilot.project + "-infra_zack-proxy"]["IPAddress"]
key = secrets.token_bytes(48)
gate = Gate(fixtures / "control-audit.sqlite3", key, PilotEngine(pilot))
origin = "https://quiz.localhost:" + str(pilot.config["port"])
command = ["docker", "run", "--rm", "-i", "--read-only", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true", "--memory", "384m", "--cpus", "1", "--pids-limit", "128",
    "--tmpfs", "/tmp:size=64m,mode=1777", "--network", pilot.project + "-infra_zack-proxy",
    "--add-host", "quiz.localhost:" + address,
    "-e", "BASE_URL=https://quiz.localhost", "-e", "ZACKBOING_EXPECTED_ORIGIN=" + origin,
    "-e", "ZACKBOING_TEST_EXISTING=" + os.environ.get("ZACKBOING_TEST_EXISTING", "0"),
    "-e", "NODE_EXTRA_CA_CERTS=/fixtures/root.crt",
    "-e", "ZACKBOING_TEST_BOOTSTRAP_FILE=/fixtures/bootstrap-token",
    "-v", str(certificate) + ":/fixtures/root.crt:ro", "-v", str(token_file) + ":/fixtures/bootstrap-token:ro",
    "zackboing-tests:0.1.0-dev", "node", "test/platform-contract.js"]
output = []
report = None
process = subprocess.Popen(command, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    for line in process.stdout:
        output.append(line)
        if line.strip() == "GAME_ACTIVE":
            blocked = gate.dispatch(signed_request(key, "stop", "zackboing"))
            assert blocked == {"ok": False, "error": "busy"}
            assert PilotEngine(pilot).status("zackboing")["running"]
            backend = pilot.inspect_service("zackboing", "app")
            source = "const db=require('./server/db');db.prepare(\"UPDATE sessions SET created_at='2000-01-01 00:00:00'\").run();db.close();"
            pilot.command(["docker", "exec", backend["Id"], "node", "-e", source])
            process.stdin.write("RESUME\n")
            process.stdin.flush()
        elif line.startswith("{"):
            report = json.loads(line)
    diagnostics = process.stderr.read()
    output.append(diagnostics)
    code = process.wait(timeout=120)
    assert code == 0, "TLS/WebSocket contract failed; no credentials printed"
    assert report and report["gameCompleted"]
    assert pilot.quiz_control("prepare-stop")["activeGames"] == 0
    pilot.quiz_control("cancel-stop")
    image = pilot.inspect_service("zackboing", "app")
    assert not any(image["NetworkSettings"]["Ports"].values())
    report.update({"imageId": image["Image"], "stopDuringGameBlocked": True,
                   "backendPortsPrivate": True, "nodeLts": "22.23.4"})
    (ROOT / "docs/implementation/evidence/zackboing-platform.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
    (ROOT / "docs/implementation/evidence/zackboing-platform-client.log").write_text(
        "$ " + " ".join(command) + "\n" + "".join(output).replace(token, "<redacted>") +
        "\nexit_code=" + str(process.returncode) + "\n")
