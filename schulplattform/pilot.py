"""Local, isolated selected-app integration environment; not a production installer.

Uses the real standalone Compose files plus generated overrides. Only Caddy's
TLS test port is published, on host loopback. No external SMTP or DNS changes.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import time
import uuid

from .proxy import caddyfile
from .secrets import SecretStore
from .state import Installation, Step, StateError
from .storage import atomic_json, exclusive

ROOT = Path(__file__).resolve().parents[1]
INFRASTRUCTURE = {
    "postgres": "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab",
    "caddy": "caddy:2.11.7-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5",
    "mailpit": "axllent/mailpit:v1.33.0@sha256:9b3a463be15354c0f0eba91697d80e3e0d8a5623ef0e627cacc836bc17fd5231",
}


APP_PORTS = {"gswb": 8000, "schulwissen": 8000, "zackboing": 3000, "schulhelfer": 8000}
DEFAULT_DOMAINS = {"gswb": "woerter.localhost", "schulwissen": "wissen.localhost", "zackboing": "quiz.localhost", "schulhelfer": "helfer.localhost"}
APP_SELECTIONS = (("gswb", "schulwissen"), ("gswb", "schulwissen", "zackboing"),
                  ("gswb", "schulwissen", "zackboing", "schulhelfer"))

class Pilot:
    def __init__(self, directory, apps=None):
        if apps is not None and tuple(apps) not in APP_SELECTIONS:
            raise ValueError("Unsupported app selection")
        self.directory = Path(directory).resolve()
        work = (ROOT / ".work").resolve()
        if not self.directory.is_relative_to(work) or self.directory == work:
            raise ValueError("Pilot state must be in a dedicated directory below .work")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.compose = ROOT / ".work/docker-compose"
        expected = (ROOT / ".work/docker-compose.sha256").read_text().split()[0]
        with self.compose.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError("Compose checksum mismatch")
        self.config_path = self.directory / "config.json"
        if self.config_path.exists():
            self.config = json.loads(self.config_path.read_text())
        else:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            self.config = {"project": "sp-pilot-" + secrets.token_hex(6), "port": port}
            if apps is not None:
                self.config["apps"] = list(apps)
            atomic_json(self.config_path, self.config)
        if not isinstance(self.config, dict) or ("apps" in self.config and not isinstance(self.config["apps"], list)):
            raise ValueError("Invalid pilot configuration")
        if (set(self.config) not in ({"project", "port"}, {"project", "port", "apps"}) or
                not isinstance(self.config.get("project"), str) or
                not __import__("re").fullmatch("sp-pilot-[a-f0-9]{12}", self.config["project"]) or
                type(self.config["port"]) is not int or not 1024 <= self.config["port"] <= 65535):
            raise ValueError("Invalid pilot configuration")
        self.apps = tuple(self.config.get("apps", ("gswb", "schulwissen")))
        if self.apps not in APP_SELECTIONS:
            raise ValueError("Unsupported app selection")
        if apps is not None and tuple(apps) != self.apps:
            raise StateError("App selection changed; use a new pilot directory or an explicit upgrade")
        self.project = self.config["project"]
        self.env = os.environ | {
            "POSTGRES_PASSWORD": "unused-overridden-by-secret-file",
            "GSWB_SECRET_FILE": str(self.directory / "runtime/gswb-key"),
            "GSWB_EDITOR_HASH_FILE": str(self.directory / "runtime/gswb-editor"),
            "SCHULHELFER_SECRET_FILE": str(self.directory / "runtime/helfer-key"),
        }
        self.log = self.directory / "operations.jsonl"

    def command(self, argv, capture=True, input=None):
        result = subprocess.run(argv, env=self.env, text=True, input=input,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        # Output may contain application data; do not persist it in administrative logs.
        with self.log.open("a") as stream:
            stream.write(json.dumps({"at": time.time(), "command": argv, "exitCode": result.returncode}) + "\n")
        if result.returncode:
            # Explicit command name only, never connection strings or exception output.
            raise StateError("Pilot command failed: " + Path(argv[0]).name + "; see local operation exit code")
        return result.stdout if capture else None

    def compose_command(self, app, *args):
        if app == "infra":
            files = ["-f", str(self.directory / "infra.json")]
        else:
            files = ["-f", str(ROOT / ".work/apps" / app / "docker-compose.yml"),
                     "-f", str(self.directory / (app + ".yml"))]
        return self.command([str(self.compose), "-p", self.project + "-" + app, *files, *args])

    def inspect_service(self, app, service):
        cid = self.compose_command(app, "ps", "-q", service).strip()
        if not cid:
            return None
        return json.loads(self.command(["docker", "inspect", cid]))[0]

    def materialize(self):
        store = SecretStore(self.directory / "secrets")
        runtime = self.directory / "runtime"
        runtime.mkdir(mode=0o700, exist_ok=True)
        values = {name: store.get_or_create(name) for name in
                  ["gswb-key", "wissen-key", "postgres-admin", "postgres-app"]}
        if "schulhelfer" in self.apps:
            values["helfer-key"] = store.get_or_create("helfer-key")
        values["gswb-editor"] = ""  # editor remains closed until separately provisioned
        values["wissen-db"] = "postgresql://schulwissen:" + values["postgres-app"] + "@db:5432/schulwissen"
        for name, value in values.items():
            path = runtime / name
            if path.exists():
                if path.read_text() != value:
                    raise StateError("Secret projection mismatch; refusing overwrite")
            else:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
                with os.fdopen(fd, "w") as stream:
                    stream.write(value)
        port = self.config["port"]
        caddy = caddyfile([(app, DEFAULT_DOMAINS[app], APP_PORTS[app]) for app in self.apps])
        caddy = caddy.replace("admin localhost:2019", "admin localhost:2019\n  local_certs")
        (self.directory / "Caddyfile").write_text(caddy)
        infrastructure = {
            "services": {
                "proxy": {
                    "image": INFRASTRUCTURE["caddy"], "restart": "no",
                    "ports": [f"127.0.0.1:{port}:443"],
                    "volumes": [str(self.directory / "Caddyfile") + ":/etc/caddy/Caddyfile:ro",
                                "caddy-data:/data", "caddy-config:/config"],
                    "networks": ["edge", "gswb-proxy", "wissen-proxy"],
                    "mem_limit": "128m", "cpus": 0.5, "pids_limit": 128,
                    "security_opt": ["no-new-privileges:true"],
                },
                "mailpit": {
                    "image": INFRASTRUCTURE["mailpit"],
                    "networks": {"wissen-proxy": {"aliases": ["mailpit"]}},
                    "environment": {"MP_DATABASE": "/tmp/mailpit.db", "MP_MAX_MESSAGES": "100"},
                    "read_only": True, "user": "10001:10001", "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "tmpfs": ["/tmp:size=64m,mode=1777"],
                    "mem_limit": "128m", "cpus": 0.5, "pids_limit": 128,
                },
            },
            "networks": {"edge": {}, "gswb-proxy": {"internal": True}, "wissen-proxy": {"internal": True}},
            "volumes": {"caddy-data": {}, "caddy-config": {}},
        }
        if "zackboing" in self.apps:
            infrastructure["services"]["proxy"]["networks"].append("zack-proxy")
            infrastructure["networks"]["zack-proxy"] = {"internal": True}
        if "schulhelfer" in self.apps:
            infrastructure["services"]["proxy"]["networks"].append("helfer-proxy")
            infrastructure["services"]["mailpit"]["networks"]["helfer-proxy"] = {"aliases": ["mailpit"]}
            infrastructure["networks"]["helfer-proxy"] = {"internal": True}
        for service in infrastructure["services"].values():
            service["logging"] = {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}
        (self.directory / "infra.json").write_text(json.dumps(infrastructure, indent=2))
        net = self.project + "-infra"
        (self.directory / "gswb.yml").write_text(f"""
