"""Verify the local two-app pilot, without actual users or external mail."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import Pilot

pilot = Pilot(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".work/pilot-v2")
out = ROOT / "docs/implementation/evidence"
out.mkdir(parents=True, exist_ok=True)
state_path = pilot.directory / "state/installation.json"
before = state_path.read_bytes()
before_mtime = state_path.stat().st_mtime_ns
secrets_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  (pilot.directory / "secrets").iterdir() if not p.name.startswith(".")}
containers_before = {app: pilot.inspect_service(app, "app")["Id"] for app in ("gswb", "schulwissen")}
result = pilot.up()
assert state_path.read_bytes() == before
assert state_path.stat().st_mtime_ns == before_mtime
assert containers_before == {app: pilot.inspect_service(app, "app")["Id"] for app in ("gswb", "schulwissen")}
assert secrets_before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         (pilot.directory / "secrets").iterdir() if not p.name.startswith(".")}

def app_script(source):
    cid = pilot.inspect_service("schulwissen", "app")["Id"]
    return pilot.command(["docker", "exec", "-i", cid, "python", "-"], input=source)

# No credentials occur in arguments or captured output.
privileges = json.loads(app_script("""
import os, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schulwissen.einstellungen")
import django
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT current_user, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
    row = cursor.fetchone()
    cursor.execute("SELECT has_database_privilege(current_user, 'postgres', 'CONNECT')")
    postgres_access = cursor.fetchone()[0]
print(json.dumps({"role": row[0], "superuser": row[1], "createdb": row[2], "createrole": row[3], "postgresConnect": postgres_access}))
"""))
assert privileges == {"role": "schulwissen", "superuser": False, "createdb": False,
                      "createrole": False, "postgresConnect": False}, privileges

# Read sink state before sending, so an older test message cannot produce a false pass.
mail_source = """
import os, json, urllib.request
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schulwissen.einstellungen")
import django
django.setup()
from django.core.mail import send_mail
from django.conf import settings
assert settings.EMAIL_HOST == "mailpit"
assert settings.EMAIL_PORT == 1025
assert settings.EMAIL_USE_TLS is False
before = json.load(urllib.request.urlopen("http://mailpit:8025/api/v1/messages"))["total"]
sent = send_mail("Synthetic platform acceptance", "Only the isolated mail sink receives this message.",
                "platform@example.invalid", ["synthetic@example.invalid"])
after = json.load(urllib.request.urlopen("http://mailpit:8025/api/v1/messages"))["total"]
assert sent == 1 and after == before + 1
print(json.dumps({"sent": sent, "newSinkMessages": after-before}))
"""
mail = json.loads(app_script(mail_source))
verification = json.loads((pilot.directory / "verified.json").read_text())
report = {"scope": "local two-app pilot, not production acceptance",
          "installation": result["id"], "secondRunNoop": True,
          "tlsAndAccess": verification["checks"], "databasePrivileges": privileges,
          "mailSink": mail}
(out / "pilot-checks.json").write_text(json.dumps(report, indent=2) + "\n")
(out / "pilot-operations.jsonl").write_bytes(pilot.log.read_bytes())
print(json.dumps(report, indent=2))
