"""Production deployment service: fixed, authenticated actions over a Unix socket.

Runs on the host (systemd, root) and is the only component that talks to
Docker. The dashboard container reaches it through the mounted socket and a
shared HMAC key; it can neither pass argv, paths, compose fragments nor shell.
Every request reloads the configuration and re-verifies the release signature.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time

from . import config as cfg
from .catalogue import APPS
from .deployment import ACTIONS, APPS as KNOWN_APPS, DeploymentBusy, EXTENDED, Gate, PLATFORM, Server
from .routing import MANAGEMENT
from .secrets import SecretStore
from .state import StateError


class ProductionEngine:
    def __init__(self, factory):
        self.factory = factory  # () -> production.Platform

    # --- helpers --------------------------------------------------------------
    def drain(self, platform, app_id, action):
        app = APPS[app_id]
        if not app.drain:
            return {}
        container = platform.stack.container(app_id, "app")
        if not container or not container["State"].get("Running"):
            return {}
        headers = "{method:'POST',headers:{'X-Abgen-Request':'1'}}" if app.drain == "worksheet" else "{method:'POST'}"
        source = (f"fetch('http://127.0.0.1:{app.port}/_platform/{action}',{headers})"
                  ".then(async r=>{if(!r.ok)process.exit(1);process.stdout.write(await r.text());})"
                  ".catch(()=>process.exit(1));")
        return json.loads(platform.stack.command([platform.stack.docker, "exec", container["Id"], "node", "-e", source]))

    def status(self, platform, app_id, routing=None):
        installed = app_id in platform.stack.apps
        state = platform.stack.service_state(app_id, "app") if installed else {"running": False, "health": "absent"}
        health = state["health"]
        if installed and state["running"]:
            for service in APPS[app_id].services[1:] + APPS[app_id].database_services:
                if platform.stack.service_state(app_id, service)["health"] != "healthy":
                    health = "degraded"
        entry = (routing or {}).get(app_id, {})
        manifest = platform.release.manifests.get(app_id, {})
        return {"app": app_id, "installed": installed, "running": state["running"], "health": health,
                "image": manifest.get("image"), "version": platform.release.version if installed else None,
                "hostname": entry.get("hostname"), "phase": entry.get("phase"), "dns": entry.get("dns"),
                "reason": entry.get("reason"), "certificate": entry.get("certificate"),
                "maintenance": bool(entry.get("maintenance"))}

    def overview(self, platform):
        routing = platform.router().load()
        smtp = {k: v for k, v in platform.config["smtp"].items()}
        smtp["passwordSet"] = SecretStore(platform.layout.secrets).path("smtp-password").exists()
        backups_path = platform.layout.backups / "status.json"
        return {
            "release": platform.release.version, "releaseDigest": platform.release.digest,
            "apps": {app: self.status(platform, app, routing) for app in sorted(KNOWN_APPS)},
            "management": routing.get(MANAGEMENT, {}),
            "smtp": smtp,
            "backups": json.loads(backups_path.read_text()) if backups_path.exists() else {},
            "backupConfig": platform.config["backup"],
            "openAcceptanceItems": [list(item) for item in platform.release.open_items()],
            "updates": self.update_check(platform),
            "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def update_check(self, platform):
        from .release_bundle import Release
        installed = platform.release.version
        candidates = []
        inbox = platform.layout.releases
        for path in sorted(inbox.iterdir()) if inbox.is_dir() else []:
            if path.is_dir() and path.name != installed and (path / "bundle.json").is_file():
                try:
                    release = Release(path, platform.trusted_key)
                    candidates.append({"version": release.version, "verified": True,
                                       "openItems": len(release.open_items())})
                except Exception:
                    candidates.append({"version": path.name, "verified": False})
        return {"installed": installed, "available": candidates}

    # --- dispatch ---------------------------------------------------------------
    def execute(self, action, app, params=None):
        platform = self.factory()
        if action in ACTIONS:
            if app not in platform.stack.apps:
                if action == "status":
                    return self.status(platform, app)
                raise StateError("App is not installed")
            if action == "status":
                return self.status(platform, app, platform.router().load())
            if action == "stop":
                if APPS[app].drain == "quiz":
                    pending = self.drain(platform, app, "prepare-stop")
                    if pending.get("activeGames"):
                        self.drain(platform, app, "cancel-stop")
                        raise DeploymentBusy("Active games must finish before stop")
                platform.router().set_maintenance(app, True)
                if APPS[app].drain == "worksheet":
                    result = self.drain(platform, app, "prepare-stop")
                    if result and (result.get("pendingUpdates") or result.get("pendingBytes")):
                        raise StateError("Worksheet collaboration is not drained")
                platform.stack.stop(app)
            else:
                platform.stack.start(app)
                if APPS[app].drain:
                    self.drain(platform, app, "cancel-stop")
                if not platform.stack.healthy(app):
                    raise StateError("App failed readiness")
                platform.router().set_maintenance(app, False)
            return self.status(platform, app, platform.router().load())
        params = params or {}
        if action == "overview":
            return self.overview(platform)
        if action == "dns-recheck":
            only = None if app == PLATFORM else {app}
            platform.router().reconcile(only=only, wait_seconds=90)
            return self.overview(platform)
        if action == "domain-change":
            if app not in platform.stack.apps:
                raise StateError("App is not installed")
            platform.change_domain(app, params["hostname"])
            return self.status(platform, app, platform.router().load())
        if action == "maintenance":
            platform.router().set_maintenance(app, params["enabled"])
            return self.status(platform, app, platform.router().load())
        if action == "smtp-update":
            data = dict(platform.config)
            data["smtp"] = {"mode": "relay", **{k: v for k, v in params.items() if v != "" or k != "username"}}
            cfg.validate(data)
            cfg.write(data, platform.config_path)
            platform = self.factory()
            platform.stack.render(platform.current_domains())
            platform.stack.infrastructure_up()
            return {"smtp": data["smtp"]}
        if action == "smtp-password":
            SecretStore(platform.layout.secrets).replace("smtp-password", params["password"])
            if platform.stack.mail_mode == "relay":
                platform.stack.render(platform.current_domains())
                platform.stack.compose("infra", "up", "-d", "--force-recreate", "--wait", "mailrelay")
            return {"passwordSet": True}
        if action == "smtp-test":
            return self.smtp_test(platform, params["recipient"])
        if action == "backup-now":
            from .backups import BackupService
            return BackupService(platform).backup(app)
        if action == "update-check":
            return self.update_check(platform)
        if action == "uninstall":
            return self.uninstall(platform, app)
        if action == "enable":
            return self.enable(platform, app)
        if action == "purge":
            return self.purge(platform, app, params["confirm"])
        raise ValueError("Unknown action")

    def uninstall(self, platform, app):
        """Remove containers and route; data stays in its volumes and in a fresh archive."""
        from .backups import BackupService
        if app not in platform.stack.apps:
            raise StateError("App is not installed")
        archive = BackupService(platform).backup(app)
        if APPS[app].drain == "quiz":
            pending = self.drain(platform, app, "prepare-stop")
            if pending.get("activeGames"):
                self.drain(platform, app, "cancel-stop")
                raise DeploymentBusy("Active games must finish before uninstall")
        platform.router().set_maintenance(app, True)
        platform.stack.compose(app, "down", "--remove-orphans")  # never -v: volumes are kept
        platform.set_enabled(app, False)
        platform = self.factory()
        platform.stack.render(platform.current_domains())
        platform.stack.infrastructure_up()
        platform.stack.write_management_catalogue(platform.current_domains())
        platform.router().apply_routes()
        return {"app": app, "installed": False, "archive": archive["archive"], "volumesKept": True}

    def enable(self, platform, app):
        """Re-activate an app: existing volumes are reused, no bootstrap is repeated."""
        if app in platform.stack.apps:
            return self.status(platform, app, platform.router().load())
        platform.set_enabled(app, True)
        platform = self.factory()
        domains = platform.current_domains()
        platform.stack.render(domains)
        platform.stack.pull()
        platform.stack.infrastructure_up()
        platform.stack.migrate(app)
        platform.stack.start(app)
        platform.stack.write_management_catalogue(domains)
        router = platform.router()
        router.set_maintenance(app, False)
        router.reconcile(only={app}, wait_seconds=90)
        return self.status(platform, app, router.load())

    def purge(self, platform, app, confirmation):
        """Irreversible: delete the volumes of an uninstalled app after an archive exists."""
        from .backups import BackupService
        if confirmation != app:
            raise StateError("Confirmation does not match the app id")
        if app in platform.stack.apps:
            raise StateError("Uninstall the app before deleting its data")
        archive = BackupService(platform).latest(app)
        removed = []
        listing = platform.stack.command([platform.stack.docker, "volume", "ls", "-q", "--filter",
                                          f"label=com.docker.compose.project=sp-{app}"])
        for volume in listing.split():
            if volume.startswith(f"sp-{app}_"):
                platform.stack.command([platform.stack.docker, "volume", "rm", volume])
                removed.append(volume)
        return {"app": app, "removedVolumes": removed, "archiveKept": archive.name}

    def smtp_test(self, platform, recipient):
        mode = platform.stack.mail_mode
        if mode == "none":
            raise StateError("Mailversand ist deaktiviert")
        container = platform.stack.container("infra", "mailrelay")
        if not container or not container["State"].get("Running"):
            raise StateError("Mail-Relay läuft nicht")
        sender = platform.config["smtp"].get("sender") or "noreply@" + platform.config["platform"]["management_domain"]
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (f"From: {sender}\nTo: {recipient}\nSubject: Schulplattform Testnachricht\n"
                   f"Content-Type: text/plain; charset=utf-8\n\nTestversand der Schulplattform ({stamp}).\n")
        since = str(int(time.time()) - 1)
        if mode == "relay":
            argv = ["/usr/sbin/sendmail", "-t", "-f", sender]
        else:
            argv = ["/mailpit", "sendmail", "-S", "127.0.0.1:1025", "-t", "-f", sender]
        import subprocess
        result = subprocess.run([platform.stack.docker, "exec", "-i", container["Id"], *argv], input=message,
                                text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise StateError("Übergabe an das Mail-Relay fehlgeschlagen")
        if mode == "sink":
            return {"status": "sink", "detail": "In den Test-Sink zugestellt (kein externer Versand)."}
        deadline = time.time() + 25
        while time.time() < deadline:
            logs = subprocess.run([platform.stack.docker, "logs", "--since", since, container["Id"]],
                                  text=True, capture_output=True, timeout=30)
            text = logs.stdout + logs.stderr
            for line in text.splitlines():
                if f"to=<{recipient}>" in line and "status=" in line:
                    match = re.search(r"status=(\w+)", line)
                    state = match.group(1) if match else "unknown"
                    detail = "Vom Anbieter angenommen." if state == "sent" else \
                        "Zustellung verzögert oder abgelehnt; Relay-Protokoll prüfen."
                    return {"status": state, "detail": detail}
            time.sleep(2)
        return {"status": "queued", "detail": "In der Warteschlange; noch keine Antwort des Anbieters."}


def main():
    from .production import Platform
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--trusted-key", required=True, type=Path)
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--allowed-uid", required=True, type=int)
    args = parser.parse_args()
    factory = lambda: Platform(args.config, args.root, args.bundle, args.trusted_key, provision_host=False)
    platform = factory()
    key = platform.deployment_key().encode()
    gate = Gate(platform.layout.state / "deployment-audit.sqlite3", key, ProductionEngine(factory))
    if args.socket.exists() and args.socket.is_socket():
        args.socket.unlink()  # stale socket from a previous run of this service
    with Server(args.socket, gate, args.allowed_uid) as server:
        os.chown(args.socket, 0, 10001) if os.geteuid() == 0 else None
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
