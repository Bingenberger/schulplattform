"""Restore synthetic school knowledge data into fresh PostgreSQL storage."""
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.pilot import Pilot, INFRASTRUCTURE
from schulplattform.postgres import Postgres

pilot = Pilot(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".work/pilot-v2")
out = ROOT / "docs/implementation/evidence"
source_id = pilot.inspect_service("schulwissen", "db")["Id"]
app_id = pilot.inspect_service("schulwissen", "app")["Id"]
fixture = """
import os, json, secrets
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schulwissen.einstellungen")
import django
django.setup()
from django.contrib.auth.models import Group
from django.test import Client
from kern.models import Nutzer, ROLLE_ADMINISTRATION
user, created = Nutzer.objects.get_or_create(email="restore-test@example.invalid",
    defaults={"anzeigename": "Synthetic Restore", "is_active": True})
password = secrets.token_urlsafe(24)
user.set_password(password)
user.save()
group = Group.objects.get(name=ROLLE_ADMINISTRATION)
user.groups.add(group)
client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
client.get("/anmelden")
token = client.cookies["csrftoken"].value
assert client.post("/anmelden", {"username": user.email, "password": password}).status_code == 403
response = client.post("/anmelden", {"username": user.email, "password": password, "csrfmiddlewaretoken": token})
assert response.status_code == 302, response.status_code
assert client.get("/").status_code == 200
print(json.dumps({"userId": user.pk, "roleId": group.pk, "localLogin": True, "missingCsrfDenied": True}))
"""
fixture_result = json.loads(pilot.command(["docker", "exec", "-i", app_id, "python", "-"], input=fixture))
source = Postgres(["docker", "exec", source_id], "schulwissen", "schulwissen")
backup = pilot.directory / ("restore-test-" + secrets.token_hex(4) + ".dump")
metadata = source.snapshot(backup)
target_name = pilot.project + "-restore-" + secrets.token_hex(4)
volume_name = target_name + "-data"
runtime = pilot.directory / "runtime"
target_id = None
try:
    target_id = pilot.command(["docker", "run", "-d", "--name", target_name, "--network", "none",
        "--memory", "256m", "--cpus", "1",
        "-e", "POSTGRES_PASSWORD_FILE=/run/secrets/admin_password",
        "-e", "POSTGRES_USER=postgres", "-e", "POSTGRES_DB=postgres",
        "-v", volume_name + ":/var/lib/postgresql/data",
        "-v", str(runtime / "postgres-admin") + ":/run/secrets/admin_password:ro",
        "-v", str(runtime / "postgres-app") + ":/run/secrets/app_db_password:ro",
        "-v", str(pilot.directory / "init-postgres.sh") + ":/docker-entrypoint-initdb.d/01-app.sh:ro",
        INFRASTRUCTURE["postgres"]]).strip()
    for attempt in range(60):
        probe = subprocess.run(["docker", "exec", target_id, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if probe.returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Restore PostgreSQL not ready")
    target = Postgres(["docker", "exec", "-i", target_id], "schulwissen", "schulwissen")
    assert target.restore_into_empty(backup, metadata, pilot.directory / "restore-locks")
    for sql in [
        "SELECT count(*) FROM django_migrations",
        "SELECT count(*) FROM pg_constraint WHERE contype='f' AND convalidated",
        "SELECT id,email FROM kern_nutzer WHERE email='restore-test@example.invalid'",
        "SELECT nutzer_id,group_id FROM kern_nutzer_groups ORDER BY nutzer_id,group_id",
        "SELECT tablename,tableowner FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
    ]:
        assert source.query(sql) == target.query(sql), sql
    assert target.query("SELECT rolsuper OR rolcreatedb OR rolcreaterole FROM pg_roles WHERE rolname=current_user") == "f"
    try:
        target.restore_into_empty(backup, metadata, pilot.directory / "restore-locks")
    except ValueError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("Nonempty restore target accepted")
    report = {"scope": "local PostgreSQL restore into a new network-isolated container and empty volume",
              "fixture": fixture_result, "archive": metadata, "sameMigrationCount": True,
              "sameForeignKeys": True, "sameOwnership": True, "sameUserAndRoleIds": True,
              "nonemptyTargetRejected": True, "targetVolume": volume_name,
              "limits": "No files/secrets/offsite restore; restored app HTTP not started."}
    (out / "pilot-postgres-restore.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    if target_id:
        pilot.command(["docker", "stop", target_id])
