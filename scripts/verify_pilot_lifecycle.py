"""Test stop/start and preservation without another bootstrap or migration."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import Pilot
from schulplattform.postgres import Postgres
from schulplattform.state import StateError

pilot = Pilot(ROOT / ".work/pilot-v2")
if not pilot.ready(None):
    pilot.start()  # establish the running test fixture even after an external stop
state = pilot.directory / "state/installation.json"
state_before = state.read_bytes()
secret_files = [p for p in (pilot.directory / "secrets").iterdir() if not p.name.startswith(".")]
secret_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in secret_files}
database = pilot.inspect_service("schulwissen", "db")["Id"]
query = "SELECT count(*) FROM django_migrations"
migrations_before = Postgres(["docker", "exec", database], "schulwissen", "schulwissen").query(query)
report = None
try:
    pilot.stop()
    assert not pilot.ready(None)
    try:
        pilot.up()
    except StateError as error:
        assert "not ready" in str(error)
    else:
        raise AssertionError("Stopped installation was reported as ready")
    offset = pilot.log.stat().st_size
    pilot.start()
    assert pilot.ready(None)
    operations = [json.loads(line) for line in pilot.log.read_bytes()[offset:].decode().splitlines()]
    assert not any("platform_migrate" in item["command"] or "grundschul_woerterbuch.migrate" in item["command"]
                   for item in operations)
    assert state.read_bytes() == state_before
    assert secret_before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in secret_files}
    database = pilot.inspect_service("schulwissen", "db")["Id"]
    assert migrations_before == Postgres(["docker", "exec", database], "schulwissen", "schulwissen").query(query)
    report = {"stopAndStart": True, "stoppedUpFailsClosed": True, "noRepeatedMigrationOrBootstrap": True,
              "sameInstallationState": True, "sameSecrets": True, "sameMigrationCount": True,
              "readyAfterStart": True}
finally:
    pilot.stop()
    if report is not None:
        report["stoppedAfterTest"] = not pilot.ready(None)
        assert report["stoppedAfterTest"]
        (ROOT / "docs/implementation/evidence/pilot-lifecycle.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
