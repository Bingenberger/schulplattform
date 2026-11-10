"""Production stack for a single host: render and operate.

Inputs are the validated host configuration (config.py) and a verified release
(release_bundle.py). Each app keeps its own standalone docker-compose.yml from
the release; the platform adds a generated override per app plus one
infrastructure project (Caddy, mail relay or sink, dashboard).

Networking is deterministic: every app gets an internal proxy network
<base>.<index>.0/24 on which Caddy is .2 and the mail relay .3. Apps therefore
trust exactly one proxy address, known before any container starts.

The Docker socket is only used by this host-side code (installer, deployment
service), never by the dashboard container.
"""
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time

from . import catalogue
from .catalogue import APPS, MAIL_PORT
from .config import enabled_apps, network_base
from .proxy import production_caddyfile
from .secrets import SecretStore
from .state import StateError
from .storage import atomic_json

DASHBOARD_UID = 10001
MANAGEMENT_INDEX = 0


def fernet_key():
    """32 random bytes, URL-safe base64 (the format cryptography.fernet expects)."""
    import base64
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


class Layout:
    def __init__(self, root):
        self.root = Path(root)
        self.secrets = self.root / "secrets"
        self.runtime = self.root / "runtime"
        self.apps = self.root / "apps"
        self.generated = self.root / "generated"
        self.state = self.root / "state"
        self.domains = self.root / "domains"
        self.caddy_data = self.root / "caddy/data"
        self.check = self.root / "caddy/check"
        self.management = self.root / "management"
        self.releases = self.root / "releases"
        self.backups = self.root / "backups"
        self.log = self.root / "state/operations.jsonl"

    def prepare(self):
        for path, mode in [(self.root, 0o711), (self.secrets, 0o700), (self.runtime, 0o711),
                           (self.apps, 0o755), (self.generated, 0o700), (self.state, 0o700),
                           (self.domains, 0o700), (self.caddy_data.parent, 0o700), (self.caddy_data, 0o700),
                           (self.check, 0o755), (self.management, 0o750), (self.releases, 0o700),
                           (self.backups, 0o700)]:
            path.mkdir(parents=True, exist_ok=True, mode=mode)
            info = path.lstat()
            if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
                raise StateError(f"Unsafe platform directory: {path}")
            os.chmod(path, mode)
        if os.geteuid() == 0:
            # The dashboard container (UID/GID 10001) may traverse and read, never write.
            os.chown(self.management, 0, DASHBOARD_UID)


def proxy_network(app):
    return f"sp-{app}-proxy"


def subnet(config, index):
    base = network_base(config)
    return ipaddress.ip_network((int(base.network_address) + index * 256, 24))


def host_address(config, index, host):
    return str(subnet(config, index).network_address + host)


def origin(hostname):
    return "https://" + hostname


