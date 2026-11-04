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
                          "volumes": {"instance": "instance", "templates": "odt_templates"}},
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
                values[key.strip()] = value.strip().strip('"').strip("'")
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
                entry["unitActive"] = run(["systemctl", "is-active", spec.get("unit", f"{app}.service")]).stdout.strip()
                entry["data"] = {}
                for volume, root in roots.items():
                    item = {"path": str(root), "exists": root.is_dir(), "bytes": size(root) if root.is_dir() else 0}
                    item["sqlite"] = [sqlite_facts(p) for p in sorted(root.rglob("*"))
                                      if p.suffix in SQLITE_SUFFIXES and p.is_file()] if root.is_dir() else []
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
            for volume, root in roots.items():
                if not root.is_dir():
                    continue
                snap = work / "volumes" / volume
                sqlite_dir = work / "sqlite" / volume
                snap.mkdir(parents=True)
                sqlite_dir.mkdir(parents=True)
                skipped = []
                for db in sorted(p for p in root.rglob("*") if p.suffix in SQLITE_SUFFIXES and p.is_file()):
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
                    for item in sorted(root.rglob("*")):
                        relative = str(item.relative_to(root))
                        if relative in skipped or relative in extras or item.is_symlink():
                            continue
                        tar.add(item, arcname="./" + relative, recursive=False)
                    for target, source in sorted(extras.items()):
                        tar.add(source, arcname="./" + target, recursive=False)
                        info.setdefault("relocated", []).append({"from": str(source.relative_to(base)),
                                                                 "to": f"{volume}:{target}"})
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
