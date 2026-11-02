"""Dashboard administrator authentication, separate from app identities."""
import base64
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import struct
import time
import uuid

from cryptography.fernet import Fernet
from werkzeug.security import check_password_hash, generate_password_hash

from .secrets import SecretStore


def otp(seed, counter, digits=6):
    if digits not in (6, 8) or type(counter) is not int or counter < 0:
        raise ValueError("Invalid TOTP parameters")
    key = base64.b32decode(seed, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return str(value % (10 ** digits)).zfill(digits)


def matching_counter(seed, code, now):
    if not isinstance(code, str) or not re.fullmatch("[0-9]{6}", code):
        return None
    current = int(now // 30)
    matches = [counter for counter in range(max(0, current - 1), current + 2)
               if hmac.compare_digest(otp(seed, counter), code)]
    return max(matches) if matches else None


SCHEMA = """
CREATE TABLE admins (
  id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, seed_cipher BLOB NOT NULL,
  last_counter INTEGER NOT NULL DEFAULT -1, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY, admin_id TEXT NOT NULL REFERENCES admins(id),
  expires INTEGER NOT NULL
);
CREATE TABLE attempts (
  username TEXT PRIMARY KEY, failures INTEGER NOT NULL,
  first_attempt INTEGER NOT NULL, locked_until INTEGER NOT NULL
);
CREATE TABLE access_projection (
  admin_id TEXT NOT NULL REFERENCES admins(id), app_id TEXT NOT NULL,
  PRIMARY KEY(admin_id, app_id)
);
CREATE TABLE audit (
  id INTEGER PRIMARY KEY, at INTEGER NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, app_id TEXT NOT NULL, outcome TEXT NOT NULL
);
PRAGMA user_version=1;
"""


class AdminStore:
    def __init__(self, directory, clock=time.time, initialize=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.directory.lstat()
        if self.directory.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("Dashboard directory must be private and owned by this user")
        if (self.directory / "dashboard.sqlite3").exists() and any(
                not (self.directory / "secrets" / name).is_file()
                for name in ("totp-wrapping-key", "dashboard-cookie-key")):
            raise ValueError("Existing dashboard requires secretstore recovery")
        if not initialize and not (self.directory / "dashboard.sqlite3").is_file():
            raise ValueError("Dashboard must be initialized through the local console")
        self.secrets = SecretStore(self.directory / "secrets")
        wrapping = self.secrets.get_or_create("totp-wrapping-key")
        self.cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(wrapping.encode()).digest()))
        self.cookie_key = self.secrets.get_or_create("dashboard-cookie-key")
        self.clock = clock
        self.path = self.directory / "dashboard.sqlite3"
        if self.path.is_symlink():
            raise ValueError("Dashboard DB symlink forbidden")
        if initialize and not self.path.exists():
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            # Schema is installed below in one explicit transaction.
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise ValueError("Dashboard DB must be initialized and private")
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if initialize and version == 0:
                existing = db.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]
                if existing:
                    raise ValueError("Unknown dashboard schema; explicit recovery required")
                db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
                version = 1
            if version != 1:
                raise ValueError("Dashboard schema migration required")
        # Same password work for unknown usernames; no permanent dummy credential.
        self.dummy_hash = generate_password_hash(secrets.token_urlsafe(32))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create_admin(self, username, password, seed):
        if (not isinstance(username, str) or not re.fullmatch("[a-zA-Z0-9_.@-]{3,80}", username)
                or not isinstance(password, str) or not 12 <= len(password) <= 256):
            raise ValueError("Invalid administrator identity or password")
        otp(seed, 1)
        identity = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO admins(id,username,password_hash,seed_cipher) VALUES(?,?,?,?)",
                       (identity, username.casefold(), generate_password_hash(password),
                        self.cipher.encrypt(seed.encode())))
        return identity

    def login(self, username, password, code):
        if (not isinstance(username, str) or not isinstance(password, str) or
                not 1 <= len(username) <= 80 or len(password) > 256):
            return None
        username = username.casefold()
        now = int(self.clock())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            admin = db.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
            attempt_key = username if admin else ":unknown"
            attempt = db.execute("SELECT * FROM attempts WHERE username=?", (attempt_key,)).fetchone()
            if attempt and attempt["locked_until"] > now:
                return None
            valid_password = check_password_hash(admin["password_hash"] if admin else self.dummy_hash, password)
            counter = None
            if admin and admin["active"] and valid_password:
                seed = self.cipher.decrypt(admin["seed_cipher"]).decode()
                counter = matching_counter(seed, code, now)
            if counter is None or counter <= admin["last_counter"]:
                count = (attempt["failures"] if attempt and now - attempt["first_attempt"] < 900 else 0) + 1
                first = attempt["first_attempt"] if attempt and now - attempt["first_attempt"] < 900 else now
                db.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?,?)",
                           (attempt_key, count, first, now + 900 if count >= 5 else 0))
                return None
            db.execute("UPDATE admins SET last_counter=? WHERE id=?", (counter, admin["id"]))
            db.execute("DELETE FROM attempts WHERE username=?", (username,))
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            token = secrets.token_urlsafe(48)
            db.execute("INSERT INTO sessions VALUES(?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), admin["id"], now + 3600))
            return token

    def authenticate(self, token):
        if not isinstance(token, str) or len(token) > 256:
            return None
        with self.connect() as db:
            row = db.execute("""SELECT a.id,a.username FROM sessions s JOIN admins a ON a.id=s.admin_id
                                WHERE s.token_hash=? AND s.expires>? AND a.active=1""",
                (hashlib.sha256(token.encode()).hexdigest(), int(self.clock()))).fetchone()
            return dict(row) if row else None

    def logout(self, token):
        if isinstance(token, str):
            with self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    def access(self, identity):
        with self.connect() as db:
            return {row[0] for row in db.execute("SELECT app_id FROM access_projection WHERE admin_id=?", (identity,))}

    def confirm_access(self, identity, app_id):
        if app_id not in ("gswb", "schulwissen", "zackboing"):
            raise ValueError("Unknown app")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO access_projection VALUES(?,?)", (identity, app_id))

    def audit(self, identity, action, app_id, outcome):
        if action not in ("start", "stop") or app_id not in ("gswb", "schulwissen", "zackboing") or outcome not in ("accepted", "failed", "completed", "blocked"):
            raise ValueError("Invalid audit event")
        with self.connect() as db:
            db.execute("INSERT INTO audit(at,actor,action,app_id,outcome) VALUES(?,?,?,?,?)",
                       (int(self.clock()), identity, action, app_id, outcome))
