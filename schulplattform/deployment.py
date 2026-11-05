"""Authenticated Unix-socket deployment protocol with fixed actions and replay defense."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import socketserver
import sqlite3
import struct
import time

from .catalogue import APP_IDS


ACTIONS = {"status", "start", "stop"}
APPS = set(APP_IDS)
PLATFORM = "_platform"
HOSTNAME = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]([a-z0-9-]{0,61}[a-z0-9])?$")
EMAIL = re.compile(r"^[^@\s<>\"']{1,64}@[a-z0-9.-]{1,253}$")


def _text(maximum, pattern=None, allow_empty=False):
    def check(value):
        return (isinstance(value, str) and (allow_empty or value) and len(value) <= maximum
                and "\n" not in value and "\r" not in value and (not pattern or not value or pattern.fullmatch(value)))
    return check


# Extended fixed actions: target apps and an exact parameter schema each.
EXTENDED = {
    "overview": ({PLATFORM}, {}),
    "dns-recheck": (APPS | {PLATFORM}, {}),
    "domain-change": (APPS, {"hostname": _text(253, HOSTNAME)}),
    "maintenance": (APPS, {"enabled": lambda v: isinstance(v, bool)}),
    "smtp-update": ({PLATFORM}, {"host": _text(253, HOSTNAME), "port": lambda v: type(v) is int and 0 < v < 65536,
                                 "security": lambda v: v in ("starttls", "tls"),
                                 "username": _text(254, re.compile(r"^\S*$"), allow_empty=True),
                                 "sender": _text(320, EMAIL), "sender_name": _text(80, re.compile(r'^[^<>"]*$'))}),
    "smtp-password": ({PLATFORM}, {"password": _text(256)}),
    "smtp-test": ({PLATFORM}, {"recipient": _text(320, EMAIL)}),
    "backup-now": (APPS, {}),
    "update-check": ({PLATFORM}, {}),
    "uninstall": (APPS, {}),
    "enable": (APPS, {}),
    "purge": (APPS, {"confirm": _text(40, re.compile(r"^[a-z][a-z-]{0,39}$"))}),
}


def valid_params(action, app, params):
    if action in ACTIONS:
        return app in APPS and params is None
    targets, schema = EXTENDED.get(action, (None, None))
    if targets is None or app not in targets:
        return False
    if schema and not isinstance(params, dict):
        return False
    params = params or {}
    return isinstance(params, dict) and set(params) == set(schema) and all(schema[k](params[k]) for k in schema)


class DeploymentBusy(ValueError):
    """An active workload prevents a safe stop."""


def canonical(request):
    return json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def signed_request(key, action, app, clock=time.time, params=None):
    if not valid_params(action, app, params) or len(key) < 32:
        raise ValueError("Invalid deployment request")
    request = {"action": action, "app": app, "at": int(clock()), "nonce": secrets.token_hex(24)}
    if params is not None:
        request["params"] = params
    request["signature"] = hmac.new(key, canonical(request), hashlib.sha256).hexdigest()
    return request


class Gate:
    def __init__(self, database, key, engine, clock=time.time):
        if len(key) < 32:
            raise ValueError("Deployment key too short")
        self.key, self.engine, self.clock = key, engine, clock
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent = self.database.parent.lstat()
        if self.database.parent.is_symlink() or parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise ValueError("Deployment audit directory must be private and owned by this user")
        if self.database.is_symlink():
            raise ValueError("Deployment audit DB symlink forbidden")
        if not self.database.exists():
            fd = os.open(self.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        if self.database.stat().st_uid != os.geteuid() or self.database.stat().st_mode & 0o077:
            raise ValueError("Deployment audit DB must be private")
        with sqlite3.connect(self.database) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests(
                nonce TEXT PRIMARY KEY, at INTEGER NOT NULL, action TEXT NOT NULL,
                app TEXT NOT NULL, outcome TEXT NOT NULL)""")

    def dispatch(self, request):
        if (not isinstance(request, dict) or
                set(request) - {"params"} != {"action", "app", "at", "nonce", "signature"} or
                not isinstance(request["action"], str) or not isinstance(request["app"], str) or
                not valid_params(request["action"], request["app"], request.get("params")) or
                type(request["at"]) is not int or abs(int(self.clock()) - request["at"]) > 60 or
                not isinstance(request["nonce"], str) or not re.fullmatch("[a-f0-9]{48}", request["nonce"]) or
                not isinstance(request["signature"], str) or not re.fullmatch("[a-f0-9]{64}", request["signature"])):
            return {"ok": False, "error": "invalid-request"}
        body = {key: value for key, value in request.items() if key != "signature"}
        expected = hmac.new(self.key, canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request["signature"]):
            return {"ok": False, "error": "unauthorized"}
        with sqlite3.connect(self.database, timeout=5) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM requests WHERE at<?", (int(self.clock()) - 3600,))
            try:
                db.execute("INSERT INTO requests VALUES(?,?,?,?,?)",
                           (request["nonce"], request["at"], request["action"], request["app"], "accepted"))
            except sqlite3.IntegrityError:
                return {"ok": False, "error": "replay"}
        try:
            if "params" in request or request["action"] in EXTENDED:
                result = self.engine.execute(request["action"], request["app"], request.get("params") or {})
            else:
                result = self.engine.execute(request["action"], request["app"])
            response = {"ok": True, "result": result}
            outcome = "completed"
        except DeploymentBusy:
            response, outcome = {"ok": False, "error": "busy"}, "blocked"
        except Exception:
            response, outcome = {"ok": False, "error": "operation-failed"}, "failed"
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE requests SET outcome=? WHERE nonce=?", (outcome, request["nonce"]))
        return response


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(3)
        credentials = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", credentials)
        if uid != self.server.allowed_uid:
            self.wfile.write(b'{"ok":false,"error":"peer-denied"}\n')
            return
        request = None
        try:
            raw = self.rfile.readline(4097)
            if len(raw) > 4096 or not raw.endswith(b"\n"):
                raise ValueError()
            request = json.loads(raw)
            response = self.server.gate.dispatch(request)
        except (ValueError, TypeError, OSError):
            response = {"ok": False, "error": "invalid-request"}
        nonce = request.get("nonce") if isinstance(request, dict) else None
        response["nonce"] = nonce if isinstance(nonce, str) and re.fullmatch("[a-f0-9]{48}", nonce) else ""
        response["mac"] = hmac.new(self.server.gate.key, canonical(response), hashlib.sha256).hexdigest()
        self.wfile.write(canonical(response) + b"\n")


