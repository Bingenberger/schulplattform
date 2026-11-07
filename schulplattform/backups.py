"""Generic per-app backups by storage type, encrypted, rotated and copied off-site.

Storage types come from the release manifest:
  PostgreSQL  pg_dump -Fc of the app database plus pg_dumpall --globals-only (roles)
  SQLite      the online .backup API inside a network-less helper container
  Directories tar snapshot of every declared named volume (SQLite files replaced by
              their consistent .backup copies; live -wal/-shm files are skipped)

Archive format (.spbk): magic, JSON header, then AES-256-GCM chunks over a tar
stream. The key lives in the secret store ("backup-key") and must additionally
be kept off the server by the operator; without it a backup is worthless.
Restores and the restore probe use the same format, as does the import of data
exported from the old server.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import subprocess
import tarfile
import tempfile
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .catalogue import APPS
from .secrets import SecretStore
from .state import StateError
from .storage import atomic_json, exclusive

MAGIC = b"SPBK1\n"
CHUNK = 4 * 1024 * 1024
HELPER = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
APP_UID = "10001:10001"
SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3")
DATABASE_SERVICE = {"schulwissen": "db", "fahrradausbildung": "db", "leseflux": "postgres", "abgen": "postgres"}

SQLITE_SCRIPT = r"""
import os, sqlite3, sys, json
src, dst = sys.argv[1], sys.argv[2]
done = []
for root, dirs, files in os.walk(src):
    for name in files:
        if name.endswith((".db", ".sqlite", ".sqlite3")):
            path = os.path.join(root, name)
            with open(path, "rb") as probe:
                # Encrypted databases (SQLCipher, sl-journal) are no readable SQLite: the file snapshot
                # of the paused app takes them as they are.
                if probe.read(16) != b"SQLite format 3\x00":
                    continue
            rel = os.path.relpath(path, src)
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            source = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
            target = sqlite3.connect(out)
            source.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()[0]
            fk = target.execute("PRAGMA foreign_key_check").fetchall()
            target.close(); source.close()
            done.append({"file": rel, "integrity": check, "foreignKeyViolations": len(fk)})
