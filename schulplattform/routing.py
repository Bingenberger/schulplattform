"""Partial readiness: route only DNS-verified hostnames and track each app's phase.

Phases per app (and the management domain):
  dns-ausstehend        no or wrong DNS record; no route, no certificate order
  zertifikat-ausstehend DNS correct, route configured, certificate not (yet) valid
  aktiv                 valid certificate and TLS readiness through the proxy
  fehler                DNS resolver failure or readiness failure after a valid certificate
"""
from datetime import datetime, timezone
import json
import time

from . import certs, dnscheck
from .storage import atomic_json, exclusive

MANAGEMENT = "_management"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Router:
    def __init__(self, stack, domains_store, resolve=dnscheck.system_resolve, ask=dnscheck.query,
                 clock=time.monotonic, sleep=time.sleep):
        self.stack = stack
        self.domains = domains_store
        self.resolve, self.ask, self.clock, self.sleep = resolve, ask, clock, sleep
        self.path = stack.layout.domains / "status.json"

    def current(self):
        return json.loads((self.stack.layout.domains / "current.json").read_text())["domains"]

    def load(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self, status):
        atomic_json(self.path, status)

    def hostnames(self):
        domains = self.current()
        names = {app: domains[app] for app in self.stack.apps}
        names[MANAGEMENT] = self.stack.config["platform"]["management_domain"]
        return names

    def check_dns(self, only=None):
        platform = self.stack.config["platform"]
        previous = self.load()
        status = {}
        for key, hostname in self.hostnames().items():
            entry = dict(previous.get(key, {}))
            if only is None or key in only or entry.get("hostname") != hostname:
                result = dnscheck.evaluate(hostname, platform["public_ipv4"], platform.get("public_ipv6"),
                                           platform.get("resolvers", ()), self.resolve, self.ask)
                entry.update(result, checkedAt=now())
                if result["dns"] != "ok":
                    entry.pop("certificate", None)
            status[key] = entry
        self.save(status)
        return status

    def apply_routes(self):
        changed = self.stack.write_caddyfile(self.current(), self.stack.routed(self.current()))
        if changed:
            self.stack.reload_proxy()
        return changed

    def reconcile(self, only=None, wait_seconds=120):
        """DNS check -> routes -> reachability -> certificate -> TLS readiness. Never loops on failures."""
        with exclusive(self.stack.layout.domains / "routing.lock"):
            status = self.check_dns(only)
            self.apply_routes()
            platform = self.stack.config["platform"]
            probe = dnscheck.ReachabilityProbe(self.stack.layout.check)
            pending = {key for key, entry in status.items() if entry.get("dns") == "ok"}
            for key in pending:
                status[key]["port80"] = probe.probe(status[key]["hostname"], platform["public_ipv4"])
            deadline = self.clock() + wait_seconds
            while True:
                for key in list(pending):
                    certificate = certs.find(self.stack.layout.caddy_data, status[key]["hostname"])
                    if certificate and certificate["valid"]:
                        status[key]["certificate"] = certificate
                        pending.discard(key)
                if not pending or self.clock() >= deadline:
                    break
                self.sleep(5)
            for key, entry in status.items():
                entry["phase"] = self.phase(key, entry)
            self.save(status)
            return status

    def phase(self, key, entry):
        if entry.get("dns") == "error":
            return "fehler"
        if entry.get("dns") != "ok":
            return "dns-ausstehend"
        certificate = entry.get("certificate")
        if not certificate or not certificate.get("valid"):
            return "zertifikat-ausstehend"
        if key == MANAGEMENT:
            return "aktiv"
        if entry.get("maintenance"):
            return "wartung"
        try:
            from .catalogue import APPS
            status, _ = self.stack.request(entry["hostname"], APPS[key].ready)
            return "aktiv" if status == 200 else "fehler"
        except Exception:
            return "fehler"

    def set_maintenance(self, app, enabled):
        with exclusive(self.stack.layout.domains / "routing.lock"):
            status = self.load()
            status.setdefault(app, {})["maintenance"] = bool(enabled)
            self.save(status)
            self.apply_routes()
