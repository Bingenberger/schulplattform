"""Production installation: preflight -> plan -> provision -> bootstrap -> verify -> completed.

The plan binds the verified release digest and the host configuration digest.
Repeating 'apply' with the same plan is a no-op; an interrupted run resumes at
the last verified step (state.Installation). A changed plan requires an
explicit '--reconfigure', which keeps volumes, keys and certificates.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from . import config as cfg
from .catalogue import APPS
from .domains import Domains
from .host import Provisioner, units
from .release_bundle import Release, key_fingerprint
from .routing import MANAGEMENT, Router
from .secrets import SecretStore
from .stack import Layout, Stack
from .state import Installation, StateError, Step
from .storage import atomic_json

PLATFORM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path("/var/lib/schulplattform")
SOCKET = "deploy.sock"


class Platform:
    def __init__(self, config_path, root, bundle, trusted_key, compose=("docker", "compose"), provision_host=True,
                 provisioner=None):
        self.config_path = Path(config_path)
        self.config = cfg.load(self.config_path)
        self.layout = Layout(root)
        self.bundle_dir = Path(bundle)
        self.trusted_key = Path(trusted_key)
        self.release = Release(self.bundle_dir, self.trusted_key)
        self.stack = Stack(self.layout, self.config, self.release, compose=compose)
        self.provision_host = provision_host
        self.provisioner = provisioner or Provisioner(self.layout.state)
        self._domains = None

    # --- shared objects ---------------------------------------------------------
    def plan(self):
        config_digest = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest()
        return {"mode": "production", "release": self.release.version, "releaseDigest": self.release.digest,
                "trustedKey": key_fingerprint(self.trusted_key), "configDigest": config_digest,
                "apps": list(self.stack.apps), "hostProvisioning": self.provision_host}

    def domains(self):
        if self._domains is None:
            initial = {app: self.config["apps"][app]["hostname"] for app in self.stack.apps}
            self._domains = Domains(self.layout.domains, initial, self.config["platform"]["management_domain"],
                                    self._domain_preflight, self._domain_activate, self._domain_verify,
                                    operation_lock=self.layout.state / "operation.lock")
        return self._domains

    def current_domains(self):
        store = self.domains()
        domains = json.loads((self.layout.domains / "current.json").read_text())["domains"]
        for app in self.stack.apps:
            if app not in domains:
                domains = store.add(app, self.config["apps"][app]["hostname"])["domains"]
        return domains

    def set_enabled(self, app, enabled):
        data = dict(self.config)
        data["apps"] = {key: dict(value) for key, value in self.config["apps"].items()}
        data["apps"][app]["enabled"] = bool(enabled)
        cfg.write(data, self.config_path)

    def router(self):
        self.domains()
        return Router(self.stack, self.domains())

    def deployment_key(self):
        store = SecretStore(self.layout.secrets)
        return store.get_or_create("deployment-channel-key")

    # --- steps ------------------------------------------------------------------
    def step_host(self, _identity):
        if not self.provision_host:
            return
        p = self.provisioner
        p.base_packages()
        if not p.docker_repository_ok():
            p.docker_repository()
        if not p.docker_ok():
            p.docker()
        if not p.firewall_ok():
            p.firewall()

    def probe_host(self, _identity):
        if not self.provision_host:
            return True
        failing = self.provisioner.diagnose()
        if failing:
            print("Host-Prüfung nicht erfüllt: " + ", ".join(failing), file=sys.stderr)
        return not failing

    def step_render(self, _identity):
        self.layout.prepare()
        self.release.store(self.layout.releases)
        domains = self.current_domains()
        missing = set(self.stack.apps) - set(domains)
        if missing:
            raise StateError("Enabled apps without a domain record; use 'reconfigure' to add apps")
        self.stack.render(domains)
        key = self.deployment_key()
        runtime = self.layout.runtime / "dashboard"
        runtime.mkdir(mode=0o711, exist_ok=True)
        self.stack._project(runtime / "deployment-key", key)
        self.stack.write_management_catalogue(domains)

    def probe_render(self, _identity):
        return (self.layout.generated / "infra.yml").is_file() and all(
            (self.layout.generated / f"{app}.yml").is_file() for app in self.stack.apps)

    def step_images(self, _identity):
        self.stack.pull()

    def probe_images(self, _identity):
        for reference in set(self.release.all_images(self.stack.apps, self.stack.mail_mode)):
            if not self.stack.command([self.stack.docker, "image", "inspect", "--format", "{{.Id}}", reference],
                                      check=False).strip():
                return False
        return True

    def step_infrastructure(self, _identity):
        self.stack.infrastructure_up()

    def probe_infrastructure(self, _identity):
        services = ["proxy", "dashboard"] + (["mailrelay"] if self.stack.mail_mode in ("relay", "sink") else [])
        return all(self.stack.service_state("infra", s)["running"] for s in services)

    def step_service(self, _identity):
        if not self.provision_host:
            return
        unit_set = self.unit_set()
        self.provisioner.install_units(unit_set)

    def probe_service(self, _identity):
        if not self.provision_host:
            return True
        return self.provisioner.units_ok(self.unit_set())

    def unit_set(self):
        unit_set = units(self.layout.root, PLATFORM_DIR, self.layout.management / SOCKET, self.config_path,
                         self.layout.releases / self.release.version, self.trusted_key_installed())
        unit_set["schulplattform-backup.timer"] = unit_set["schulplattform-backup.timer"].replace(
            "{schedule}", self.config["backup"]["schedule"])
        return unit_set

    def trusted_key_installed(self):
        destination = self.layout.state / "release-trust.pub"
        if not destination.exists():
            destination.write_bytes(self.trusted_key.read_bytes())
            os.chmod(destination, 0o644)
        elif destination.read_bytes() != self.trusted_key.read_bytes():
            raise StateError("A different release trust key is already installed; explicit rotation required")
        return destination

    def step_apps(self, _identity):
        for app in self.stack.apps:
            if not self.stack.healthy(app):
                self.stack.migrate(app)
                self.stack.start(app)

    def probe_apps(self, _identity):
        return all(self.stack.healthy(app) for app in self.stack.apps)

    def step_routes(self, _identity):
        self.router().reconcile(wait_seconds=int(os.environ.get("SP_CERT_WAIT", "150")))

    def probe_routes(self, _identity):
        status = self.router().load()
        return all(key in status and "phase" in status[key] for key in [*self.stack.apps, MANAGEMENT])

    def step_bootstrap(self, _identity):
        record = self.layout.state / "bootstrap.json"
        data = json.loads(record.read_text()) if record.exists() else {}
        # The dashboard admin is created on the console; without a terminal it stays pending.
        if not data.get("dashboardAdmin") and sys.stdin.isatty() and os.environ.get("SP_NO_TTY") != "1":
            self.setup_dashboard_admin()
            data["dashboardAdmin"] = True
        data.setdefault("dashboardAdmin", False)
        data["appSetup"] = {app: data.get("appSetup", {}).get(app, False) for app in self.stack.apps}
        data["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        atomic_json(record, data)

    def probe_bootstrap(self, _identity):
        return (self.layout.state / "bootstrap.json").is_file()

    def step_verify(self, identity):
        status = self.router().load()
        results = {"installation": identity, "release": self.release.version, "apps": {}, "pending": {}}
        for app in self.stack.apps:
            if not self.stack.healthy(app):
                raise StateError(f"{app}: not healthy")
            entry = status.get(app, {})
            if entry.get("phase") == "aktiv":
                results["apps"][app] = self.stack.verify_app(app, entry["hostname"])
            else:
                results["pending"][app] = {"phase": entry.get("phase"), "reason": entry.get("reason", "")}
            for service in APPS[app].services:
                container = self.stack.container(app, service)
                if any(container["NetworkSettings"]["Ports"].values()):
                    raise StateError(f"{app}/{service}: published host port")
        infra = json.loads((self.layout.generated / "infra.yml").read_text())
        if "docker.sock" in json.dumps(infra["services"]["dashboard"]):
            raise StateError("Dashboard must not receive the Docker socket")
        results["openAcceptanceItems"] = [list(item) for item in self.release.open_items()]
        atomic_json(self.layout.state / "verified.json", results)

    def probe_verify(self, identity):
        path = self.layout.state / "verified.json"
        return path.exists() and json.loads(path.read_text()).get("installation") == identity

    def steps(self):
        return [Step("host", self.step_host, self.probe_host),
                Step("render", self.step_render, self.probe_render),
                Step("images", self.step_images, self.probe_images),
                Step("infrastructure", self.step_infrastructure, self.probe_infrastructure),
                Step("service", self.step_service, self.probe_service),
                Step("apps", self.step_apps, self.probe_apps),
                Step("routes", self.step_routes, self.probe_routes),
                Step("bootstrap", self.step_bootstrap, self.probe_bootstrap),
                Step("verify", self.step_verify, self.probe_verify)]

    def apply(self, reconfigure=False):
        self.layout.prepare()
        installation = Installation(self.layout.state)
        if reconfigure and installation.path.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            os.replace(installation.path, self.layout.state / f"installation-{stamp}.json")
        return installation.run(self.plan(), self.steps())

    # --- domain transaction drivers -------------------------------------------
    def _domain_preflight(self, old, candidate):
        from .dnscheck import evaluate
        platform = self.config["platform"]
        for app, hostname in candidate.items():
            if old.get(app) != hostname:
                result = evaluate(hostname, platform["public_ipv4"], platform.get("public_ipv6"),
                                  platform.get("resolvers", ()))
                if result["dns"] != "ok":
                    raise StateError(f"DNS für {hostname}: {result['reason']}")
        return True

    def _domain_activate(self, domains):
        self.stack.render(domains)
        self.stack.write_management_catalogue(domains)
        for app in self.stack.apps:
            self.stack.start(app)  # compose recreates only services whose configuration changed
        router = Router(self.stack, self.domains())
        router.check_dns()
        router.apply_routes()

    def _domain_verify(self, domains):
        router = Router(self.stack, self.domains())
        status = router.reconcile(wait_seconds=int(os.environ.get("SP_CERT_WAIT", "150")))
        for app, hostname in domains.items():
            if status.get(app, {}).get("hostname") != hostname or status[app].get("phase") != "aktiv":
                return False
            self.stack.verify_app(app, hostname)
        return True

    def change_domain(self, app, hostname):
        result = self.domains().change(app, hostname)
        data = dict(self.config)
        data["apps"] = {key: dict(value) for key, value in self.config["apps"].items()}
        data["apps"][app]["hostname"] = hostname
        cfg.write(data, self.config_path)
        return result

    # --- console bootstrap ----------------------------------------------------
    def setup_dashboard_admin(self, username=None):
        """Create the personal platform admin inside the dashboard container (owner UID, own TTY)."""
        import re
        if not username:
            with open("/dev/tty", "r+") as tty:
                tty.write("Persönlicher Benutzername für die Plattformverwaltung: ")
                tty.flush()
                username = tty.readline().strip()
        if not re.fullmatch(r"[a-z][a-z0-9._-]{2,40}", username):
            raise StateError("Benutzername: 3–41 Zeichen, Kleinbuchstaben, Ziffern, . _ -")
        # Short-lived container on the same state volume and UID; works before the first admin exists.
        self.stack.compose("infra", "run", "--rm", "--no-deps", "--pull", "never", "dashboard", "python", "-m",
                           "schulplattform.dashboard", "setup", "--state-dir", "/state", "--username", username,
                           tty=True, capture=False)
        self.stack.compose("infra", "restart", "dashboard")