print(json.dumps(done))
"""


def encrypt_stream(source, destination, key, header):
    aes = AESGCM(key)
    head = json.dumps(header, sort_keys=True).encode()
    destination.write(MAGIC + struct.pack(">I", len(head)) + head)
    prefix = secrets.token_bytes(4)
    index = 0
    digest = hashlib.sha256()
    chunk = source.read(CHUNK)
    while True:
        following = source.read(CHUNK)
        final = not following
        nonce = prefix + struct.pack(">Q", index)
        aad = head + struct.pack(">QB", index, 1 if final else 0)
        sealed = aes.encrypt(nonce, chunk, aad)
        destination.write(nonce + struct.pack(">IB", len(sealed), 1 if final else 0) + sealed)
        digest.update(chunk)
        index += 1
        if final:
            return digest.hexdigest()
        chunk = following


def decrypt_stream(source, destination, key):
    aes = AESGCM(key)
    if source.read(len(MAGIC)) != MAGIC:
        raise StateError("Not a platform backup archive")
    (length,) = struct.unpack(">I", source.read(4))
    if length > 65536:
        raise StateError("Invalid archive header")
    head = source.read(length)
    header = json.loads(head)
    index = 0
    while True:
        frame = source.read(17)
        if len(frame) != 17:
            raise StateError("Archive truncated")
        nonce, size, final = frame[:12], *struct.unpack(">IB", frame[12:])
        if struct.unpack(">Q", nonce[4:])[0] != index or size > CHUNK + 16:
            raise StateError("Archive chunk order violated")
        sealed = source.read(size)
        try:
            destination.write(aes.decrypt(nonce, sealed, head + struct.pack(">QB", index, final)))
        except Exception:
            raise StateError("Archive authentication failed (wrong key or modified file)") from None
        index += 1
        if final:
            if source.read(1):
                raise StateError("Trailing data after final chunk")
            return header


class BackupService:
    def __init__(self, platform):
        self.platform = platform
        self.stack = platform.stack
        self.layout = platform.layout
        self.status_path = self.layout.backups / "status.json"

    def key(self):
        value = SecretStore(self.layout.secrets).get_or_create("backup-key")
        return hashlib.sha256(value.encode()).digest()

    def volumes(self, app_id):
        manifest = self.platform.release.manifests[app_id]
        declared = [v for v in self.stack.compose(app_id, "config", "--volumes").split() if v]
        engine = manifest["database"]["engine"]
        postgres_mounts = {"/var/lib/postgresql/data", "/var/lib/postgresql"}
        skip = {p["id"].replace("-", "_") for p in manifest["persistence"] if p["mount"] in postgres_mounts} | \
               {p["id"] for p in manifest["persistence"] if p["mount"] in postgres_mounts}
        return [v for v in declared if v not in skip] if engine.startswith("postgres") else declared

    def _record(self, app_id, **values):
        with exclusive(self.layout.backups / "status.lock"):
            status = json.loads(self.status_path.read_text()) if self.status_path.exists() else {}
            status[app_id] = status.get(app_id, {}) | values
            atomic_json(self.status_path, status)

    def _await_health(self, app_id, seconds=150):
        """Health checks may fail while an app is paused for the file snapshot; Docker reports it
        unhealthy until the next check passes (real server: an import right after a backup was refused).
        Waits until the app answers healthy again, so the next operation sees its real state."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.stack.healthy(app_id):
                return True
            time.sleep(3)
        return False

    def backup(self, app_id):
        if app_id not in self.stack.apps:
            raise StateError("App is not installed")
        manifest = self.platform.release.manifests[app_id]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_dir = self.layout.backups / app_id
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        work = Path(tempfile.mkdtemp(prefix=f".{app_id}-", dir=self.layout.backups))
        try:
            os.chmod(work, 0o700)
            healthy = self.stack.healthy(app_id)
            info = {"schemaVersion": 1, "app": app_id, "release": self.platform.release.version, "healthy": healthy,
                    "sourceCommit": manifest["sourceCommit"], "createdAt": stamp,
                    "engine": manifest["database"]["engine"], "database": manifest["database"]["name"],
                    "volumes": [], "sqlite": []}
            if info["engine"].startswith("postgres"):
                service = DATABASE_SERVICE[app_id]
                # pg_dump needs a running database, even if the app itself is stopped.
                self.stack.compose(app_id, "up", "-d", "--pull", "never", "--no-build", "--wait",
                                   "--wait-timeout", "120", service)
                dump = self.stack.compose(app_id, "exec", "-T", service, "pg_dump", "-Fc", "-U", "postgres",
                                          "-d", info["database"], capture=True, binary=True)
                (work / "database.dump").write_bytes(dump)
                roles = self.stack.compose(app_id, "exec", "-T", service, "pg_dumpall", "--globals-only",
                                           "-U", "postgres", "--no-role-passwords", capture=True, binary=True)
                (work / "globals.sql").write_bytes(roles)
            for volume in self.volumes(app_id):
                name = f"sp-{app_id}_{volume}"
                snap = work / "volumes" / volume
                snap.mkdir(parents=True)
                sqlite_out = work / "sqlite" / volume
                sqlite_out.mkdir(parents=True)
                for path in (snap, sqlite_out):
                    os.chown(path, 10001, 10001) if os.geteuid() == 0 else None
                # Consistent SQLite copies first, then the remaining files.
                result = self.stack.command([self.stack.docker, "run", "--rm", "--network", "none", "--read-only",
                                             "--user", APP_UID, "--cap-drop", "ALL",
                                             "--security-opt", "no-new-privileges:true",
                                             "-v", f"{name}:/src", "-v", f"{sqlite_out}:/out",
                                             HELPER, "python", "-c", SQLITE_SCRIPT, "/src", "/out"])
                checks = json.loads(result or "[]")
                for check in checks:
                    if check["integrity"] != "ok":
                        raise StateError(f"{app_id}: SQLite integrity check failed")
                info["sqlite"] += [dict(check, volume=volume) for check in checks]
                # Freeze the app's processes only for the file snapshot (seconds), so files cannot change
                # or vanish while tar reads them. SQLite was copied above via the online API.
                running = [svc for svc in APPS[app_id].services if self.stack.service_state(app_id, svc)["running"]]
                if running:
                    self.stack.compose(app_id, "pause", *running)
                try:
                    self.stack.command([self.stack.docker, "run", "--rm", "--network", "none", "--read-only",
                                        "--user", APP_UID, "--cap-drop", "ALL", "--security-opt",
                                        "no-new-privileges:true", "-v", f"{name}:/src:ro", "-v", f"{snap}:/out",
                                        HELPER, "tar", "-C", "/src",
                                        # Only the files copied through the SQLite API above (and their
                                        # journals) are left out; every other file stays in the snapshot.
                                        *[f"--exclude=./{c['file']}{suffix}" for c in checks
                                          for suffix in ("", "-wal", "-shm", "-journal")],
                                        "-cf", "/out/files.tar", "."])
                finally:
                    if running:
                        self.stack.compose(app_id, "unpause", *running, check=False)
                        if healthy:
                            self._await_health(app_id)
                info["volumes"].append(volume)
            (work / "backup.json").write_text(json.dumps(info, indent=2))
            archive = target_dir / f"{app_id}-{stamp}.spbk"
            temporary = archive.with_suffix(".partial")
            with temporary.open("wb") as out:
                reader = _tar_reader(work)
                plain_digest = encrypt_stream(reader, out, self.key(),
                                              {"app": app_id, "createdAt": stamp, "release": info["release"]})
            os.chmod(temporary, 0o600)
            os.replace(temporary, archive)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        size = archive.stat().st_size
        offsite = self.offsite(archive)
        self.rotate(app_id)
        values = dict(lastSuccess=stamp, lastArchive=archive.name, size=size, plainSha256=plain_digest,
                      offsite=offsite, healthyAtBackup=healthy)
        if healthy:
            values["lastHealthyArchive"] = archive.name
        self._record(app_id, **values)
        return {"app": app_id, "archive": archive.name, "size": size, "offsite": offsite, "healthy": healthy}

    PLATFORM_PATHS = ("secrets", "runtime", "domains/current.json", "state/release-trust.pub", "state/bootstrap.json")

    def backup_platform(self):
        """Configuration, secret store, projections, domain state, certificates and dashboard admin state.

        Needed to rebuild a server: without the secrets, carried links (parent tokens) and app session
        keys would change. Encrypted with the same backup key; keep that key off the server.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_dir = self.layout.backups / "_platform"
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        work = Path(tempfile.mkdtemp(prefix=".platform-", dir=self.layout.backups))
        try:
            root = self.layout.root
            with tarfile.open(work / "platform.tar", "w") as tar:
                tar.add(self.platform.config_path, arcname="etc/platform.toml")
                for relative in self.PLATFORM_PATHS:
                    if (root / relative).exists():
                        tar.add(root / relative, arcname="var/" + relative)
                tar.add(self.layout.caddy_data, arcname="var/caddy/data")
            dashboard = self.stack.command([self.stack.docker, "volume", "inspect", "--format", "{{.Mountpoint}}",
                                            "sp-infra_dashboard-state"], check=False).strip()
            if dashboard:
                with tarfile.open(work / "dashboard.tar", "w") as tar:
                    tar.add(dashboard, arcname=".")
            (work / "backup.json").write_text(json.dumps({"schemaVersion": 1, "app": "_platform", "createdAt": stamp,
                                                         "release": self.platform.release.version}))
            archive = target_dir / f"_platform-{stamp}.spbk"
            with archive.with_suffix(".partial").open("wb") as out:
                encrypt_stream(_tar_reader(work), out, self.key(), {"app": "_platform", "createdAt": stamp})
            os.chmod(archive.with_suffix(".partial"), 0o600)
            os.replace(archive.with_suffix(".partial"), archive)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        offsite = self.offsite(archive)
        self._record("_platform", lastSuccess=stamp, lastArchive=archive.name, size=archive.stat().st_size,
                     offsite=offsite)
        return {"app": "_platform", "archive": archive.name, "offsite": offsite}

    def rotate(self, app_id):
        days = self.platform.config["backup"].get("retention_days", 14)
        limit = datetime.now(timezone.utc) - timedelta(days=days)
        archives = sorted((self.layout.backups / app_id).glob(f"{app_id}-*.spbk"))
        for archive in archives[:-1]:  # always keep the newest
            stamp = archive.stem.split("-", 1)[1] if app_id.count("-") == 0 else archive.stem[len(app_id) + 1:]
            created = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            if created < limit:
                archive.unlink()

    def offsite(self, archive):
        target = self.platform.config["backup"].get("offsite")
        if not target:
            return {"status": "nicht konfiguriert"}
        try:
            if target.startswith("/"):
                destination = Path(target) / archive.parent.name
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(archive, destination / (archive.name + ".partial"))
                os.replace(destination / (archive.name + ".partial"), destination / archive.name)
            else:
                key = SecretStore(self.layout.secrets).path("backup-ssh-key")
                if not key.exists():
                    return {"status": "fehler", "detail": "SSH-Schlüssel für das Backup-Ziel fehlt"}
                url = target[len("sftp://"):]
                login, path = url.split("/", 1)
                port = "22"
                if ":" in login:
                    login, port = login.rsplit(":", 1)
                subprocess.run(["scp", "-q", "-P", port, "-i", str(key), "-o", "BatchMode=yes",
                                "-o", "StrictHostKeyChecking=yes", str(archive), f"{login}:/{path}/"],
                               check=True, capture_output=True, timeout=3600)
            return {"status": "ok", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        except (OSError, subprocess.SubprocessError):
            return {"status": "fehler", "detail": "Übertragung zum Backup-Ziel fehlgeschlagen"}

    def latest(self, app_id):
        archives = sorted((self.layout.backups / app_id).glob(f"{app_id}-*.spbk"))
        if not archives:
            raise StateError("No backup archive")
        return archives[-1]

    def unpack(self, archive, destination, key=None):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryFile(dir=destination) as plain:
            with open(archive, "rb") as source:
                header = decrypt_stream(source, plain, key or self.key())
            plain.seek(0)
            with tarfile.open(fileobj=plain, mode="r:") as tar:
                tar.extractall(destination, filter="data")
        return header

    def restore_probe(self, app_id):
        """Decrypt the newest archive and check it in isolation; never touches live data."""
        archive = self.latest(app_id)
        work = Path(tempfile.mkdtemp(prefix=f".probe-{app_id}-", dir=self.layout.backups))
        try:
            self.unpack(archive, work)
            info = json.loads((work / "backup.json").read_text())
            result = {"archive": archive.name, "app": app_id}
            if info["engine"].startswith("postgres"):
                result["postgres"] = self._probe_postgres(app_id, info, work)
            for check in info["sqlite"]:
                if check["integrity"] != "ok":
                    raise StateError("SQLite copy failed integrity check")
            result["sqliteFiles"] = len(info["sqlite"])
            result["volumes"] = info["volumes"]
            result["status"] = "ok"
        except Exception as exc:
            result = {"archive": archive.name, "app": app_id, "status": "fehler", "detail": type(exc).__name__}
        finally:
            shutil.rmtree(work, ignore_errors=True)
        self._record(app_id, lastRestoreProbe=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     restoreProbe=result["status"])
        return result

    def _probe_postgres(self, app_id, info, work):
        from .catalogue import INFRASTRUCTURE
        image = INFRASTRUCTURE[info["engine"]]
        name = f"sp-probe-{app_id}-{secrets.token_hex(4)}"
        password = secrets.token_hex(16)
        os.chmod(work, 0o755)
        for item in work.iterdir():
            os.chmod(item, 0o644) if item.is_file() else None
        self.stack.command([self.stack.docker, "run", "-d", "--rm", "--name", name, "--network", "none",
                            "-e", f"POSTGRES_PASSWORD={password}", "-v", f"{work}:/backup:ro", image])
        try:
            for _ in range(60):
                if not self.stack.command([self.stack.docker, "exec", name, "pg_isready", "-U", "postgres"],
                                          check=False).strip().endswith("accepting connections"):
                    import time
                    time.sleep(1)
                else:
                    break
            self.stack.command([self.stack.docker, "exec", name, "psql", "-q", "-U", "postgres", "-f",
                                "/backup/globals.sql"], check=False)
            self.stack.command([self.stack.docker, "exec", name, "createdb", "-U", "postgres", info["database"]])
            self.stack.command([self.stack.docker, "exec", name, "pg_restore", "-U", "postgres", "-d",
                                info["database"], "--exit-on-error", "/backup/database.dump"])
            query = ("SELECT (SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')),"
                     " (SELECT count(*) FROM pg_constraint WHERE contype='f'),"
                     " (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())")
            row = self.stack.command([self.stack.docker, "exec", name, "psql", "-At", "-U", "postgres", "-d",
                                      info["database"], "-c", query]).strip().split("|")
            if int(row[0]) == 0:
                raise StateError("Restored database has no tables")
            return {"tables": int(row[0]), "foreignKeys": int(row[1]), "owner": row[2]}
        finally:
            self.stack.command([self.stack.docker, "rm", "-f", name], check=False)


def resolve_archive(service, app_id, archive):
    """'backup' prints only the file name; accept it and look in the app's backup folder."""
    archive = Path(archive)
    if archive.is_file():
        return archive
    candidate = service.layout.backups / app_id / archive.name
    if archive.name == str(archive) and candidate.is_file():
        return candidate
    raise StateError(f"Sicherung {archive} nicht gefunden (gesucht auch in {service.layout.backups / app_id})")


