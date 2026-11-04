"""Versioned host configuration (platform.toml): load, validate, write, wizard.

The file holds no secrets. SMTP and backup credentials live in the private
secret store and are entered only through the controlling terminal.
"""
import ipaddress
import json
import os
from pathlib import Path
import re
import tomllib

from jsonschema import Draft202012Validator, FormatChecker

from .catalogue import APP_IDS
from .proxy import hostname as check_hostname
from .storage import exclusive

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/platform-config-v1.schema.json"
DEFAULT_PATH = Path("/etc/schulplattform/platform.toml")
DEFAULT_NETWORK_BASE = "10.231.0.0/16"


class ConfigError(ValueError):
    pass


def validate(data):
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = ".".join(str(p) for p in first.absolute_path) or "(root)"
        raise ConfigError(f"platform.toml invalid at {where}: {first.message}")
    platform = data["platform"]
    seen = {platform["management_domain"]: "management_domain"}
    for app, entry in data["apps"].items():
        check_hostname(entry["hostname"])
        if entry["hostname"] in seen:
            raise ConfigError(f"Hostname {entry['hostname']} used twice ({seen[entry['hostname']]}, {app})")
        seen[entry["hostname"]] = app
    if not any(entry["enabled"] for entry in data["apps"].values()):
        raise ConfigError("At least one app must be enabled")
    ipv4 = ipaddress.IPv4Address(platform["public_ipv4"])
    if platform.get("public_ipv6"):
        ipaddress.IPv6Address(platform["public_ipv6"])
    for resolver in platform.get("resolvers", []):
        ipaddress.ip_address(resolver)
    if platform["acme_environment"] != "custom":
        if not ipv4.is_global:
            raise ConfigError("public_ipv4 must be a public address for Let's Encrypt")
        if platform.get("acme_ca") or platform.get("acme_ca_root") or platform.get("issued_root"):
            raise ConfigError("acme_ca/acme_ca_root/issued_root are only allowed with acme_environment = custom")
    base = ipaddress.ip_network(platform.get("network_base", DEFAULT_NETWORK_BASE))
    if base.prefixlen != 16:
        raise ConfigError("network_base must be a /16")
    return data


def load(path=DEFAULT_PATH):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise ConfigError(f"Configuration {path} missing; run './install.sh configure' first") from None
    if path.is_symlink() or not path.is_file():
        raise ConfigError("Configuration must be a regular file")
    if info.st_mode & 0o022:
        raise ConfigError("Configuration must not be group/world writable")
    with path.open("rb") as stream:
        try:
            data = tomllib.load(stream)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"platform.toml is not valid TOML: {exc}") from None
    return validate(data)


def enabled_apps(data):
    return tuple(app for app in APP_IDS if data["apps"].get(app, {}).get("enabled"))


def network_base(data):
    return ipaddress.ip_network(data["platform"].get("network_base", DEFAULT_NETWORK_BASE))


# --- writing -------------------------------------------------------------------

def _value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    raise TypeError("Unsupported TOML value")


def dumps(data):
    validate(data)
    lines = ["# Schulplattform host configuration. No secrets in this file.",
             "# Validate with: ./install.sh configure --check", "", f"schema = {data['schema']}", ""]
    for section in ("platform", "smtp", "backup"):
        lines.append(f"[{section}]")
        lines += [f"{key} = {_value(value)}" for key, value in data[section].items()]
        lines.append("")
    for app in APP_IDS:
        if app in data["apps"]:
            lines.append(f"[apps.{app}]")
            lines += [f"{key} = {_value(value)}" for key, value in data["apps"][app].items()]
            lines.append("")
    text = "\n".join(lines)
    if tomllib.loads(text) != data:
        raise ConfigError("Internal TOML serialisation mismatch")
    return text


def write(data, path=DEFAULT_PATH):
    path = Path(path)
    text = dumps(data)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    with exclusive(path.parent / ".platform.toml.lock"):
        temporary = path.with_name("." + path.name + ".new")
        fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            previous = path.with_name(path.name + ".previous")
            previous.write_bytes(path.read_bytes())
            os.chmod(previous, 0o644)
        os.replace(temporary, path)


# --- interactive wizard --------------------------------------------------------

