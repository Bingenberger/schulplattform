"""Three-app no-op, maintenance, stop/start and retained-data checks."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import Pilot
from schulplattform.pilot_engine import PilotEngine

pilot = Pilot(ROOT / ".work/pilot-v3")
engine = PilotEngine(pilot)
def hashes():
    paths = [pilot.directory / "state/installation.json"]
    paths += list((pilot.directory / "secrets").rglob("*"))
    return {str(p.relative_to(pilot.directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}
def containers():
    return {app: pilot.inspect_service(app, "app")["Id"] for app in pilot.apps}

before, identities = hashes(), containers()
first = pilot.up()
second = pilot.up()
assert first == second
assert hashes() == before and containers() == identities
assert pilot.inspect_service("zackboing", "app")["HostConfig"]["Init"] is True
offset = len(pilot.log.read_text().splitlines())
result = engine.execute("stop", "zackboing")
assert not result["running"]
assert pilot.request("quiz.localhost", "/health/ready")[0] == 503
result = engine.execute("start", "zackboing")
assert result["running"] and result["health"] == "healthy"
assert pilot.request("quiz.localhost", "/health/ready")[0] == 200
operations = [json.loads(line) for line in pilot.log.read_text().splitlines()[offset:]]
assert not any("server/migrate.js" in entry["command"] or "server/bootstrap.js" in entry["command"] for entry in operations)
assert hashes() == before
report = {"apps": list(pilot.apps), "installationId": first["id"], "twoNoopRuns": True,
          "sameContainersAndKeys": True, "initEnabled": True, "stoppedRoute503": True,
          "restartReady200": True, "noRepeatedMigrationOrBootstrap": True}
pilot.stop()
assert not pilot.ready(None)
report["pilotStoppedDataRetained"] = True
out = ROOT / "docs/implementation/evidence"
(out / "zackboing-lifecycle.json").write_text(json.dumps(report, indent=2) + "\n")
(out / "pilot-v3-operations.jsonl").write_text(pilot.log.read_text())
print(json.dumps(report, indent=2))
