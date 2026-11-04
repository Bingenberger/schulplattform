"""Ubuntu 24.04 host provisioning: Docker from the official repository, firewall, units.

Every step is idempotent and has a probe that checks the real effect. Nothing
pre-existing is overwritten: foreign Docker, proxy or database installations
stop the installation in preflight (installer.blockers). SSH configuration is
never touched; the firewall keeps every port sshd actually listens on open.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

DOCKER_GPG_URL = "https://download.docker.com/linux/ubuntu/gpg"
DOCKER_GPG_FINGERPRINT = "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
DOCKER_KEYRING = Path("/etc/apt/keyrings/docker.asc")
DOCKER_SOURCES = Path("/etc/apt/sources.list.d/docker.sources")
DOCKER_PACKAGES_VERSION = "5:29.1.3-1~ubuntu.24.04~noble"
COMPOSE_PLUGIN_VERSION = "2.40.3-1~ubuntu.24.04~noble"
BASE_PACKAGES = ("ca-certificates", "curl", "gnupg", "python3-venv", "ufw", "sqlite3")
DAEMON_JSON = Path("/etc/docker/daemon.json")
DAEMON_CONFIG = {"log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"},
                 "live-restore": True, "no-new-privileges": True}
MARKER = "host.json"
UNIT_DIR = Path("/etc/systemd/system")


class HostError(RuntimeError):
    pass


def run(argv, check=True, input=None, timeout=1800, env=None):
    result = subprocess.run(argv, input=input, text=True, capture_output=True, timeout=timeout,
                            env=(os.environ | (env or {})))
    if check and result.returncode:
        raise HostError(f"{Path(argv[0]).name} {' '.join(argv[1:3])} failed (exit {result.returncode})")
    return result


APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a"}


class Provisioner:
    def __init__(self, state_dir, runner=run):
        self.state_dir = Path(state_dir)
        self.run = runner

    # --- marker ------------------------------------------------------------------
    def marker(self):
        path = self.state_dir / MARKER
        return json.loads(path.read_text()) if path.exists() else {}

    def mark(self, **values):
        from .storage import atomic_json
        data = self.marker() | values
        atomic_json(self.state_dir / MARKER, data)

    # --- packages ----------------------------------------------------------------
    def installed(self, package):
        result = self.run(["dpkg-query", "-W", "-f=${Status} ${Version}", package], check=False)
        return result.stdout.split(" ")[3] if result.returncode == 0 and "install ok installed" in result.stdout else None

    def base_packages(self):
        missing = [p for p in BASE_PACKAGES if not self.installed(p)]
        if missing:
            self.run(["apt-get", "update", "-q"], env=APT_ENV)
            self.run(["apt-get", "install", "-y", "-q", "--no-install-recommends", *missing], env=APT_ENV)

    def base_packages_ok(self):
        return all(self.installed(p) for p in BASE_PACKAGES)

    # --- Docker ---------------------------------------------------------------------
    def docker_repository(self):
        with urllib.request.urlopen(DOCKER_GPG_URL, timeout=30) as response:
            key = response.read(65536)
        with tempfile.TemporaryDirectory() as home:
            listing = self.run(["gpg", "--homedir", home, "--show-keys", "--with-colons"], input=key.decode()).stdout
        fingerprints = re.findall(r"^fpr:+([0-9A-F]{40}):", listing, re.M)
        if DOCKER_GPG_FINGERPRINT not in fingerprints:
            raise HostError("Docker repository key fingerprint mismatch; refusing to trust it")
        DOCKER_KEYRING.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        DOCKER_KEYRING.write_bytes(key)
        os.chmod(DOCKER_KEYRING, 0o644)
        codename = self.run(["sh", "-c", ". /etc/os-release && printf %s \"$VERSION_CODENAME\""]).stdout
        if codename != "noble":
            raise HostError("Only Ubuntu 24.04 (noble) is supported")
        DOCKER_SOURCES.write_text("Types: deb\nURIs: https://download.docker.com/linux/ubuntu\n"
                                  f"Suites: {codename}\nComponents: stable\nArchitectures: amd64\n"
                                  f"Signed-By: {DOCKER_KEYRING}\n")
        os.chmod(DOCKER_SOURCES, 0o644)
        self.run(["apt-get", "update", "-q"], env=APT_ENV)

    def docker_repository_ok(self):
        return DOCKER_KEYRING.is_file() and DOCKER_SOURCES.is_file()

    def docker(self):
        packages = [f"docker-ce={DOCKER_PACKAGES_VERSION}", f"docker-ce-cli={DOCKER_PACKAGES_VERSION}",
                    "containerd.io", "docker-buildx-plugin", f"docker-compose-plugin={COMPOSE_PLUGIN_VERSION}"]
        if not DAEMON_JSON.exists():
            DAEMON_JSON.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            DAEMON_JSON.write_text(json.dumps(DAEMON_CONFIG, indent=2) + "\n")
        self.run(["apt-get", "install", "-y", "-q", "--no-install-recommends", *packages], env=APT_ENV)
        self.run(["apt-mark", "hold", "docker-ce", "docker-ce-cli", "docker-compose-plugin"])
        self.run(["systemctl", "enable", "--now", "docker.service"])
        self.mark(dockerInstalledByPlatform=True, dockerVersion=DOCKER_PACKAGES_VERSION)

    def docker_ok(self):
        return (self.installed("docker-ce") == DOCKER_PACKAGES_VERSION
                and self.installed("docker-compose-plugin") == COMPOSE_PLUGIN_VERSION
                and self.run(["docker", "info", "--format", "{{.ServerVersion}}"], check=False).returncode == 0)

    # --- firewall -----------------------------------------------------------------
    def ssh_ports(self):
        output = self.run(["ss", "-H", "-ltnp"], check=False).stdout
        ports = set()
        for line in output.splitlines():
            if '"sshd"' in line or "sshd" in line.split()[-1]:
                match = re.search(r":(\d+)\s", line.split()[3] + " ")
                if match:
                    ports.add(int(match.group(1)))
        return sorted(ports) or [22]

    def firewall(self):
        for port in self.ssh_ports():
            self.run(["ufw", "allow", f"{port}/tcp"])
        for port in (80, 443):
            self.run(["ufw", "allow", f"{port}/tcp"])
        self.run(["ufw", "default", "deny", "incoming"])
        self.run(["ufw", "default", "allow", "outgoing"])
        self.run(["ufw", "--force", "enable"])
        self.mark(firewallManagedByPlatform=True, sshPorts=self.ssh_ports())

    def firewall_ok(self):
        status = self.run(["ufw", "status"], check=False).stdout
        return "Status: active" in status and all(f"{p}/tcp" in status for p in [*self.ssh_ports(), 80, 443])

    # --- systemd units ---------------------------------------------------------------
    def install_units(self, units):
        changed = False
        for name, text in units.items():
            path = UNIT_DIR / name
            if not path.exists() or path.read_text() != text:
                path.write_text(text)
                os.chmod(path, 0o644)
                changed = True
        if changed:
            self.run(["systemctl", "daemon-reload"])
        for name in units:
            if name.endswith(".timer") or (name.endswith(".service") and not name.endswith("@.service")
                                           and "oneshot" not in units[name]):
                self.run(["systemctl", "enable", "--now", name])
        return changed

    def units_ok(self, units):
        for name, text in units.items():
            path = UNIT_DIR / name
            if not path.exists() or path.read_text() != text:
                return False
            if name.endswith(".timer") or ("oneshot" not in text and name.endswith(".service")):
                if self.run(["systemctl", "is-active", "--quiet", name], check=False).returncode:
                    return False
        return True


def units(root, platform_dir, socket_path, config_path, bundle_dir, trusted_key):
    python = f"{platform_dir}/.venv/bin/python"
    common = (f"WorkingDirectory={platform_dir}\nEnvironment=PYTHONDONTWRITEBYTECODE=1\n"
              "ProtectHome=read-only\nPrivateTmp=true\nNoNewPrivileges=true\n")
    cli = (f"{python} -m schulplattform.installer --config {config_path} --root {root} "
           f"--bundle {bundle_dir} --trusted-key {trusted_key}")
    return {
        "schulplattform-deploy.service": (
            "[Unit]\nDescription=Schulplattform deployment service (fixed actions, Unix socket)\n"
            "After=docker.service network-online.target\nRequires=docker.service\n\n"
            "[Service]\nType=simple\n" + common +
            f"ExecStart={python} -m schulplattform.deployment_service --config {config_path} --root {root} "
            f"--bundle {bundle_dir} --trusted-key {trusted_key} --socket {socket_path} --allowed-uid 10001\n"
            "Restart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n"),
        "schulplattform-reconcile.service": (
            "[Unit]\nDescription=Schulplattform DNS/certificate reconciliation\nAfter=docker.service\n\n"
            "[Service]\nType=oneshot\n" + common + f"ExecStart={cli} reconcile --quiet\n"),
        "schulplattform-reconcile.timer": (
            "[Unit]\nDescription=Re-check pending DNS entries hourly\n\n"
            "[Timer]\nOnBootSec=5min\nOnUnitActiveSec=1h\nRandomizedDelaySec=5min\n\n"
            "[Install]\nWantedBy=timers.target\n"),
        "schulplattform-backup.service": (
            "[Unit]\nDescription=Schulplattform daily backup\nAfter=docker.service\n\n"
            "[Service]\nType=oneshot\n" + common + f"ExecStart={cli} backup --all --quiet\n"),
        "schulplattform-backup.timer": (
            "[Unit]\nDescription=Schulplattform daily backup\n\n"
            "[Timer]\nOnCalendar=*-*-* {schedule}:00\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n"),
    }


def copy_if_changed(source, destination, mode):
    destination = Path(destination)
    if destination.exists() and destination.read_bytes() == Path(source).read_bytes():
        return False
    shutil.copyfile(source, destination)
    os.chmod(destination, mode)
    return True