services:
  app:
    image: gswb:0.1.0-dev
    ports: !reset []
    restart: "no"
    networks:
      default: {{}}
      proxy:
        aliases: [gswb]
networks:
  proxy:
    external: true
    name: {net}_gswb-proxy
""")

        if "zackboing" in self.apps:
            (self.directory / "zackboing.yml").write_text(f"""
services:
  app:
    image: zackboing:0.1.0-dev
    ports: !reset []
    environment:
      ZACKBOING_PUBLIC_URL: https://quiz.localhost:{port}
      ZACKBOING_PROXY_IPS: 127.0.0.1
    networks:
      default: {{}}
      proxy:
        aliases: [zackboing]
networks:
  proxy:
    external: true
    name: {net}_zack-proxy
""")
        if "schulhelfer" in self.apps:
            (self.directory / "schulhelfer.yml").write_text(f"""
services:
  app:
    image: schulhelfer:0.1.0-dev
    ports: !reset []
    environment:
      BASE_URL: https://helfer.localhost:{port}
      PROXY_IPS: 127.0.0.1
      SMTP_HOST: mailpit
      SMTP_PORT: "1025"
      SMTP_STARTTLS: "false"
      SMTP_USE_TLS: "false"
    networks:
      default: {{}}
      proxy:
        aliases: [schulhelfer]
