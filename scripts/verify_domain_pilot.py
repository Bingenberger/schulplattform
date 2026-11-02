"""Live local domain change with TLS, app URL, CSRF and sink-link checks."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.domains import Domains, DomainError
from schulplattform.pilot import Pilot
from schulplattform.proxy import caddyfile

pilot = Pilot(ROOT / ".work/pilot-v2")
out = ROOT / "docs/implementation/evidence"
original = {"schulwissen": "wissen.localhost", "gswb": "woerter.localhost"}
fault = {"enabled": False}
checks = []


def preflight(old, new):
    # Deliberately local: no claim of public DNS ownership or ACME validation.
    return set(new) == set(original) and all(domain.endswith(".localhost") for domain in new.values())


def activate(domains):
    config = caddyfile([(app, domain, 8000) for app, domain in domains.items()])
    config = config.replace("admin localhost:2019", "admin localhost:2019\n  local_certs")
    # This file is bind-mounted. Caddy only adopts it after explicit validation/reload.
    with (pilot.directory / "Caddyfile").open("w") as stream:
        stream.write(config)
        stream.flush()
        os.fsync(stream.fileno())
    proxy = pilot.inspect_service("infra", "proxy")["Id"]
    pilot.command(["docker", "exec", proxy, "caddy", "validate", "--config", "/etc/caddy/Caddyfile"])
    env = pilot.directory / "wissen.env"
    lines = []
    for line in env.read_text().splitlines():
        if line.startswith("SW_ALLOWED_HOSTS="):
            line = "SW_ALLOWED_HOSTS=" + domains["schulwissen"] + ",localhost"
        elif line.startswith("SW_OEFFENTLICHE_URL="):
            line = "SW_OEFFENTLICHE_URL=https://" + domains["schulwissen"] + ":" + str(pilot.config["port"])
        lines.append(line)
    with env.open("w") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    pilot.compose_command("schulwissen", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")
    pilot.command(["docker", "exec", proxy, "caddy", "reload", "--config", "/etc/caddy/Caddyfile"])


def verify(domains):
    for attempt in range(30):
        try:
            assert pilot.request(domains["schulwissen"], "/health/ready")[0] == 200
            assert pilot.request(domains["schulwissen"], "/anmelden")[0] == 200
            assert pilot.request(domains["schulwissen"], "/anmelden", "POST")[0] == 403
            break
        except (OSError, AssertionError):
            time.sleep(0.2)
    else:
        return False
    if fault["enabled"] and domains["schulwissen"] == "wissen-defekt.localhost":
        return False
    # Generate a password-reset message with the app's actual request/form flow.
    host = domains["schulwissen"] + ":" + str(pilot.config["port"])
    source = """
import os, json, urllib.request
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schulwissen.einstellungen")
import django
django.setup()
from django.test import Client
from django.conf import settings
host = HOST_VALUE
origin = "https://" + host
assert settings.OEFFENTLICHE_URL == origin
client = Client(enforce_csrf_checks=True, HTTP_HOST=host)
client.get("/passwort-vergessen", secure=True)
token = client.cookies["csrftoken"].value
response = client.post("/passwort-vergessen", {"email": "restore-test@example.invalid", "csrfmiddlewaretoken": token},
                       secure=True, HTTP_REFERER=origin + "/passwort-vergessen")
assert response.status_code == 302
messages = json.load(urllib.request.urlopen("http://mailpit:8025/api/v1/messages"))["messages"]
message = json.load(urllib.request.urlopen("http://mailpit:8025/api/v1/message/" + messages[0]["ID"]))
assert origin in message["Text"]
print(json.dumps({"mailLinkMatchesDomain": True}))
""".replace("HOST_VALUE", repr(host))
    app = pilot.inspect_service("schulwissen", "app")["Id"]
    result = json.loads(pilot.command(["docker", "exec", "-i", app, "python", "-"], input=source))
    checks.append({"domain": domains["schulwissen"], "tls": True, "loginPage": True,
                   "missingCsrfDenied": True, **result})
    return True


driver = Domains(pilot.directory / "domain-transactions", original, "verwaltung.localhost",
                 preflight, activate, verify)
try:
    driver.change("schulwissen", "wissen-neu.localhost")
    fault["enabled"] = True
    try:
        driver.change("schulwissen", "wissen-defekt.localhost")
    except DomainError as exc:
        assert "restored" in str(exc), str(exc)
    else:
        raise AssertionError("Forced domain failure was accepted")
    current = json.loads(driver.path.read_text())
    assert current["domains"]["schulwissen"] == "wissen-neu.localhost"
    assert pilot.request("wissen-neu.localhost", "/health/ready")[0] == 200
    report = {"scope": "local TLS/domain rollback with synthetic mail only",
              "successfulChange": True, "forcedFailureRolledBack": True, "checks": checks,
              "limits": ["No public DNS/ACME ownership test", "No OIDC callbacks configured",
                         "No QR function in this tested flow", "Recovery through local CLI, not management web domain"]}
    (out / "pilot-domain-rollback.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
finally:
    # Restore the pilot's original domain as a transaction; no hidden state reset.
    fault["enabled"] = False
    driver.change("schulwissen", "wissen.localhost")
