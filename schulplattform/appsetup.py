"""Console-only first access per app (no default passwords, nothing over HTTP).

Uses the commands documented in each app's PLATFORM.md (catalogue.App.setup).
Values are read from the controlling terminal; passwords never appear as
arguments, in logs or in shell history.
"""
import getpass
import json
import os
import re

from .catalogue import APPS
from .state import StateError
from .terminal import open_tty

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
    with open_tty() as tty:
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


YOUTUBE_KEY = "tafel-youtube-key"


def _replace_projection(path, value):
    """Rotatable operator key (unlike first-access hashes): replace atomically, empty disables."""
    if path.is_symlink() or not path.exists():
        raise StateError("Projection missing; run apply first")
    temporary = path.with_name("." + path.name + ".new")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o444)
    os.replace(temporary, path)


def set_youtube_key(platform):
    """Store the YouTube Data API key for the grundschultafel video search; empty input switches it off."""
    if "grundschultafel" not in platform.stack.apps:
        raise StateError("grundschultafel is not installed")
    with open_tty() as tty:
        key = getpass.getpass("YouTube-API-Schlüssel (unsichtbar, leer = Videosuche aus): ", stream=tty).strip()
    if key and not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", key):
        raise StateError("Das sieht nicht nach einem YouTube-API-Schlüssel aus; nichts geändert")
    _replace_projection(platform.layout.runtime / YOUTUBE_KEY, key)
    platform.stack.render(platform.current_domains())
    platform.stack.compose("grundschultafel", "up", "-d", "--pull", "never", "--no-build", "--force-recreate",
                           "--wait", *APPS["grundschultafel"].services)
    return bool(key)


GALLERY_AI_KEY = "gallery-ai-key"


def set_gallery_ai_key(platform, source):
    """Service-account JSON for the gallery's optional AI metadata (Gemini/Vertex AI); None switches it off.

    The key is read from a file the operator copied to the server (it is multi-line JSON, not typed
    in), checked for shape, stored as a read-only projection and the source should be deleted."""
    if "bildergalerie" not in platform.stack.apps:
        raise StateError("bildergalerie is not installed")
    value = ""
    if source is not None:
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 16384:
            raise StateError(f"{source}: keine reguläre Datei (höchstens 16 KiB); nichts geändert")
        try:
            data = json.loads(source.read_text())
        except (ValueError, UnicodeDecodeError):
            raise StateError("Die Datei ist kein JSON; nichts geändert") from None
        if not isinstance(data, dict) or data.get("type") != "service_account" or not data.get("project_id") \
                or not data.get("private_key"):
            raise StateError("Das ist kein Google-Service-Account-Schlüssel; nichts geändert")
        value = json.dumps(data)
    _replace_projection(platform.layout.runtime / GALLERY_AI_KEY, value)
    platform.stack.render(platform.current_domains())
    platform.stack.compose("bildergalerie", "up", "-d", "--pull", "never", "--no-build", "--force-recreate",
                           "--wait", *APPS["bildergalerie"].services)
    return bool(value)


WISSEN_OIDC = "wissen-oidc"


def set_nextcloud_oidc(platform):
    """Client secret for schulwissen's Nextcloud login; empty input switches the login off.

    Issuer and client id come from platform.toml (apps.schulwissen.nextcloud_issuer /
    nextcloud_client_id); the secret is typed in invisibly and kept as a read-only projection."""
    if "schulwissen" not in platform.stack.apps:
        raise StateError("schulwissen is not installed")
    entry = platform.stack.config["apps"]["schulwissen"]
    if not (entry.get("nextcloud_issuer") and entry.get("nextcloud_client_id")):
        raise StateError("Zuerst nextcloud_issuer und nextcloud_client_id unter [apps.schulwissen] in "
                         "platform.toml eintragen; nichts geändert")
    with open_tty() as tty:
        secret = getpass.getpass("Client-Geheimnis aus Nextcloud (unsichtbar, leer = Nextcloud-Anmeldung aus): ",
                                 stream=tty).strip()
    if secret and not re.fullmatch(r"[\x21-\x7e]{8,500}", secret):
        raise StateError("Das sieht nicht nach einem Client-Geheimnis aus; nichts geändert")
    _replace_projection(platform.layout.runtime / WISSEN_OIDC, secret)
    platform.stack.render(platform.current_domains())
    platform.stack.compose("schulwissen", "up", "-d", "--pull", "never", "--no-build", "--force-recreate",
                           "--wait", *APPS["schulwissen"].services)
    return bool(secret)