networks:
  proxy:
    external: true
    name: {net}_helfer-proxy
""")
        # No administrative database credential is passed to the application.
        (self.directory / "init-postgres.sh").write_text("""#!/bin/sh
set -eu
export APP_DB_PASSWORD="$(cat /run/secrets/app_db_password)"
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\\getenv app_password APP_DB_PASSWORD
CREATE ROLE schulwissen LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
CREATE DATABASE schulwissen OWNER schulwissen;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL
""")
        (self.directory / "wissen.env").write_text(
            "SW_SECRET_KEY_FILE=/run/secrets/session_key\n"
            "SW_DATABASE_URL_FILE=/run/secrets/database_url\n"
            "SW_ALLOWED_HOSTS=wissen.localhost,localhost\n"
            f"SW_OEFFENTLICHE_URL=https://wissen.localhost:{port}\n"
            "SW_SMTP_HOST=mailpit\nSW_SMTP_PORT=1025\nSW_SMTP_TLS=false\n")
        (self.directory / "schulwissen.yml").write_text(f"""
services:
  db:
    image: {INFRASTRUCTURE["postgres"]}
    restart: "no"
    environment: !override
      POSTGRES_USER: postgres
      POSTGRES_DB: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/admin_password
    secrets: [admin_password, app_db_password]
    volumes:
      - {self.directory}/init-postgres.sh:/docker-entrypoint-initdb.d/01-app.sh:ro
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U postgres -d postgres"]
  app:
    image: schulwissen:0.1.0-dev
    restart: "no"
    ports: !reset []
    env_file: !override
      - {self.directory}/wissen.env
    environment: !override
      SW_MEDIEN_VERZEICHNIS: /medien
      SW_WORKER: "2"
      FORWARDED_ALLOW_IPS: 127.0.0.1
    secrets: [session_key, database_url]
    networks:
      default: {{}}
      proxy:
        aliases: [schulwissen]
    healthcheck:
      test: [CMD, python, -c, "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/health/ready', headers={{'Host': 'localhost'}}), timeout=2)"]
      interval: 5s
      timeout: 3s
      retries: 20
secrets:
  admin_password:
    file: {runtime}/postgres-admin
  app_db_password:
    file: {runtime}/postgres-app
  session_key:
    file: {runtime}/wissen-key
  database_url:
    file: {runtime}/wissen-db
networks:
  proxy:
    external: true
    name: {net}_wissen-proxy