class Server(socketserver.UnixStreamServer):
    def __init__(self, path, gate, allowed_uid):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent = self.path.parent.lstat()
        if self.path.parent.is_symlink() or parent.st_uid != os.geteuid() or parent.st_mode & 0o027:
            raise ValueError("Socket directory must be owned and not writable by clients")
        if self.path.exists() or self.path.is_symlink():
            raise ValueError("Deployment socket already exists; refusing replacement")
        self.gate, self.allowed_uid = gate, allowed_uid
        super().__init__(str(self.path), Handler)
        self.socket_identity = self.path.lstat().st_ino
        self.path.chmod(0o660)

    def server_close(self):
        super().server_close()
        if hasattr(self, "socket_identity") and self.path.exists() and self.path.lstat().st_ino == self.socket_identity:
            self.path.unlink()

    def handle_error(self, request, client_address):
        # Protocol errors must not log request bodies, signatures or credentials.
        pass


class Client:
    def __init__(self, path, key):
        self.path, self.key = str(path), key

    def execute(self, action, app, params=None):
        request = signed_request(self.key, action, app, params=params)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5 if action in ("status", "overview") else 600)
            connection.connect(self.path)
            connection.sendall(canonical(request) + b"\n")
            with connection.makefile("rb") as stream:
                raw = stream.readline(65537)
        if len(raw) > 65536:
            raise ValueError("Oversized deployment response")
        response = json.loads(raw)
        if not isinstance(response, dict) or not isinstance(response.get("mac"), str):
            raise ValueError("Unauthenticated deployment response")
        signature = response.pop("mac")
        expected = hmac.new(self.key, canonical(response), hashlib.sha256).hexdigest()
        if response.get("nonce") != request["nonce"] or not hmac.compare_digest(signature, expected):
            raise ValueError("Unauthenticated deployment response")
        if not response.get("ok"):
            if response.get("error") == "busy":
                raise DeploymentBusy("App has an active workload")
            raise ValueError("Deployment operation rejected")
        return response["result"]


def main():
    import argparse
    from .secrets import SecretStore
    from .pilot import Pilot
    from .pilot_engine import PilotEngine
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-state", required=True, type=Path)
    parser.add_argument("--service-state", required=True, type=Path)
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--allowed-uid", required=True, type=int)
    args = parser.parse_args()
    if args.allowed_uid < 0:
        parser.error("--allowed-uid must be a nonnegative local UID")
    args.service_state.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = args.service_state.lstat()
    if args.service_state.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        parser.error("Service state directory must be private and owned by this user")
    if (args.service_state / "audit.sqlite3").exists() and not (args.service_state / "secrets/deployment-channel-key").is_file():
        parser.error("Existing deployment service requires credential recovery")
    store = SecretStore(args.service_state / "secrets")
    key = store.get_or_create("deployment-channel-key").encode()
    gate = Gate(args.service_state / "audit.sqlite3", key, PilotEngine(Pilot(args.pilot_state)))
    with Server(args.socket, gate, args.allowed_uid) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