def restore(service, app_id, archive, key=None, confirm=False):
    """Replace one app's data with a platform backup archive (.spbk). See restore_directory()."""
    if not confirm:
        raise StateError("Restore replaces this app's data; confirmation required")
    archive = resolve_archive(service, app_id, archive)
    work = Path(tempfile.mkdtemp(prefix=f".restore-{app_id}-", dir=service.layout.backups))
    try:
        header = service.unpack(archive, work, key)
        if header.get("app") != app_id:
            raise StateError("Archive belongs to a different app")
        facts = restore_directory(service, app_id, work)
        facts["archive"] = Path(archive).name
        return facts
    finally:
        shutil.rmtree(work, ignore_errors=True)


def restore_directory(service, app_id, work, legacy=False):
    """Replace one app's data with an unpacked archive directory (platform backup or old-server export).

    Destructive for that app's volumes; callers must have obtained confirmation. Order:
    stop app -> remove its containers (never other apps) -> remove and recreate its named
    volumes -> files and SQLite copies into the empty volumes as UID 10001 -> PostgreSQL
    via the app's init script, then pg_restore (legacy: objects owned by the app role,
    because old installs used the app user as superuser) -> carried-over secrets ->
    explicit migration job -> start -> health.
    """
    platform = service.platform
    stack = service.stack
    if app_id not in stack.apps:
        raise StateError("App is not installed")
    work = Path(work)
    info = json.loads((work / "backup.json").read_text())
    if info["app"] != app_id:
        raise StateError("Archive belongs to a different app")
    manifest = platform.release.manifests[app_id]
    expected = manifest["database"]["engine"]
    if info["engine"] != expected and not (legacy and info["engine"] in ("sqlite", "files")
                                           and expected in ("sqlite", "files")):
        raise StateError(f"Archive storage engine {info['engine']} differs from the installed release ({expected})")
    volumes = [v for v in stack.compose(app_id, "config", "--volumes").split() if v]
    for volume in info.get("volumes", []):
        if volume not in volumes:
            raise StateError(f"Archive volume {volume} unknown to this release")
    stack.compose(app_id, "stop", "--timeout", "130")
    stack.compose(app_id, "rm", "-f", "-s")
    for volume in volumes:
        stack.command([stack.docker, "volume", "rm", f"sp-{app_id}_{volume}"], check=False)
        stack.command([stack.docker, "volume", "create", "--label", f"com.docker.compose.project=sp-{app_id}",
                       "--label", f"com.docker.compose.volume={volume}", f"sp-{app_id}_{volume}"])
    os.chmod(work, 0o755)
    for path in work.rglob("*"):
        if path.is_symlink():
            raise StateError("Symlink in archive refused")
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    facts = {"app": app_id, "sourceRelease": info.get("release"), "legacy": legacy,
             "createdAt": info.get("createdAt"), "volumes": [], "sqlite": len(info.get("sqlite", []))}
    owners = {item["id"].replace("-", "_"): item["owner"] for item in manifest["persistence"]}
    owners.update({item["id"]: item["owner"] for item in manifest["persistence"]})
    for volume in info.get("volumes", []):
        name = f"sp-{app_id}_{volume}"
        # A volume created outside Compose is root-owned; give it the owner declared in the manifest
        # (Compose would otherwise copy it from the image on first use). Only CAP_CHOWN is granted.
        stack.command([stack.docker, "run", "--rm", "--network", "none", "--read-only", "--user", "0:0",
                       "--cap-drop", "ALL", "--cap-add", "CHOWN", "--security-opt", "no-new-privileges:true",
                       "-v", f"{name}:/dst", HELPER, "chown", owners.get(volume, APP_UID), "/dst"])
        sqlite_dir = work / "sqlite" / volume
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        stack.command([stack.docker, "run", "--rm", "--network", "none", "--read-only", "--user", APP_UID,
                       "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                       "-v", f"{name}:/dst", "-v", f"{work}/volumes/{volume}:/in:ro",
                       "-v", f"{sqlite_dir}:/sqlite:ro", HELPER, "sh", "-c",
                       "tar -C /dst --no-same-owner --no-same-permissions -xf /in/files.tar && "
                       "cd /sqlite && find . -type f -exec sh -c 'mkdir -p \"/dst/$(dirname \"$1\")\" && "
                       "cp \"$1\" \"/dst/$1\" && chmod 600 \"/dst/$1\"' _ {} \\;"])
        facts["volumes"].append(volume)
    if info["engine"].startswith("postgres"):
        db_service = DATABASE_SERVICE[app_id]
        stack.compose(app_id, "up", "-d", "--pull", "never", "--no-build", "--wait", "--wait-timeout", "120",
                      db_service)
        container = stack.container(app_id, db_service)
        role = manifest["database"]["account"]
        stack.command([stack.docker, "cp", str(work / "database.dump"), f"{container['Id']}:/tmp/restore.dump"])
        options = ["--no-owner", f"--role={role}"] if legacy else []
        stack.command([stack.docker, "exec", container["Id"], "pg_restore", "-U", "postgres", "-d",
                       info["database"], "--clean", "--if-exists", "--exit-on-error", *options, "/tmp/restore.dump"])
        stack.command([stack.docker, "exec", container["Id"], "rm", "-f", "/tmp/restore.dump"])
        facts["postgres"] = postgres_counts(stack, container["Id"], info["database"])
    carried = []
    for relative in info.get("secrets", []):
        source = work / "secrets" / relative
        target = service.layout.runtime / relative
        if not source.is_file() or target.is_symlink() or ".." in Path(relative).parts:
            raise StateError("Invalid carried secret")
        value = source.read_text().strip()
        if len(value) < 32:
            raise StateError(f"Carried secret {relative} shorter than 32 characters; replace it and re-issue links")
        temporary = target.with_name("." + target.name + ".import")
        temporary.write_text(value)
        os.chmod(temporary, 0o444)
        os.replace(temporary, target)
        # Keep the secret store authoritative: the projection is re-derived from it on every render.
        kind = dict(APPS[app_id].secrets).get(relative, "")
        if kind.startswith(("random:", "fernet:")):
            from .secrets import SecretStore
            SecretStore(service.layout.secrets).replace(kind.split(":", 1)[1], value)
        carried.append(relative)
    facts["carriedSecrets"] = carried
    stack.migrate(app_id)
    stack.start(app_id)
    if not stack.healthy(app_id):
        raise StateError("App not healthy after restore")
    facts["healthy"] = True
    return facts