""")

    def provision(self, identity):
        self.materialize()
        self.compose_command("infra", "up", "-d", "--no-build")
        self.compose_command("schulwissen", "up", "-d", "--no-build", "--wait", "db")

    def provisioned(self, identity):
        try:
            return all((self.inspect_service(app, service) or {}).get("State", {}).get("Running") is True
                       for app, service in [("infra", "proxy"), ("infra", "mailpit"), ("schulwissen", "db")])
        except StateError:
            return False

    def configure_proxy(self):
        proxy = self.inspect_service("infra", "proxy")
        address = proxy["NetworkSettings"]["Networks"][self.project + "-infra_wissen-proxy"]["IPAddress"]
        import ipaddress
        ipaddress.ip_address(address)
        path = self.directory / "schulwissen.yml"
        lines = []
        for line in path.read_text().splitlines():
            if line.startswith("      SW_PROXY_IPS:"):
                continue
            if line.startswith("      FORWARDED_ALLOW_IPS:"):
                lines.append("      FORWARDED_ALLOW_IPS: " + address)
                lines.append("      SW_PROXY_IPS: " + address)
            else:
                lines.append(line)
        path.write_text("\n".join(lines) + "\n")


        if "zackboing" in self.apps:
            address = proxy["NetworkSettings"]["Networks"][self.project + "-infra_zack-proxy"]["IPAddress"]
            ipaddress.ip_address(address)
            path = self.directory / "zackboing.yml"
            lines = [("      ZACKBOING_PROXY_IPS: " + address) if line.startswith("      ZACKBOING_PROXY_IPS:") else line
                     for line in path.read_text().splitlines()]
            path.write_text("\n".join(lines) + "\n")

        if "schulhelfer" in self.apps:
            address = proxy["NetworkSettings"]["Networks"][self.project + "-infra_helfer-proxy"]["IPAddress"]
            ipaddress.ip_address(address)
            path = self.directory / "schulhelfer.yml"
            lines = [("      PROXY_IPS: " + address) if line.startswith("      PROXY_IPS:") else line
                     for line in path.read_text().splitlines()]
            path.write_text("\n".join(lines) + "\n")

    def bootstrap(self, identity):
        self.configure_proxy()
        # Schema jobs only. No administrative or real user account is created.
        self.compose_command("gswb", "run", "--rm", "--no-deps", "app", "python", "-m", "grundschul_woerterbuch.migrate")
        self.compose_command("schulwissen", "run", "--rm", "--no-deps", "app", "python", "manage.py", "platform_migrate")
        if "zackboing" in self.apps:
            self.compose_command("zackboing", "run", "--rm", "--no-deps", "app", "node", "server/migrate.js")
        if "schulhelfer" in self.apps:
            self.compose_command("schulhelfer", "run", "--rm", "--no-deps", "app", "python", "-m", "app.migrate")
        self.compose_command("gswb", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")
        self.compose_command("schulwissen", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")
        if "zackboing" in self.apps:
            self.compose_command("zackboing", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")

        if "schulhelfer" in self.apps:
            self.compose_command("schulhelfer", "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")

    def ready(self, identity):
        try:
            return all((self.inspect_service(app, "app") or {}).get("State", {}).get("Health", {}).get("Status") == "healthy"
                       for app in self.apps)
        except StateError:
            return False

    def request(self, host, path, method="GET", headers=None):
        context = ssl.create_default_context(cafile=str(self.directory / "root.crt"))
        connection = http.client.HTTPSConnection(host, self.config["port"], context=context, timeout=5)
        connection.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", self.config["port"]), timeout=5),
                                              server_hostname=host)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return response.status, body
        finally:
            connection.close()



    def quiz_control(self, action):
        if action not in ("prepare-stop", "cancel-stop") or "zackboing" not in self.apps:
            raise ValueError("Unknown local quiz control")
        backend = self.inspect_service("zackboing", "app")
        if not backend:
            raise StateError("Quiz service is not running")
        source = ("fetch('http://127.0.0.1:3000/_platform/" + action + "',{method:'POST'})"
                  ".then(async r=>{if(!r.ok)process.exit(1);process.stdout.write(await r.text());})"
                  ".catch(()=>process.exit(1));")
        return json.loads(self.command(["docker", "exec", backend["Id"], "node", "-e", source]))

    def current_domains(self):
        path = self.directory / "domain-transactions/current.json"
        domains = (json.loads(path.read_text())["domains"] if path.exists()
                   else {app: DEFAULT_DOMAINS[app] for app in self.apps})
        if set(domains) != set(self.apps):
            raise StateError("Unexpected pilot domains")
        from .proxy import hostname
        for domain in domains.values():
            hostname(domain)
        return domains

    def refresh_routes(self, maintenance=()):
        domains = self.current_domains()
        config = caddyfile([(app, domains[app], APP_PORTS[app]) for app in sorted(domains)])
        config = config.replace("admin localhost:2019", "admin localhost:2019\n  local_certs")
        for app in domains:
            backend = self.inspect_service(app, "app")
            if app in maintenance or not backend or not backend["State"]["Running"]:
                config = config.replace("reverse_proxy " + app + ":" + str(APP_PORTS[app]), 'respond "Wartung" 503')
        with (self.directory / "Caddyfile").open("w") as stream:
            stream.write(config)
            stream.flush()
            os.fsync(stream.fileno())
        proxy = self.inspect_service("infra", "proxy")
        if proxy:
            for action in ("validate", "reload"):
                self.command(["docker", "exec", proxy["Id"], "caddy", action, "--config", "/etc/caddy/Caddyfile"])

    def verify(self, identity):
        proxy = self.inspect_service("infra", "proxy")
        self.command(["docker", "cp", proxy["Id"] + ":/data/caddy/pki/authorities/local/root.crt",
                      str(self.directory / "root.crt")])
        results = {}
        domains = self.current_domains()
        for app, host in domains.items():
            status, _ = self.request(host, "/health/ready")
            if status != 200:
                raise StateError("TLS readiness check failed")
            results[app + "-tls-ready"] = status
            backend = self.inspect_service(app, "app")
            if any(backend["NetworkSettings"]["Ports"].values()):
                raise StateError("Backend has a published host port")
            if backend["Config"]["User"] in ("", "0", "root") or not backend["HostConfig"]["ReadonlyRootfs"]:
                raise StateError("Backend user/root filesystem contract violated")
            results[app + "-private-backend"] = True
        for method, path in [("GET", "/review"), ("POST", "/review/synthetic/approve")]:
            status, _ = self.request(domains["gswb"], path, method, {"X-Forwarded-User": "admin", "Remote-User": "admin"})
            if status != 401:
                raise StateError("Anonymous editor access accepted")
        status, _ = self.request(domains["schulwissen"], "/")
        if status != 302:
            raise StateError("Anonymous school knowledge access accepted")
        if "zackboing" in self.apps:
            if self.request(domains["zackboing"], "/api/admin/users")[0] != 401:
                raise StateError("Anonymous quiz administration accepted")
            if self.request(domains["zackboing"], "/_platform/prepare-stop", "POST")[0] != 403:
                raise StateError("Quiz private control reachable through proxy")
        if "schulhelfer" in self.apps:
            if self.request(domains["schulhelfer"], "/admin")[0] != 303:
                raise StateError("Anonymous helper administration accepted")
            if self.request(domains["schulhelfer"], "/")[0] != 200:
                raise StateError("Public helper index unavailable")
        results["negative-access"] = True
        atomic_json(self.directory / "verified.json", {"installation": identity, "checks": results})

    def verified(self, identity):
        path = self.directory / "verified.json"
        if not path.exists():
            return False
        result = json.loads(path.read_text())
        return result.get("installation") == identity and self.ready(identity)

    def up(self, check_running=True):
        # Bind state to immutable local image IDs, not development tags.
        images = {}
        for app in self.apps:
            images[app] = json.loads(self.command(["docker", "image", "inspect", app + ":0.1.0-dev"]))[0]["Id"]
        plan = {"mode": "local-pilot", "config": self.config, "images": images,
                "infrastructure": INFRASTRUCTURE}
        result = Installation(self.directory / "state").run(plan, [
            Step("provision", self.provision, self.provisioned),
            Step("bootstrap", self.bootstrap, self.ready),
            Step("verify", self.verify, self.verified),
        ])
        if check_running and not self.ready(result["id"]):
            raise StateError("Pilot installed but not ready; use pilot-start or inspect the stopped services")
        return result

    def start(self):
        path = self.directory / "state/installation.json"
        if not path.exists() or json.loads(path.read_text()).get("status") != "completed":
            raise StateError("Pilot must have completed installation before lifecycle start")
        result = self.up(check_running=False)  # also rejects changed image IDs
        with exclusive(self.directory / "state/installation.lock"):
            self.compose_command("infra", "up", "-d", "--no-build")
            self.compose_command("schulwissen", "up", "-d", "--no-build", "--wait", "db")
            self.configure_proxy()
            for app in self.apps:
                self.compose_command(app, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90")
            if "zackboing" in self.apps:
                self.quiz_control("cancel-stop")
            self.refresh_routes()
            self.verify(result["id"])
        return result

    def stop(self):
        with exclusive(self.directory / "state/installation.lock"):
            if "zackboing" in self.apps and self.inspect_service("zackboing", "app"):
                pending = self.quiz_control("prepare-stop")
                if pending["activeGames"]:
                    self.quiz_control("cancel-stop")
                    raise StateError("Active games must finish before stopping the pilot")
            for app in (*self.apps, "infra"):
                if (self.directory / ("infra.json" if app == "infra" else app + ".yml")).exists():
                    self.compose_command(app, "stop")
