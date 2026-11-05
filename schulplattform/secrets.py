"""Host-private secrets and single-use local bootstrap capabilities."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time

from .storage import atomic_json, exclusive


class SecretStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Secretstore must be a private directory owned by this user")

    def path(self, name):
        if not re.fullmatch("[a-z][a-z0-9-]{0,63}", name):
            raise ValueError("Invalid secret reference")
        return self.directory / name

    def get_or_create(self, name, generate=None):
        """Existing value, or a new one (default: 64 URL-safe characters; ``generate`` for formats
        an app requires, e.g. a Fernet key). An existing value is never replaced."""
        path = self.path(name)
        with exclusive(self.directory / ".store.lock"):
            if not path.exists() and not path.is_symlink():
                temporary = self.directory / ("." + secrets.token_hex(16))
                fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(fd, "w") as stream:
                        stream.write(generate() if generate else secrets.token_urlsafe(48))
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.link(temporary, path)  # never replace an existing credential
                    directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                finally:
                    temporary.unlink(missing_ok=True)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError("Secret file must be private, regular and owned by this user")
            value = path.read_text()
            if len(value) < 32:
                raise ValueError("Invalid existing secret; refusing automatic replacement")
            return value


    def replace(self, name, value):
        """Store an operator-provided credential (e.g. SMTP password); never generated, never logged."""
        if not isinstance(value, str) or not value or len(value) > 4096 or "\n" in value:
            raise ValueError("Invalid credential value")
        path = self.path(name)
        with exclusive(self.directory / ".store.lock"):
            temporary = self.directory / ("." + secrets.token_hex(16))
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(value)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)


class Bootstrap:
    def __init__(self, directory, clock=time.time):
        self.directory = Path(directory)
        self.clock = clock

    def issue(self, ttl=900):
        if not 1 <= ttl <= 900:
            raise ValueError("Bootstrap TTL must be between 1 and 900 seconds")
        with exclusive(self.directory / "bootstrap.lock"):
            path = self.directory / "bootstrap.json"
            if path.exists() or path.is_symlink():
                raise ValueError("Bootstrap already issued; explicit local recovery required")
            token = secrets.token_urlsafe(32)
            atomic_json(path, dict(sha256=hashlib.sha256(token.encode()).hexdigest(),
                                   expires=self.clock() + ttl, used=False))
            return token  # caller must deliver to controlling TTY, never logs or HTTP HTML

    def consume(self, token):
        if not isinstance(token, str) or len(token) > 256:
            return False
        with exclusive(self.directory / "bootstrap.lock"):
            path = self.directory / "bootstrap.json"
            if path.is_symlink():
                return False
            try:
                record = json.loads(path.read_text())
                if record["used"] is not False or record["expires"] <= self.clock():
                    return False
                if not hmac.compare_digest(record["sha256"], hashlib.sha256(token.encode()).hexdigest()):
                    return False
            except (OSError, ValueError, KeyError, TypeError):
                return False
            record["used"] = True
            atomic_json(path, record)
            return True
