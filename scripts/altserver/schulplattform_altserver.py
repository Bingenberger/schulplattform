#!/usr/bin/env python3
"""Read-only inventory and consistent export of the existing (old) app installations.

Runs on the OLD server with the Python standard library only. It never writes
into an app directory, never changes a database and never stops a service.

  python3 schulplattform_altserver.py inventory [--app NAME=PATH ...] > inventory.json
  python3 schulplattform_altserver.py export APP --key-file transfer.key [--path PATH]
          [--compose-project NAME] --out /sicherer/pfad

inventory: version (git commit if the install is a checkout), storage engine,
schema revision, data paths and sizes and the NAMES of configured secrets.
No personal data and no secret values are printed.

export: one archive per app in the platform's import layout, encrypted with
gpg (AES256, passphrase = content of the transfer key file created on the new
server with './install.sh import-key'). SQLite files are copied with the online
.backup API; PostgreSQL is dumped with pg_dump -Fc from the running container.
Secrets that existing links depend on (e.g. the losverkauf parent token) are
included inside the encrypted archive so links keep working.

For a consistent snapshot announce a short write freeze; the export itself
does not stop anything.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time

# Native default paths from the apps' own deploy files at the audited commits.
APPS = {
    "gswb": {"kind": "native", "default": "/opt/gswb",
             "volumes": {"dictionary": "data", "images": "static/images", "audio": "static/audio",
                         "uploads": "static/uploads"}},
    "zackboing": {"kind": "native", "default": "/opt/zackboing", "data_env": ("ZACKBOING_DATA", "/var/lib/zackboing"),
                  "volumes": {"data": "@data"}, "unit": "zackboing.service"},
    "schulhelfer": {"kind": "native", "default": "/opt/schulfest", "volumes": {"data": "data"},
                    "unit": "schulfest-helfer.service", "envfile": ".env"},
    "losverkauf": {"kind": "native", "default": "/opt/losverkauf", "volumes": {"data": "data"},
                   "unit": "losverkauf.service", "envfile": "losverkauf.env",
                   "secrets": {"ELTERN_TOKEN": "losverkauf/parent-token", "SECRET_KEY": "losverkauf/session-key"},
                   # The old version reads the district map from the app directory; the new one from the data volume.
                   "extra": {"static/bezirke.geojson": ("data", "maps/bezirke.geojson")}},
    "grundschultafel": {"kind": "native", "default": "/opt/grundschultafel", "volumes": {"data": "data"}},
    "kompetenz-manager": {"kind": "native", "default": "/opt/kompetenz-manager",
                          "volumes": {"instance": "instance", "templates": "odt_templates"},
                          # Old installs may run on PostgreSQL (DATABASE_URL); the platform uses SQLite.
                          "database_url": True, "sqlite_target": ("instance", "schule.db")},
    "fundkiste": {"kind": "native", "default": "/opt/fundkiste", "volumes": {"data": "data"},
                  "unit": "fundkiste.service",
                  # The team key usually sits in the unit's Environment=; it moves into the data volume so
                  # printed QR codes keep working. data/team_key.txt (if present) travels with the files.
                  "unit_files": {"FUNDKISTE_TEAM_KEY": ("data", "team_key.txt")}},
    "schuleva": {"kind": "native", "default": "/opt/schulbefragung", "volumes": {"data": "data"},
                 "unit": "schulbefragung.service", "envfile": ".env",
                 "exclude": {"data": ("backups",)},          # daily cp copies from the old cron job
                 "extra_dirs": {"surveys": ("data", "surveys")}},
    "schulkasse": {"kind": "native", "default": "/opt/schulkasse", "volumes": {"data": "instance"},
                   "unit": "schulkasse.service", "envfile": ".env",
                   # The key encrypts the 2FA secrets: without it nobody can log in after the move.
                   "secrets": {"SCHULKASSE_SECRET_KEY": "schulkasse-key"},
                   "exclude": {"data": ("backups",)}},       # the app's own tar.gz backups stay behind
    "schulwissen": {"kind": "compose", "db": ("db", "schulwissen", "schulwissen"), "engine": "postgres16",
                    "volumes": {"medien": ("app", "/medien")}},
    "fahrradausbildung": {"kind": "compose", "db": ("db", "fahrrad", "fahrrad"), "engine": "postgres16",
                          "volumes": {"vorlagen": ("app", "/vorlagen")}},
    "leseflux": {"kind": "compose", "db": ("postgres", "leseflux", "leseflux"), "engine": "postgres16",
                 "volumes": {}},
    "abgen": {"kind": "compose", "db": ("postgres", "abgen", "abgen"), "engine": "postgres18",
              "volumes": {"assets": ("app", "/app/data/assets")}},
}
SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3")
SCHEMA_QUERIES = {
    "alembic": "SELECT version_num FROM alembic_version",
    "django": "SELECT app || '.' || name FROM django_migrations ORDER BY id DESC LIMIT 1",
    "drizzle": "SELECT hash FROM drizzle.__drizzle_migrations ORDER BY id DESC LIMIT 1",
    "prisma": "SELECT migration_name FROM _prisma_migrations ORDER BY finished_at DESC NULLS LAST LIMIT 1",
}


def run(argv, **kwargs):
    """Missing tools (no docker, git or systemctl on this host) count as a failed command."""
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=600, **kwargs)
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]}: not installed")


def git_commit(path):
    result = run(["git", "-C", str(path), "rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def env_names(path):
    names = []
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                names.append(line.split("=", 1)[0].strip())
    except OSError:
        pass
    return names


def env_values(path):
    values = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                key = key[len("export "):].strip() if key.startswith("export ") else key
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def sqlite_facts(path):
    """Read-only facts about a SQLite file: user_version, alembic revision, table row counts."""
    facts = {"file": str(path), "bytes": os.path.getsize(path)}
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        facts["userVersion"] = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                                   "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        facts["tables"] = {t: connection.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in tables}
        if "alembic_version" in tables:
            facts["alembic"] = [r[0] for r in connection.execute("SELECT version_num FROM alembic_version")]
        connection.close()
    except sqlite3.Error as exc:
        facts["error"] = type(exc).__name__
    return facts


def excluded(spec, volume, relative):
    """Paths below a volume that must not travel (e.g. the old cron job's database copies)."""
    for prefix in spec.get("exclude", {}).get(volume, ()):
        if relative == prefix or relative.startswith(prefix + "/"):
            return True
    return False


def resolve_native(app, override=None):
    spec = APPS[app]
    base = Path(override or spec["default"])
    roots = {}
    for volume, relative in spec["volumes"].items():
        if relative == "@data":
            variable, default = spec["data_env"]
            unit_env = unit_environment(spec.get("unit"))
            roots[volume] = Path(unit_env.get(variable, default))
        else:
            roots[volume] = base / relative
    return base, roots


def unit_environment(unit):
    if not unit:
        return {}
    result = run(["systemctl", "show", unit, "-p", "Environment", "--value"])
    values = {}
    for item in result.stdout.split():
        if "=" in item:
            key, value = item.split("=", 1)
            values[key] = value
    return values


def compose_container(project, service):
    if not shutil.which("docker"):
        raise SystemExit("docker is not installed on this host")
    argv = ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.service={service}"]
    if project:
        argv += ["--filter", f"label=com.docker.compose.project={project}"]
    ids = run(argv).stdout.split()
    if len(ids) != 1:
        raise SystemExit(f"Expected one running container for service '{service}'"
                         f"{' in project ' + project if project else ''}; found {len(ids)}. Use --compose-project.")
    return ids[0]


def postgres_facts(container, user, database):
    facts = {"database": database}
    tables = run(["docker", "exec", container, "psql", "-At", "-U", user, "-d", database, "-c",
                  "SELECT quote_ident(schemaname)||'.'||quote_ident(tablename) FROM pg_tables "
                  "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1"]).stdout.split()
    facts["tables"] = {}
    for table in tables:
        count = run(["docker", "exec", container, "psql", "-At", "-U", user, "-d", database, "-c",
                     f"SELECT count(*) FROM {table}"]).stdout.strip()
        facts["tables"][table.replace('"', "")] = int(count) if count.isdigit() else None
    for kind, query in SCHEMA_QUERIES.items():
        result = run(["docker", "exec", container, "psql", "-At", "-U", user, "-d", database, "-c", query])
        if result.returncode == 0 and result.stdout.strip():
            facts[kind] = result.stdout.strip().splitlines()[-1]
    facts["serverVersion"] = run(["docker", "exec", container, "psql", "-At", "-U", user, "-d", database, "-c",
                                  "SHOW server_version"]).stdout.strip()
    return facts


SYSTEM_DIRS = ("/", "/root", "/var/lib/systemd")


def running_services():
    """Running systemd services that work in an application directory: unit, user, working
    directory and program path only (no arguments, they may carry secrets). Helps locating
    installs outside the default paths."""
    listing = run(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend", "--plain"])
    services = []
    for line in listing.stdout.splitlines():
        unit = line.split()[0] if line.split() else ""
        if not unit.endswith(".service"):
            continue
        shown = run(["systemctl", "show", unit, "-p", "WorkingDirectory", "-p", "User", "-p", "ExecStart"]).stdout
        props = dict(item.split("=", 1) for item in shown.splitlines() if "=" in item)
        workdir = props.get("WorkingDirectory", "")
        if not workdir or workdir in SYSTEM_DIRS:
            continue
        program = ""
        if "path=" in props.get("ExecStart", ""):
            program = props["ExecStart"].split("path=", 1)[1].split(" ;", 1)[0].strip()
        services.append({"unit": unit, "user": props.get("User", ""), "workingDirectory": workdir,
                         "program": program, "commit": git_commit(workdir)})
    return services


def compose_projects():
    if not shutil.which("docker"):
        return []
    result = run(["docker", "ps", "--format", '{{.Label "com.docker.compose.project"}}\t'
                  '{{.Label "com.docker.compose.project.working_dir"}}\t{{.Label "com.docker.compose.service"}}'])
    projects = {}
    for line in result.stdout.splitlines():
        name, workdir, service = (line.split("\t") + ["", "", ""])[:3]
        if name:
            entry = projects.setdefault(name, {"project": name, "workingDirectory": workdir, "services": []})
            entry["services"].append(service)
    return sorted(projects.values(), key=lambda e: e["project"])


def unit_for(base, preferred=None):
    """The running systemd unit serving from this directory (old installs use their own unit names)."""
    for service in running_services():
        if service["workingDirectory"] == str(base):
            return service["unit"]
    return preferred


def unit_values(unit):
    """Environment of a unit: its EnvironmentFile(s) and Environment= lines. Values stay in memory."""
    values = {}
    if not unit:
        return values
    files = run(["systemctl", "show", unit, "-p", "EnvironmentFiles", "--value"]).stdout
    for item in files.split("\n"):
        path = item.strip().split(" ")[0].lstrip("-")
        if path:
            values.update(env_values(path))
    values.update(unit_environment(unit))
    return values


def database_url(base, unit):
    url = unit_values(unit).get("DATABASE_URL") or env_values(base / ".env.local").get("DATABASE_URL") or ""
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


def redacted_database(url):
    """Engine and database name only, never credentials."""
    if not url:
        return {"engine": "sqlite"}
    scheme, _, rest = url.partition("://")
    return {"engine": scheme.split("+")[0], "database": rest.rsplit("/", 1)[-1].split("?")[0]}


# Runs with the old app's own Python environment so the app's models define the target schema.
# Read-only on the source: one REPEATABLE READ READ ONLY transaction for a consistent snapshot.
CONVERT = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
from sqlalchemy import create_engine, func, inspect, select, text
from extensions import db
import models  # noqa: F401  registers all tables
mode, target = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else None)
source = create_engine(os.environ["KM_SOURCE_URL"])
meta = db.metadata
inspector = inspect(source)
names = set(inspector.get_table_names())
expected = set(meta.tables)
issues = {"extraTables": sorted(names - expected), "missingTables": sorted(expected - names), "columns": {}}
for table in meta.sorted_tables:
    if table.name in names:
        have = {c["name"] for c in inspector.get_columns(table.name)}
        want = {c.name for c in table.columns}
        if have != want:
            issues["columns"][table.name] = {"extra": sorted(have - want), "missing": sorted(want - have)}
compatible = not (issues["extraTables"] or issues["missingTables"] or issues["columns"])
result = {"compatible": compatible, "issues": issues, "counts": {}}
with source.connect() as src:
    src.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    for table in meta.sorted_tables:
        if table.name in names:
            result["counts"][table.name] = src.execute(select(func.count()).select_from(table)).scalar()
    if mode == "convert":
        if not compatible:
            print(json.dumps(result)); sys.exit(2)
        destination = create_engine("sqlite:///" + target)
        meta.create_all(destination)
        copied = {}
        with destination.begin() as dst:
            for table in meta.sorted_tables:
                rows, batch = 0, []
                for row in src.execute(select(table)).mappings():
                    batch.append(dict(row)); rows += 1
                    if len(batch) == 1000:
                        dst.execute(table.insert(), batch); batch = []
                if batch:
                    dst.execute(table.insert(), batch)
                copied[table.name] = rows
        result["copied"] = copied
        if copied != result["counts"]:
            print(json.dumps(result)); sys.exit(3)
print(json.dumps(result))
"""


def app_python(base, unit):
    program = ""
    for service in running_services():
        if service["unit"] == unit:
            program = service["program"]
    for candidate in ([Path(program).parent / "python"] if program else []) + [base / "venv/bin/python"]:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"No Python environment of the app found (looked next to {program or base})")


def convert_database(base, unit, url, mode, target=None):
    argv = [str(app_python(base, unit)), "-I", "-c", CONVERT, str(base), mode] + ([str(target)] if target else [])
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "KM_SOURCE_URL": url, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(argv, capture_output=True, text=True, timeout=7200, env=env, cwd="/")
    try:
        report = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        tail = result.stderr.strip().splitlines()[-1:] or ["no output"]
        raise SystemExit(f"Database check failed: {tail[0][:300]}")
    if result.returncode == 2:
        raise SystemExit("Source schema does not match the app's models; nothing exported: "
                         + json.dumps(report["issues"]))
    if result.returncode:
        raise SystemExit("Row counts differ after copying; nothing exported")
    return report


def inventory(overrides, projects):
    report = {"schemaVersion": 1, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "host": os.uname().nodename, "apps": {}}
    for app, spec in APPS.items():
        entry = {"kind": spec["kind"]}
        try:
            if spec["kind"] == "native":
                base, roots = resolve_native(app, overrides.get(app))
                entry["present"] = base.is_dir()
                if not entry["present"]:
                    report["apps"][app] = entry
                    continue
                entry["path"] = str(base)
                entry["commit"] = git_commit(base)
                unit = unit_for(base, spec.get("unit", f"{app}.service"))
                entry["unit"] = unit
                entry["unitActive"] = run(["systemctl", "is-active", unit]).stdout.strip()
                if spec.get("database_url"):
                    url = database_url(base, unit)
                    entry["database"] = redacted_database(url)
                    if url.startswith("postgresql"):
                        report_ = convert_database(base, unit, url, "check")
                        entry["database"].update(compatible=report_["compatible"], issues=report_["issues"],
                                                 tables=report_["counts"])
                entry["data"] = {}
                for volume, root in roots.items():
                    item = {"path": str(root), "exists": root.is_dir(), "bytes": size(root) if root.is_dir() else 0}
                    item["sqlite"] = [sqlite_facts(p) for p in sorted(root.rglob("*"))
                                      if p.suffix in SQLITE_SUFFIXES and p.is_file()
                                      and not excluded(spec, volume, str(p.relative_to(root)))] if root.is_dir() else []
                    entry["data"][volume] = item
                envfile = spec.get("envfile")
                entry["secretNames"] = env_names(base / envfile) if envfile else []
            else:
                service, user, database = spec["db"]
                container = compose_container(projects.get(app), service)
                entry["present"] = True
                labels = json.loads(run(["docker", "inspect", container, "--format", "{{json .Config.Labels}}"]).stdout)
                entry["composeProject"] = labels.get("com.docker.compose.project")
                entry["workingDir"] = labels.get("com.docker.compose.project.working_dir")
                if entry["workingDir"]:
                    entry["commit"] = git_commit(entry["workingDir"])
                    entry["secretNames"] = env_names(Path(entry["workingDir"]) / ".env")
                entry["postgres"] = postgres_facts(container, user, database)
                entry["data"] = {}
                for volume, (svc, mount) in spec["volumes"].items():
                    app_container = compose_container(entry["composeProject"], svc)
                    du = run(["docker", "exec", app_container, "du", "-sb", mount]).stdout.split()
                    entry["data"][volume] = {"mount": mount, "bytes": int(du[0]) if du else None}
        except SystemExit as exc:
            entry = {"kind": spec["kind"], "present": False, "note": str(exc)}
        except Exception as exc:  # one unreadable app must not cost the whole inventory
            entry.update(error=f"{type(exc).__name__}: {exc}")
        report["apps"][app] = entry
    report["runningServices"] = running_services()
    report["composeProjects"] = compose_projects()
    return report


def gpg_encrypt(source, destination, key_file):
    with open(source, "rb") as plain, open(destination, "wb") as out:
        result = subprocess.run(["gpg", "--batch", "--yes", "--quiet", "--symmetric", "--cipher-algo", "AES256",
                                 "--s2k-digest-algo", "SHA512", "--passphrase-file", str(key_file), "-o", "-"],
                                stdin=plain, stdout=out, stderr=subprocess.PIPE, timeout=7200)
    if result.returncode:
        raise SystemExit("gpg encryption failed")


def export(app, key_file, out_dir, path=None, project=None):
    spec = APPS[app]
    key_file = Path(key_file)
    if not key_file.is_file() or len(key_file.read_text().strip()) < 32:
        raise SystemExit("Transfer key file missing or too short (create it on the new server: ./install.sh import-key)")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    work = Path(tempfile.mkdtemp(prefix=f"export-{app}-"))
    os.chmod(work, 0o700)
    try:
        info = {"schemaVersion": 1, "app": app, "createdAt": stamp, "legacy": True, "volumes": [], "sqlite": [],
                "sourceHost": os.uname().nodename, "counts": {}}
        if spec["kind"] == "native":
            base, roots = resolve_native(app, path)
            info.update(engine="sqlite" if app != "grundschultafel" else "files", sourcePath=str(base),
                        sourceCommit=git_commit(base))
            converted = None
            if spec.get("database_url"):
                unit = unit_for(base, spec.get("unit", f"{app}.service"))
                url = database_url(base, unit)
                if url.startswith("postgresql"):
                    volume, name = spec["sqlite_target"]
                    converted = work / "sqlite" / volume / name
                    converted.parent.mkdir(parents=True)
                    report_ = convert_database(base, unit, url, "convert", converted)
                    info["sourceDatabase"] = redacted_database(url)
                    info["converted"] = {"from": "postgresql", "to": f"{volume}/{name}",
                                         "rows": sum(report_["copied"].values())}
            for volume, root in roots.items():
                if not root.is_dir():
                    continue
                snap = work / "volumes" / volume
                sqlite_dir = work / "sqlite" / volume
                snap.mkdir(parents=True)
                sqlite_dir.mkdir(parents=True, exist_ok=True)
                skipped = []
                if converted and converted.parent == sqlite_dir:
                    # The converted database replaces whatever stale SQLite files lie in the source directory.
                    name = converted.name
                    skipped += [p.name for p in root.iterdir() if p.name.startswith(name)]
                    copy = sqlite3.connect(converted)
                    integrity = copy.execute("PRAGMA integrity_check").fetchone()[0]
                    violations = len(copy.execute("PRAGMA foreign_key_check").fetchall())
                    copy.close()
                    facts = sqlite_facts(converted)
                    info["sqlite"].append({"volume": volume, "file": name, "integrity": integrity,
                                           "foreignKeyViolations": violations,
                                           "userVersion": facts.get("userVersion"), "alembic": None})
                    info["counts"][f"{volume}/{name}"] = facts.get("tables", {})
                for db in sorted(p for p in root.rglob("*") if p.suffix in SQLITE_SUFFIXES and p.is_file()
                                 and not excluded(spec, volume, str(p.relative_to(root)))
                                 and not (converted and converted.parent == sqlite_dir)):
                    relative = db.relative_to(root)
                    target = sqlite_dir / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
                    copy = sqlite3.connect(target)
                    source.backup(copy)
                    integrity = copy.execute("PRAGMA integrity_check").fetchone()[0]
                    copy.close()
                    source.close()
                    facts = sqlite_facts(target)
                    info["sqlite"].append({"volume": volume, "file": str(relative), "integrity": integrity,
                                           "foreignKeyViolations": 0, "userVersion": facts.get("userVersion"),
                                           "alembic": facts.get("alembic")})
                    info["counts"][f"{volume}/{relative}"] = facts.get("tables", {})
                    skipped += [str(relative), str(relative) + "-wal", str(relative) + "-shm",
                                str(relative) + "-journal"]
                with tarfile.open(snap / "files.tar", "w") as tar:
                    extras = {target: base / source for source, (vol, target) in spec.get("extra", {}).items()
                              if vol == volume and (base / source).is_file()}
                    unit_files = {}
                    if spec.get("unit_files"):
                        values = unit_values(unit_for(base, spec.get("unit")))
                        for variable, (vol, target) in spec["unit_files"].items():
                            if vol == volume and values.get(variable):
                                generated = work / "unit-files" / volume / target
                                generated.parent.mkdir(parents=True, exist_ok=True)
                                old = os.umask(0o077)
                                generated.write_text(values[variable])
                                os.umask(old)
                                unit_files[target] = generated
                                info.setdefault("fromUnit", []).append(f"{variable} -> {volume}:{target}")
                    for item in sorted(root.rglob("*")):
                        relative = str(item.relative_to(root))
                        if (relative in skipped or relative in extras or relative in unit_files
                                or item.is_symlink() or excluded(spec, volume, relative)):
                            continue
                        tar.add(item, arcname="./" + relative, recursive=False)
                    for source, (vol, target) in spec.get("extra_dirs", {}).items():
                        # Directories next to the app (e.g. edited questionnaires) move into the volume.
                        directory = base / source
                        if vol != volume or not directory.is_dir():
                            continue
                        for item in sorted(directory.rglob("*")):
                            if item.is_symlink():
                                continue
                            tar.add(item, arcname=f"./{target}/{item.relative_to(directory)}", recursive=False)
                        info.setdefault("relocated", []).append({"from": source, "to": f"{volume}:{target}"})
                    for target, source in sorted(extras.items()):
                        tar.add(source, arcname="./" + target, recursive=False)
                        info.setdefault("relocated", []).append({"from": str(source.relative_to(base)),
                                                                 "to": f"{volume}:{target}"})
                    for target, source in sorted(unit_files.items()):
                        # The unit's value wins over a file of the same name, as in the old app.
                        tar.add(source, arcname="./" + target, recursive=False)
                info["volumes"].append(volume)
            envfile = spec.get("envfile")
            values = env_values(base / envfile) if envfile else {}
            for variable, target in spec.get("secrets", {}).items():
                if values.get(variable):
                    destination = work / "secrets" / target
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(values[variable])
                    info.setdefault("secrets", []).append(target)
        else:
            service, user, database = spec["db"]
            container = compose_container(project, service)
            labels = json.loads(run(["docker", "inspect", container, "--format", "{{json .Config.Labels}}"]).stdout)
            project = labels.get("com.docker.compose.project")
            facts = postgres_facts(container, user, database)
            info.update(engine=spec["engine"], database=database, sourceRole=user,
                        sourceCommit=git_commit(labels.get("com.docker.compose.project.working_dir") or "."),
                        schema={k: v for k, v in facts.items() if k in SCHEMA_QUERIES},
                        sourceServerVersion=facts.get("serverVersion"))
            info["counts"]["postgres"] = facts["tables"]
            with open(work / "database.dump", "wb") as dump:
                result = subprocess.run(["docker", "exec", container, "pg_dump", "-Fc", "-U", user, "-d", database],
                                        stdout=dump, stderr=subprocess.PIPE, timeout=7200)
            if result.returncode:
                raise SystemExit("pg_dump failed")
            for volume, (svc, mount) in spec["volumes"].items():
                app_container = compose_container(project, svc)
                snap = work / "volumes" / volume
                snap.mkdir(parents=True)
                (work / "sqlite" / volume).mkdir(parents=True)
                with open(snap / "files.tar", "wb") as out:
                    result = subprocess.run(["docker", "exec", app_container, "tar", "-C", mount, "-cf", "-", "."],
                                            stdout=out, stderr=subprocess.PIPE, timeout=7200)
                if result.returncode:
                    raise SystemExit(f"Copying {mount} failed")
                info["volumes"].append(volume)
        (work / "backup.json").write_text(json.dumps(info, indent=2))
        plain = out_dir / f".{app}-{stamp}.tar"
        with tarfile.open(plain, "w") as tar:
            tar.add(work, arcname=".")
        archive = out_dir / f"{app}-{stamp}.altserver.tar.gpg"
        gpg_encrypt(plain, archive, key_file)
        plain.unlink()
        os.chmod(archive, 0o600)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        summary = {"app": app, "archive": str(archive), "sha256": digest, "volumes": info["volumes"],
                   "sqliteFiles": len(info["sqlite"]), "engine": info["engine"],
                   "tables": sum(len(v) for v in info["counts"].values())}
        print(json.dumps(summary, indent=2))
        return summary
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--app", action="append", default=[], help="NAME=PATH for native installs in other places")
    inv.add_argument("--compose-project", action="append", default=[], help="NAME=PROJECT for compose apps")
    exp = sub.add_parser("export")
    exp.add_argument("app", choices=sorted(APPS))
    exp.add_argument("--key-file", required=True)
    exp.add_argument("--out", required=True)
    exp.add_argument("--path")
    exp.add_argument("--compose-project")
    args = parser.parse_args()
    if args.command == "inventory":
        overrides = dict(item.split("=", 1) for item in args.app)
        projects = dict(item.split("=", 1) for item in args.compose_project)
        json.dump(inventory(overrides, projects), sys.stdout, indent=2)
        print()
    else:
        export(args.app, args.key_file, args.out, args.path, args.compose_project)


if __name__ == "__main__":
    main()