def postgres_counts(stack, container_id, database):
    tables = stack.command([stack.docker, "exec", container_id, "psql", "-At", "-U", "postgres", "-d", database,
                            "-c", "SELECT quote_ident(schemaname)||'.'||quote_ident(tablename) FROM pg_tables "
                                  "WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1"]).split()
    counts = {}
    for table in tables:
        value = stack.command([stack.docker, "exec", container_id, "psql", "-At", "-U", "postgres", "-d", database,
                               "-c", f"SELECT count(*) FROM {table}"]).strip()
        counts[table.replace('"', "")] = int(value) if value.isdigit() else None
    owners = stack.command([stack.docker, "exec", container_id, "psql", "-At", "-U", "postgres", "-d", database,
                            "-c", "SELECT string_agg(DISTINCT tableowner, ',') FROM pg_tables WHERE schemaname='public'"])
    fks = stack.command([stack.docker, "exec", container_id, "psql", "-At", "-U", "postgres", "-d", database,
                         "-c", "SELECT count(*) FROM pg_constraint WHERE contype='f'"])
    return {"tables": counts, "owners": owners.strip(), "foreignKeys": int(fks.strip() or 0)}


def _tar_reader(directory):
    """Stream a tar of directory without holding it in memory."""
    read_fd, write_fd = os.pipe()
    import threading

    def writer():
        with os.fdopen(write_fd, "wb") as sink, tarfile.open(fileobj=sink, mode="w|") as tar:
            tar.add(directory, arcname=".")

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    return os.fdopen(read_fd, "rb")
