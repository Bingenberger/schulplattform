"""Durable domain configuration transaction with compensating rollback.

DNS ownership, certificates, callback registration and application-specific
checks are mandatory driver responsibilities. This core never edits DNS.
"""
import json
from pathlib import Path
import re
import uuid

from .proxy import hostname
from .storage import atomic_json, exclusive


class DomainError(RuntimeError):
    pass


class Domains:
    def __init__(self, directory, initial, management_domain, preflight, activate, verify, operation_lock=None):
        self.directory = Path(directory)
        self.path = self.directory / "current.json"
        self.pending = self.directory / "pending.json"
        self.operation_lock = Path(operation_lock) if operation_lock else self.directory / "operation.lock"
        self.management_domain = hostname(management_domain)
        self.preflight, self.activate, self.verify = preflight, activate, verify
        self.validate(initial)
        with exclusive(self.directory / "domains.lock"):
            if not self.path.exists():
                atomic_json(self.path, {"generation": str(uuid.uuid4()), "domains": initial})
            else:
                self.validate(json.loads(self.path.read_text())["domains"])

    def validate(self, domains):
        if not isinstance(domains, dict) or not domains:
            raise ValueError("Expected app/domain mapping")
        seen = {self.management_domain}
        for app, domain in domains.items():
            if not re.fullmatch("[a-z][a-z0-9-]{0,40}", app):
                raise ValueError("Invalid app ID")
            hostname(domain)
            if domain in seen:
                raise ValueError("Duplicate or administrative domain")
            seen.add(domain)

    def _recover(self):
        if not self.pending.exists():
            return
        pending = json.loads(self.pending.read_text())
        if pending["status"] in ("committed", "rolled-back"):
            return
        current = json.loads(self.path.read_text())
        if current == pending["candidate"]:
            pending["status"] = "committed"
            atomic_json(self.pending, pending)
            return
        try:
            self.activate(pending["old"]["domains"])
            if self.verify(pending["old"]["domains"]) is not True:
                raise DomainError("Rollback verification failed")
        except BaseException:
            pending["status"] = "recovery-required"
            atomic_json(self.pending, pending)
            raise DomainError("Domain recovery failed; administrative access must be used") from None
        atomic_json(self.path, pending["old"])
        pending["status"] = "rolled-back"
        atomic_json(self.pending, pending)

    def recover(self):
        with exclusive(self.operation_lock):
            with exclusive(self.directory / "domains.lock"):
                self._recover()

    def change(self, app, domain):
        with exclusive(self.operation_lock):
            return self._change_locked(app, domain)

    def _change_locked(self, app, domain):
        with exclusive(self.directory / "domains.lock"):
            self._recover()
            old = json.loads(self.path.read_text())
            if app not in old["domains"]:
                raise ValueError("Unknown app")
            candidate = {"generation": str(uuid.uuid4()), "domains": old["domains"] | {app: domain}}
            self.validate(candidate["domains"])
            if candidate["domains"] == old["domains"]:
                return old
            if self.preflight(old["domains"], candidate["domains"]) is not True:
                raise DomainError("Domain preflight failed; no change applied")
            pending = {"old": old, "candidate": candidate, "status": "applying"}
            atomic_json(self.pending, pending)
            try:
                self.activate(candidate["domains"])
                if self.verify(candidate["domains"]) is not True:
                    raise DomainError("Domain verification failed")
            except BaseException:
                self._recover()
                raise DomainError("Domain change rejected; previous configuration restored") from None
            atomic_json(self.path, candidate)  # durable commit point
            pending["status"] = "committed"
            atomic_json(self.pending, pending)
            return candidate