SUGGESTED_PREFIX = {"gswb": "woerterbuch", "schulwissen": "wissen", "zackboing": "quiz",
                    "schulhelfer": "helfer", "losverkauf": "lose", "grundschultafel": "tafel",
                    "fahrradausbildung": "rad", "leseflux": "lesen", "kompetenz-manager": "kompetenz",
                    "abgen": "blaetter"}


def wizard(path=DEFAULT_PATH, existing=None, tty_path="/dev/tty"):
    """Ask on the controlling terminal; never reads arguments or environment for values."""
    existing = existing or {}
    with open(tty_path, "r+") as tty:
        def ask(prompt, default=None, pattern=None):
            while True:
                suffix = f" [{default}]" if default not in (None, "") else ""
                tty.write(f"{prompt}{suffix}: ")
                tty.flush()
                answer = tty.readline().strip() or (default or "")
                if not pattern or re.fullmatch(pattern, answer):
                    return answer
                tty.write("  Ungültige Eingabe.\n")

        old = existing.get("platform", {})
        tty.write("Schulplattform – Konfiguration. DNS-Einträge setzen Sie selbst beim Provider.\n\n")
        parent = ask("Gemeinsame Domain für Vorschläge (z. B. schule.example.de), leer = keine",
                     None, r"|[a-z0-9.-]+")
        management = ask("Verwaltungsdomain (Dashboard)", old.get("management_domain") or
                         (f"verwaltung.{parent}" if parent else None), r"[a-z0-9.-]+")
        data = {"schema": 1, "platform": {
            "management_domain": management,
            "acme_email": ask("Kontakt-E-Mail für Let's Encrypt", old.get("acme_email"), r"[^@\s]+@[a-z0-9.-]+"),
            "acme_environment": ask("ACME-Umgebung (staging/production)", old.get("acme_environment", "staging"),
                                    r"staging|production"),
            "public_ipv4": ask("Öffentliche IPv4-Adresse dieses Servers (vom Hoster)", old.get("public_ipv4"),
                               r"[0-9.]+"),
        }}
        ipv6 = ask("Öffentliche IPv6-Adresse (leer = keine)", old.get("public_ipv6", ""), r"|[0-9a-fA-F:]+")
        if ipv6:
            data["platform"]["public_ipv6"] = ipv6
        data["apps"] = {}
        for app in APP_IDS:
            previous = existing.get("apps", {}).get(app, {})
            enabled = ask(f"{app}: installieren? (j/n)", "j" if previous.get("enabled", True) else "n", r"[jn]") == "j"
            suggestion = previous.get("hostname") or (f"{SUGGESTED_PREFIX[app]}.{parent}" if parent else None)
            data["apps"][app] = {"enabled": enabled,
                                 "hostname": ask(f"{app}: Hostname", suggestion, r"[a-z0-9.-]+")}
        mode = ask("Mailversand (relay = über Ihren SMTP-Anbieter, none = keiner)",
                   existing.get("smtp", {}).get("mode", "relay"), r"relay|none")
        smtp = {"mode": mode}
        if mode == "relay":
            prior = existing.get("smtp", {})
            smtp.update(host=ask("SMTP-Server", prior.get("host"), r"[a-z0-9.-]+"),
                        port=int(ask("SMTP-Port", str(prior.get("port", 587)), r"[0-9]{1,5}")),
                        security=ask("Verschlüsselung (starttls/tls)", prior.get("security", "starttls"), r"starttls|tls"),
                        username=ask("SMTP-Benutzer (leer = ohne Anmeldung)", prior.get("username", ""), r"\S*"),
                        sender=ask("Absenderadresse", prior.get("sender"), r"[^@\s<>]+@[a-z0-9.-]+"),
                        sender_name=ask("Absendername", prior.get("sender_name", "Schulplattform"), r"[^<>\"]*"))
        data["smtp"] = smtp
        data["backup"] = {"schedule": ask("Uhrzeit der täglichen Sicherung (HH:MM)",
                                          existing.get("backup", {}).get("schedule", "02:30"), r"[0-2][0-9]:[0-5][0-9]"),
                          "retention_days": int(ask("Aufbewahrung in Tagen", str(existing.get("backup", {})
                                                    .get("retention_days", 14)), r"[0-9]{1,3}"))}
        offsite = ask("Externes Backup-Ziel (sftp://user@host/pfad oder Mount-Pfad, leer = später)",
                      existing.get("backup", {}).get("offsite", ""), r"|\S+")
        if offsite:
            data["backup"]["offsite"] = offsite
    write(data, path)
    return data
