"""Console-only first access per app (no default passwords, nothing over HTTP).

Uses the commands documented in each app's PLATFORM.md (catalogue.App.setup).
Values are read from the controlling terminal; passwords never appear as
arguments, in logs or in shell history.
"""
import getpass
import os
import re

from .catalogue import APPS
from .state import StateError

PATTERNS = {"name": (r"[a-z][a-z0-9._-]{2,40}", "Persönlicher Benutzername"),
            "email": (r"[^@\s]{1,64}@[a-z0-9.-]{1,253}", "Persönliche E-Mail-Adresse"),
            "display": (r"[^\x00-\x1f<>\"]{2,80}", "Anzeigename")}


def _ask(tty, key):
    pattern, label = PATTERNS[key]
    for _ in range(3):
        tty.write(f"{label}: ")
        tty.flush()
        value = tty.readline().strip()
        if re.fullmatch(pattern, value):
            return value
        tty.write("  Ungültige Eingabe.\n")
    raise StateError("Abgebrochen")


def _write_projection(path, value):
    if path.is_symlink() or not path.exists():
        raise StateError("Projection missing; run apply first")
    if path.read_text():
        raise StateError(f"{path.name} ist bereits gesetzt; Änderung nur über eine ausdrückliche Rotation")
    temporary = path.with_name("." + path.name + ".new")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o444)
    os.replace(temporary, path)


def setup_app(platform, app_id):
    if app_id not in platform.stack.apps:
        raise StateError("App is not installed")
    kind, spec, *rest = APPS[app_id].setup
    with open("/dev/tty", "r+") as tty:
        if kind == "host-hash":
            from werkzeug.security import generate_password_hash
            hash_file, *name_file = spec
            username = _ask(tty, "name")
            password = getpass.getpass("Passwort (mindestens 12 Zeichen, unsichtbar): ", stream=tty)
            again = getpass.getpass("Passwort wiederholen: ", stream=tty)
            if len(password) < 12 or password != again:
                raise StateError("Passwort zu kurz oder Wiederholung abweichend; nichts geändert")
            runtime = platform.layout.runtime
            if name_file:
                _write_projection(runtime / name_file[0], username)
            _write_projection(runtime / hash_file, generate_password_hash(password))
            platform.stack.render(platform.current_domains())
            platform.stack.compose(app_id, "up", "-d", "--pull", "never", "--no-build", "--force-recreate",
                                   "--wait", *APPS[app_id].services)
            tty.write(f"{app_id}: persönlicher Zugang '{username}' eingerichtet.\n")
            return
        values = {key: _ask(tty, key) for key in PATTERNS if any("{" + key + "}" in part for part in spec)}
    argv = [part.format(**values) for part in spec]
    if kind == "run":
        platform.stack.compose(app_id, "run", "--rm", "--no-deps", "--pull", "never", "app", *argv,
                               tty=True, capture=False)
    elif kind == "exec":
        platform.stack.compose(app_id, "exec", "app", *argv, tty=True, capture=False)
    else:
        raise StateError("Unknown setup kind")
