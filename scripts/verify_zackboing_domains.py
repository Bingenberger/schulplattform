"""Exercise canonical QR and WebSocket origins across local domain rollback."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.domains import Domains, DomainError
from schulplattform.pilot import Pilot, APP_PORTS
from schulplattform.proxy import caddyfile

pilot = Pilot(ROOT / ".work/pilot-v3")
original = pilot.current_domains()
assert original["zackboing"] == "quiz.localhost"
checks = []
fault = False

def preflight(old, new):
    if set(new) != set(original) or not all(x.endswith(".localhost") for x in new.values()):
        return False
    pending = pilot.quiz_control("prepare-stop")
    if pending["activeGames"]:
        pilot.quiz_control("cancel-stop")
        return False
    return True

def activate(domains):
    # Preserve the named data volume; only the runtime public origin changes.
    path = pilot.directory / "zackboing.yml"
    lines = path.read_text().splitlines()
    lines = ["      ZACKBOING_PUBLIC_URL: https://" + domains["zackboing"] + ":" + str(pilot.config["port"])
             if line.strip().startswith("ZACKBOING_PUBLIC_URL:") else line for line in lines]
    with path.open("w") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    pilot.compose_command("zackboing", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90", "app")
    config = caddyfile([(app, domain, APP_PORTS[app]) for app, domain in domains.items()])
    config = config.replace("admin localhost:2019", "admin localhost:2019\n  local_certs")
    with (pilot.directory / "Caddyfile").open("w") as stream:
        stream.write(config)
        stream.flush()
        os.fsync(stream.fileno())
    proxy = pilot.inspect_service("infra", "proxy")["Id"]
    for action in ("validate", "reload"):
        pilot.command(["docker", "exec", proxy, "caddy", action, "--config", "/etc/caddy/Caddyfile"])

def verify(domains):
    host = domains["zackboing"]
    for _ in range(30):
        try:
            if pilot.request(host, "/health/ready")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(0.2)
    else:
        return False
    if fault and host == "quiz-defekt.localhost":
        return False
    proxy = pilot.inspect_service("infra", "proxy")
    address = proxy["NetworkSettings"]["Networks"][pilot.project + "-infra_zack-proxy"]["IPAddress"]
    origin = "https://" + host + ":" + str(pilot.config["port"])
    old = "https://" + ("quiz.localhost" if host != "quiz.localhost" else "quiz-neu.localhost") + ":" + str(pilot.config["port"])
    command = ["docker", "run", "--rm", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--memory", "384m", "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:size=64m,mode=1777", "--network", pilot.project + "-infra_zack-proxy",
        "--add-host", host + ":" + address,
        "-e", "BASE_URL=https://" + host, "-e", "ZACKBOING_EXPECTED_ORIGIN=" + origin,
        "-e", "ZACKBOING_OLD_ORIGIN=" + old, "-e", "ZACKBOING_CONTRACT_MODE=probe",
        "-e", "NODE_EXTRA_CA_CERTS=/fixtures/root.crt",
        "-v", str(pilot.directory / "contract-fixtures/root.crt") + ":/fixtures/root.crt:ro",
        "zackboing-tests:0.1.0-dev", "node", "test/platform-contract.js"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        return False
    checks.append({"domain": host, **json.loads(result.stdout)})
    return True

driver = Domains(pilot.directory / "domain-transactions", original, "verwaltung.localhost",
                 preflight, activate, verify, operation_lock=pilot.directory / "state/installation.lock")
try:
    driver.change("zackboing", "quiz-neu.localhost")
    fault = True
    try:
        driver.change("zackboing", "quiz-defekt.localhost")
    except DomainError as error:
        assert "restored" in str(error)
    else:
        raise AssertionError("Failed verification was accepted")
    assert pilot.current_domains()["zackboing"] == "quiz-neu.localhost"
    report = {"scope": "local CA and synthetic account only", "successfulChange": True,
              "forcedFailureRolledBack": True, "checks": checks,
              "limits": ["No public DNS ownership/ACME proof", "No mail or OIDC flow in Zackboing"]}
finally:
    fault = False
    driver.change("zackboing", "quiz.localhost")
    pilot.quiz_control("cancel-stop")
report["originalRestored"] = True
(ROOT / "docs/implementation/evidence/zackboing-domains.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