class Stack:
    def __init__(self, layout, config, release, compose=("docker", "compose"), run=None, docker="docker"):
        self.layout = layout
        self.config = config
        self.release = release
        self.compose_argv = tuple(compose)
        self.docker = docker
        self._run = run or self._subprocess
        self.apps = enabled_apps(config)
        self.mail_mode = config["smtp"]["mode"]

    # --- process execution ----------------------------------------------------
    def _subprocess(self, argv, env=None, capture=True, timeout=600, tty=False, binary=False):
        result = subprocess.run(argv, env=env, text=not binary, timeout=timeout,
                                stdin=None if tty else subprocess.DEVNULL,
                                stdout=None if tty else subprocess.PIPE,
                                stderr=None if tty else subprocess.PIPE)
        empty = b"" if binary else ""
        if result.returncode and os.environ.get("SP_DEBUG") == "1" and result.stderr:
            # Explicit operator diagnostics only; stderr may contain application data.
            tail = result.stderr[-1500:] if not binary else result.stderr[-1500:].decode(errors="replace")
            print(f"[SP_DEBUG] {Path(argv[0]).name} {' '.join(argv[1:6])}: {tail}", file=sys.stderr)
        return result.returncode, (result.stdout or empty) if capture else empty

    def command(self, argv, capture=True, timeout=600, tty=False, check=True, binary=False):
        if binary:
            code, output = self._run(list(argv), env=self.environment(), capture=capture, timeout=timeout,
                                     tty=tty, binary=True)
        else:
            code, output = self._run(list(argv), env=self.environment(), capture=capture, timeout=timeout, tty=tty)
        self.layout.log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.layout.log.open("a") as stream:
            # Command names and exit codes only; output can contain application data.
            stream.write(json.dumps({"at": time.time(), "command": [Path(argv[0]).name, *argv[1:4]],
                                     "exitCode": code}) + "\n")
        if code and check:
            raise StateError(f"Command failed: {Path(argv[0]).name} {' '.join(argv[1:4])} (exit {code})")
        return output

    def environment(self):
        env = {key: value for key, value in os.environ.items()
               if key in ("PATH", "HOME", "LANG", "LC_ALL", "DOCKER_HOST", "DOCKER_CONFIG")}
        for app in APPS.values():
            for variable, relative in app.compose_env.items():
                env[variable] = ("unused-overridden-by-secret-file" if relative == "!unused"
                                 else str(self.layout.runtime / relative))
        name_file = self.layout.runtime / "gswb-editor-name"
        env["EDITOR_USERNAME"] = name_file.read_text().strip() if name_file.exists() else ""
        return env

    def compose(self, app, *args, **kwargs):
        if app == "infra":
            files = ["-f", str(self.layout.generated / "infra.yml")]
            project = "sp-infra"
        else:
            files = ["-f", str(self.layout.apps / app / "docker-compose.yml"),
                     "-f", str(self.layout.generated / f"{app}.yml")]
            project = "sp-" + app
        return self.command([*self.compose_argv, "-p", project, "--project-directory",
                             str(self.layout.apps / app if app != "infra" else self.layout.generated),
                             *files, *args], **kwargs)

    # --- rendering ------------------------------------------------------------
    def mail_host(self):
        return "mailrelay" if self.mail_mode in ("relay", "sink") else "mail-disabled.invalid"

    def mail_from(self):
        smtp = self.config["smtp"]
        if smtp.get("sender"):
            name = smtp.get("sender_name", "Schulplattform")
            return json.dumps(f"{name} <{smtp['sender']}>")
        return json.dumps("Schulplattform <noreply@" + self.config["platform"]["management_domain"] + ">")

    def materialize_secrets(self):
        store = SecretStore(self.layout.secrets)
        values = {}
        for app_id in self.apps:
            for relative, kind in APPS[app_id].secrets:
                if kind.startswith("random:"):
                    values[relative] = store.get_or_create(kind.split(":", 1)[1])
                elif kind.startswith("fernet:"):
                    values[relative] = store.get_or_create(kind.split(":", 1)[1], generate=fernet_key)
        for app_id in self.apps:
            for relative, kind in APPS[app_id].secrets:
                path = self.layout.runtime / relative
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o711)
                if kind.startswith(("random:", "fernet:")):
                    value = values[relative]
                elif kind == "empty":
                    value = None  # created empty once; later filled only by explicit local setup
                elif kind.startswith("url:"):
                    template = kind.split(":", 1)[1]
                    value = template
                    for name in ("postgres-app", "rad-db-app", "lese-db-app", "abgen-db-app"):
                        if "{" + name + "}" in value:
                            value = value.replace("{" + name + "}", store.get_or_create(name))
                else:
                    raise StateError("Unknown secret kind")
                self._project(path, value)
        if self.mail_mode == "relay" and self.config["smtp"].get("username"):
            password = store.path("smtp-password")
            if not password.exists():
                raise StateError("SMTP password not set; run './install.sh smtp-password' on the console")

    @staticmethod
    def _project(path, value):
        if path.is_symlink():
            raise StateError("Secret projection symlink refused")
        if path.exists():
            if value is not None and path.read_text() != value:
                raise StateError(f"Secret projection mismatch for {path.name}; refusing overwrite")
            return
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        with os.fdopen(fd, "w") as stream:
            stream.write(value or "")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, 0o444)

    def youtube_key_set(self):
        path = self.layout.runtime / "tafel-youtube-key"
        return path.is_file() and not path.is_symlink() and bool(path.read_text().strip())

    def projection_set(self, name):
        path = self.layout.runtime / name
        return path.is_file() and not path.is_symlink() and bool(path.read_text().strip())

    def gallery_public(self):
        return self.config["apps"].get("bildergalerie", {}).get("public", True)

    def _own_gallery_origin(self):
        gallery = self.config["apps"].get("bildergalerie", {})
        return origin(gallery["hostname"]) if gallery.get("enabled") else ""

    def gallery_origin(self, app_id):
        """Explicit gallery_origin ("" = off), else the platform's own bildergalerie when enabled."""
        configured = self.config["apps"].get(app_id, {}).get("gallery_origin")
        return configured if configured is not None else self._own_gallery_origin()

    def own_gallery(self, app_id):
        """The API token goes only to the platform's own gallery, never to an external origin."""
        own = self._own_gallery_origin()
        return bool(own) and self.gallery_origin(app_id) == own

    def woerterbuch_origin(self, app_id):
        """Explicit woerterbuch_origin ("" = off), else the public origin of this platform's gswb.

        The board fetches the public read-only API over the public domain like any other client;
        app proxy networks stay isolated (no shared network between grundschultafel and gswb)."""
        apps = self.config["apps"]
        configured = apps.get(app_id, {}).get("woerterbuch_origin")
        if configured is not None:
            return configured
        gswb = apps.get("gswb", {})
        return origin(gswb["hostname"]) if gswb.get("enabled") else ""

    def karten_kacheln(self, app_id):
        """Tile URL for fahrradausbildung's PDF maps, only with karten = true (tiles reveal post locations)."""
        return catalogue.KARTEN_KACHELN if self.config["apps"].get(app_id, {}).get("karten") else ""

    def oidc_block(self, app_id):
        """SW_OIDC_* lines for schulwissen's env file, only when issuer, client id and secret are all set.

        The _FILE variable must not point to an empty file (the app refuses to start), so an
        incomplete setup renders nothing and the Nextcloud login simply stays off."""
        entry = self.config["apps"].get(app_id, {})
        if not (entry.get("nextcloud_issuer") and entry.get("nextcloud_client_id")
                and self.projection_set("wissen-oidc")):
            return ""
        lines = [f"SW_OIDC_ISSUER={entry['nextcloud_issuer']}"]
        if entry.get("nextcloud_discovery_url"):
            lines.append(f"SW_OIDC_DISCOVERY_URL={entry['nextcloud_discovery_url']}")
        lines += [f"SW_OIDC_CLIENT_ID={entry['nextcloud_client_id']}",
                  "SW_OIDC_CLIENT_SECRET_FILE=/run/secrets/oidc_client_secret"]
        return "".join(line + "\n" for line in lines)

    def files_block(self, app_id):
        """SW_NEXTCLOUD_* lines (technical account for the file picker), only when URL, user and app
        password are all set; like oidc_block, an empty _FILE would stop schulwissen."""
        entry = self.config["apps"].get(app_id, {})
        if not (entry.get("nextcloud_files_url") and entry.get("nextcloud_files_user")
                and self.projection_set("wissen-nextcloud")):
            return ""
        return (f"SW_NEXTCLOUD_URL={entry['nextcloud_files_url']}\n"
                f"SW_NEXTCLOUD_NUTZER={entry['nextcloud_files_user']}\n"
                "SW_NEXTCLOUD_PASSWORT_FILE=/run/secrets/nextcloud_password\n")

    def context(self, app_id, hostname):
        app = APPS[app_id]
        values = {
            "host": hostname, "origin": origin(hostname),
            "proxy_ip": host_address(self.config, app.index, 2),
            "proxy_network": proxy_network(app_id),
            "mail_host": self.mail_host(), "mail_port": MAIL_PORT, "mail_from": self.mail_from(),
            "runtime": str(self.layout.runtime),
            "postgres16": catalogue.INFRASTRUCTURE["postgres16"],
            "postgres18": catalogue.INFRASTRUCTURE["postgres18"],
            # Optional features of grundschultafel (gallery, YouTube search, dictionary).
            "gallery_origin": json.dumps(self.gallery_origin(app_id)),
            "gallery_token_file": json.dumps("/run/secrets/gallery-token" if self.own_gallery(app_id) else ""),
            # bildergalerie: publicly searchable unless switched off in platform.toml
            "gallery_public": json.dumps("true" if self.gallery_public() else "false"),
            "gallery_ai_key_file": json.dumps("/run/secrets/ai-key" if self.projection_set("gallery-ai-key") else ""),
            "youtube_enabled": json.dumps("1" if self.youtube_key_set() else "0"),
            "woerterbuch_origin": json.dumps(self.woerterbuch_origin(app_id)),
            # fahrradausbildung: server-side map images in PDFs, off unless karten = true
            "karten_kacheln": json.dumps(self.karten_kacheln(app_id)),
            # schulwissen: optional Nextcloud login (env-file lines, not YAML)
            "oidc_block": self.oidc_block(app_id),
            # schulwissen: optional Nextcloud file picker (technical account)
            "files_block": self.files_block(app_id),
        }
        for service, image in app.images.items():
            values["image_" + service] = self.release.image(image)
        return values

    def render(self, domains):
        """Write compose copies, overrides, infra project and Caddyfile for the given domains."""
        self.layout.prepare()
        self.materialize_secrets()
        self.render_apps(domains)
        self._write(self.layout.generated / "infra.yml", json.dumps(self.infrastructure(), indent=2), 0o600)
        self.write_caddyfile(domains, self.routed(domains))

    def render_apps(self, domains):
        """Compose copies and per-app overrides; unchanged files are left untouched."""
        for app_id in self.apps:
            target = self.layout.apps / app_id
            self.release.install_compose(app_id, target)
            context = self.context(app_id, domains[app_id])
            override = APPS[app_id].override.format(**context)
            self._write(self.layout.generated / f"{app_id}.yml", override, 0o600)
            for relative in APPS[app_id].host_dirs:
                directory = self.layout.runtime / relative
                directory.mkdir(parents=True, exist_ok=True, mode=0o755)
            for relative, template in APPS[app_id].extra_files.items():
                self._write(self.layout.runtime / relative, template.format(**context), 0o444)

    @staticmethod
    def _write(path, text, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text() == text:
            os.chmod(path, mode)
            return False
        temporary = path.with_name("." + path.name + ".new")
        if temporary.exists():
            os.chmod(temporary, 0o600)
            temporary.unlink()
        with open(temporary, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        return True

    def infrastructure(self):
        config = self.config
        networks = {
            "edge": {"name": "sp-edge"},
            "management": {"name": "sp-management", "internal": True,
                           "ipam": {"config": [{"subnet": str(subnet(config, MANAGEMENT_INDEX)),
                                                "ip_range": str(list(subnet(config, MANAGEMENT_INDEX)
                                                                     .subnets(new_prefix=25))[1])}]}},
        }
        proxy_networks = {}
        for app_id in self.apps:
            index = APPS[app_id].index
            net = subnet(config, index)
            # Fixed addresses (.2 proxy, .3 mail relay) lie outside the dynamic range, so an app container
            # started while the proxy is being recreated can never take the proxy's address.
            networks[f"{app_id}-proxy"] = {"name": proxy_network(app_id), "internal": True,
                                           "ipam": {"config": [{"subnet": str(net),
                                                                "ip_range": str(list(net.subnets(new_prefix=25))[1])}]}}
            proxy_networks[f"{app_id}-proxy"] = {"ipv4_address": host_address(config, index, 2)}
        # Directory mount: atomic replace of the Caddyfile creates a new inode, which a single-file
        # bind mount would never see.
        caddy_volumes = [f"{self.layout.generated}/caddy:/etc/caddy/conf:ro",
                         f"{self.layout.caddy_data}:/data", "caddy-config:/config",
                         f"{self.layout.check}:/srv/check:ro"]
        if config["platform"]["acme_environment"] == "custom" and config["platform"].get("acme_ca_root"):
            caddy_volumes.append(f"{config['platform']['acme_ca_root']}:/etc/caddy/acme-root.pem:ro")
        services = {
            "proxy": {
                "image": catalogue.INFRASTRUCTURE["caddy"], "restart": "unless-stopped",
                "command": ["caddy", "run", "--config", "/etc/caddy/conf/Caddyfile", "--adapter", "caddyfile"],
                "ports": ["80:80", "443:443"],
                "volumes": caddy_volumes,
                "networks": {"edge": {},
                             "management": {"ipv4_address": host_address(config, MANAGEMENT_INDEX, 2)},
                             **proxy_networks},
                "cap_drop": ["ALL"], "cap_add": ["NET_BIND_SERVICE"],
                "security_opt": ["no-new-privileges:true"],
                "mem_limit": "256m", "cpus": 1.0, "pids_limit": 256,
            },
            "dashboard": {
                "image": self.release.image("schulplattform-dashboard"), "restart": "unless-stopped",
                "user": f"{DASHBOARD_UID}:{DASHBOARD_UID}",
                "read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
                "tmpfs": ["/tmp:size=64m,mode=1777"], "mem_limit": "384m", "cpus": 0.5, "pids_limit": 128,
                "environment": {
                    "SP_DASHBOARD_STATE": "/state", "SP_DEPLOYMENT_SOCKET": "/run/management/deploy.sock",
                    "SP_DEPLOYMENT_KEY_FILE": "/run/management-key/deployment-key",
                    "SP_APP_CATALOGUE": "/run/management/apps.json",
                    "SP_DASHBOARD_HOSTS": config["platform"]["management_domain"],
                },
                "volumes": ["dashboard-state:/state",
                            f"{self.layout.management}:/run/management:ro",
                            f"{self.layout.runtime}/dashboard:/run/management-key:ro"],
                "networks": {"management": {"aliases": ["dashboard"]}},
                "healthcheck": {
                    "test": ["CMD", "python", "-c",
                             "import urllib.request;urllib.request.urlopen(urllib.request.Request("
                             "'http://127.0.0.1:8000/health/live',headers={'Host':'"
                             + config["platform"]["management_domain"] + "'}),timeout=2)"],
                    "interval": "15s", "timeout": "3s", "retries": 3},
            },
        }
        if self.mail_mode in ("relay", "sink"):
            mail_networks = {"edge": {}}
            client_networks = []
            for app_id in self.apps:
                if APPS[app_id].mail:
                    index = APPS[app_id].index
                    mail_networks[f"{app_id}-proxy"] = {"ipv4_address": host_address(config, index, 3),
                                                       "aliases": ["mailrelay"]}
                    client_networks.append(str(subnet(config, index)))
            if self.mail_mode == "relay":
                smtp = config["smtp"]
                relay = {
                    "image": self.release.image("schulplattform-relay"), "restart": "unless-stopped",
                    "read_only": True, "cap_drop": ["ALL"],
                    "cap_add": ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETUID", "SETGID", "KILL"],
                    "security_opt": ["no-new-privileges:true"],
                    "tmpfs": ["/etc/postfix:mode=0755", "/run", "/tmp", "/var/lib/postfix"],
                    "volumes": ["relay-spool:/var/spool/postfix"],
                    "environment": {"RELAY_UPSTREAM_HOST": smtp["host"], "RELAY_UPSTREAM_PORT": str(smtp["port"]),
                                    "RELAY_SECURITY": smtp["security"], "RELAY_SENDER": smtp["sender"],
                                    "RELAY_SENDER_NAME": smtp.get("sender_name", "Schulplattform"),
                                    "RELAY_USERNAME": smtp.get("username", ""),
                                    "RELAY_NETWORKS": " ".join(client_networks) or "127.0.0.1/32"},
                    "mem_limit": "128m", "cpus": 0.5, "pids_limit": 128,
                    "networks": mail_networks,
                }
                if smtp.get("username"):
                    relay["volumes"].append(f"{self.layout.secrets}/smtp-password:/run/secrets/smtp-password:ro")
                services["mailrelay"] = relay
            else:
                services["mailrelay"] = {
                    "image": catalogue.INFRASTRUCTURE["mailpit"], "restart": "unless-stopped",
                    "environment": {"MP_DATABASE": "/tmp/mailpit.db", "MP_MAX_MESSAGES": "500",
                                    "MP_SMTP_BIND_ADDR": f"0.0.0.0:{MAIL_PORT}"},
                    "read_only": True, "user": "10001:10001", "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"], "tmpfs": ["/tmp:size=64m,mode=1777"],
                    "mem_limit": "128m", "cpus": 0.5, "pids_limit": 128,
                    "networks": {**mail_networks, "management": {"aliases": ["mailsink"]}},
                }
        for service in services.values():
            service["logging"] = {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}
        volumes = {"caddy-config": {}, "dashboard-state": {}}
        if self.mail_mode == "relay":
            volumes["relay-spool"] = {}
        return {"name": "sp-infra", "services": services, "networks": networks, "volumes": volumes}

    # --- routing --------------------------------------------------------------
    def routed(self, domains):
        """Apps whose current hostname passed the DNS check (maintenance apps stay routed to a 503)."""
        status = self.domain_status()
        return {app for app in self.apps
                if status.get(app, {}).get("hostname") == domains[app]
                and status.get(app, {}).get("dns") == "ok"}

    def domain_status(self):
        path = self.layout.domains / "status.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def write_caddyfile(self, domains, routed, maintenance=None):
        platform = self.config["platform"]
        if maintenance is None:
            maintenance = {key for key, entry in self.domain_status().items() if entry.get("maintenance")}
        routes = []
        for app_id in sorted(routed):
            app = APPS[app_id]
            routes.append((domains[app_id], None if app_id in maintenance else f"{app_id}:{app.port}"))
        management_routed = self.domain_status().get("_management", {}).get("dns") == "ok"
        text = production_caddyfile(
            routes, management=(platform["management_domain"], "dashboard:8000") if management_routed else None,
            email=platform["acme_email"], environment=platform["acme_environment"],
            acme_ca=platform.get("acme_ca"), custom_root="/etc/caddy/acme-root.pem"
            if platform.get("acme_ca_root") else None)
        return self._write(self.layout.generated / "caddy" / "Caddyfile", text, 0o644)

    def _caddyfile(self):
        path = self.layout.generated / "caddy" / "Caddyfile"
        return path.read_text() if path.exists() else ""

    @staticmethod
    def _acme_directory(text):
        for line in text.splitlines():
            if line.strip().startswith("acme_ca "):
                return line.split(None, 1)[1].strip()
        return None

    def _proxy_marker(self):
        try:
            return json.loads((self.layout.state / "proxy-loaded.json").read_text())
        except (OSError, ValueError):
            return {}

    def proxy_current(self):
        """True when the running Caddy has loaded the Caddyfile as it is on disk now."""
        digest = hashlib.sha256(self._caddyfile().encode()).hexdigest()
        return self._proxy_marker().get("digest") == digest

    def reload_proxy(self):
        """Apply the Caddyfile. A changed ACME directory needs a restart: Caddy keeps certificates of the
        previous CA in its in-memory cache across reloads and would serve them until renewal."""
        container = self.container("infra", "proxy")
        if not (container and container["State"].get("Running")):
            return
        text = self._caddyfile()
        acme = self._acme_directory(text)
        config = ["--config", "/etc/caddy/conf/Caddyfile", "--adapter", "caddyfile"]
        self.command([self.docker, "exec", container["Id"], "caddy", "validate", *config])
        if self._proxy_marker().get("acme") == acme:
            self.command([self.docker, "exec", container["Id"], "caddy", "reload", *config])
        else:
            self.command([self.docker, "restart", "--time", "20", container["Id"]])
        self._write(self.layout.state / "proxy-loaded.json",
                    json.dumps({"digest": hashlib.sha256(text.encode()).hexdigest(), "acme": acme}) + "\n", 0o600)

    # --- inspection -----------------------------------------------------------
    def container(self, app, service):
        cid = self.compose(app, "ps", "-a", "-q", service, check=False).strip()
        if not cid or "\n" in cid:
            return None
        output = self.command([self.docker, "inspect", cid], check=False)
        try:
            return json.loads(output)[0]
        except (ValueError, IndexError):
            return None

    def service_state(self, app, service):
        container = self.container(app, service)
        if not container:
            return {"exists": False, "running": False, "health": "absent", "image": None}
        state = container["State"]
        return {"exists": True, "running": state.get("Running") is True,
                "health": state.get("Health", {}).get("Status", "running" if state.get("Running") else "stopped"),
                "image": container["Config"].get("Image")}

    def outdated(self, app_id):
        """True when a service container does not run the image pinned by the current release."""
        for service, name in APPS[app_id].images.items():
            container = self.container(app_id, service)
            if not container:
                return True
            digest = self.release.image(name).rpartition("@")[2]
            if digest in container.get("Config", {}).get("Image", ""):
                continue
            output = self.command([self.docker, "image", "inspect", "--format", "{{json .RepoDigests}}",
                                   container.get("Image", "")], check=False)
            try:
                if any(entry.endswith("@" + digest) for entry in json.loads(output or "[]") or []):
                    continue
            except ValueError:
                pass
            return True
        return False

    def healthy(self, app_id):
        services = APPS[app_id].services + APPS[app_id].database_services
        return all(self.service_state(app_id, service)["health"] == "healthy" for service in services)

    # --- lifecycle --------------------------------------------------------------
    def pull(self):
        images = sorted(set(self.release.all_images(self.apps, self.mail_mode)))
        for reference in images:
            present = self.command([self.docker, "image", "inspect", "--format", "{{.Id}}", reference], check=False)
            if not present.strip():
                self.command([self.docker, "pull", "--quiet", reference], timeout=1800)
        return images

    def infrastructure_up(self):
        (self.layout.runtime / "dashboard").mkdir(mode=0o711, exist_ok=True)
        pending = self.layout.state / "dashboard-restore.tar"
        if pending.exists():
            # Disaster recovery: seed the (new, empty) dashboard volume once, as its owner UID.
            self.command([self.docker, "volume", "create", "sp-infra_dashboard-state"])
            os.chmod(pending, 0o644)
            self.command([self.docker, "run", "--rm", "--network", "none", "--read-only", "--user", "0:0",
                          "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "DAC_OVERRIDE", "--cap-add", "FOWNER",
                          "-v", "sp-infra_dashboard-state:/state", "-v", f"{pending}:/in.tar:ro",
                          catalogue_helper(), "sh", "-c",
                          "[ -z \"$(ls -A /state)\" ] && tar -C /state -xf /in.tar && chown -R 10001:10001 /state "
                          "&& chmod 700 /state || true"])
            pending.unlink()
        self.compose("infra", "up", "-d", "--pull", "never", "--remove-orphans", "--wait", "--wait-timeout", "120")

    def migrate(self, app_id):
        app = APPS[app_id]
        if app.database_services:
            self.compose(app_id, "up", "-d", "--pull", "never", "--no-build", "--wait", "--wait-timeout", "120",
                         *app.database_services)
        for argv in app.migrations:
            self.compose(app_id, "run", "--rm", "--no-deps", "--pull", "never", app.migration_service, *argv,
                         timeout=1800)

    def start(self, app_id):
        app = APPS[app_id]
        self.compose(app_id, "up", "-d", "--pull", "never", "--no-build", "--wait", "--wait-timeout", "180",
                     *app.database_services, *app.services)

    def stop(self, app_id):
        app = APPS[app_id]
        self.compose(app_id, "stop", "--timeout", "130", *reversed(app.services))

    # --- verification ---------------------------------------------------------
    def tls_context(self):
        platform = self.config["platform"]
        if platform["acme_environment"] == "custom":
            return ssl.create_default_context(cafile=platform.get("issued_root") or platform.get("acme_ca_root"))
        if platform["acme_environment"] == "staging":
            # Staging certificates chain to non-public roots; hostname is still checked below.
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return ssl.create_default_context()

    def request(self, hostname, path, method="GET", headers=(), address="127.0.0.1", port=443, timeout=10):
        context = self.tls_context()
        raw = socket.create_connection((address, port), timeout=timeout)
        sock = context.wrap_socket(raw, server_hostname=hostname)
        try:
            if self.config["platform"]["acme_environment"] == "staging":
                if hostname not in self._san(sock.getpeercert(True)):
                    raise StateError("Certificate does not cover hostname")
            connection = http.client.HTTPSConnection(hostname, port, context=context, timeout=timeout)
            connection.sock = sock
            connection.request(method, path, headers=dict(headers))
            response = connection.getresponse()
            body = response.read(65536)
            return response.status, body
        finally:
            sock.close()

    @staticmethod
    def _san(der):
        from cryptography import x509
        certificate = x509.load_der_x509_certificate(der)
        try:
            return certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value \
                .get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            return []

    def verify_app(self, app_id, hostname):
        """TLS readiness through the proxy plus the app's negative-access checks."""
        app = APPS[app_id]
        results = {}
        status, _ = self.request(hostname, app.ready)
        if status != 200:
            raise StateError(f"{app_id}: TLS readiness returned {status}")
        results["ready"] = status
        for check in app.checks:
            status, _ = self.request(hostname, check.path, check.method, check.headers)
            if status != check.expected:
                raise StateError(f"{app_id}: {check.method} {check.path} returned {status}, expected {check.expected}")
            results[f"{check.method} {check.path}"] = status
        for service in app.services:
            container = self.container(app_id, service)
            if not container or any(container["NetworkSettings"]["Ports"].values()):
                raise StateError(f"{app_id}/{service}: backend publishes a host port")
            if container["Config"]["User"] in ("", "0", "root") or not container["HostConfig"]["ReadonlyRootfs"]:
                raise StateError(f"{app_id}/{service}: non-root/read-only contract violated")
        results["private-backend"] = True
        return results

    def write_management_catalogue(self, domains):
        entries = {}
        for app_id in self.apps:
            entries[app_id] = {"name": DISPLAY.get(app_id, app_id), "description": DESCRIPTION.get(app_id, ""),
                               "url": origin(domains[app_id]),
                               "public": app_id == "gswb" or (app_id == "bildergalerie" and self.gallery_public())}
        path = self.layout.management / "apps.json"
        self._write(path, json.dumps(entries, ensure_ascii=False, indent=2), 0o644)


DISPLAY = {"gswb": "Wörterbuch", "schulwissen": "Schulwissen", "zackboing": "Zackboing", "schulhelfer": "Schulhelfer",
           "losverkauf": "Losverkauf", "grundschultafel": "Grundschultafel",
           "fahrradausbildung": "Fahrradausbildung", "leseflux": "Leseflux",
           "kompetenz-manager": "Kompetenz-Manager", "abgen": "Arbeitsblätter", "fundkiste": "Fundkiste", "schuleva": "Schulbefragung", "schulkasse": "Schulkasse", "schulanmeldung": "Schulanmeldung",
           "sl-journal": "Schulleitungsjournal", "bildergalerie": "Bildergalerie"}
DESCRIPTION = {"gswb": "Öffentliche Wörterbuchsuche", "schulwissen": "Schulinterne Inhalte",
               "zackboing": "Quiz und Spiele", "schulhelfer": "Helferlisten", "losverkauf": "Losverkauf",
               "grundschultafel": "Persönliche Lehrertafel", "fahrradausbildung": "Radfahrausbildung und Posten",
               "leseflux": "Leseübungen", "kompetenz-manager": "Kompetenzen und Berichte",
               "abgen": "Arbeitsblätter gemeinsam erstellen", "fundkiste": "Fundsachen der Schule",
               "schuleva": "Anonyme Eltern- und Schülerbefragung",
               "schulkasse": "Beiträge und Kassenbuch",
               "schulanmeldung": "Einschulung und Elternportal",
               "sl-journal": "Journal der Schulleitung (verschlüsselt)",
               "bildergalerie": "KI-Bilder (CC0) für Unterricht und Tafel"}


def catalogue_helper():
    from .backups import HELPER
    return HELPER


def digest_file(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def remove_tree(path):
    if Path(path).exists():
        shutil.rmtree(path)
