"""Local SQLite + file/directory snapshots; caller must pause all application writers.

No encryption, retention or remote transport is provided here. Restore requires an
isolated empty target and a separately trusted archive checksum. Links and special
files are refused; files restore private and non-executable under the helper UID.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile

from .backup import snapshot_sqlite, verify_sqlite

MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 20000


def relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or
            PurePosixPath(value).is_absolute() or
            any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError("Invalid snapshot path")
    return value


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create(root, stream, database=None, directories=(), files=()):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid source root")
    paths = [relative(item) for item in directories]
    regular = [relative(item) for item in files]
    if database is not None:
        relative(database)
    selected = paths + regular + ([database] if database else [])
    if len(set(selected)) != len(selected) or any(
            a != b and PurePosixPath(a) in PurePosixPath(b).parents for a in selected for b in selected):
        raise ValueError("Overlapping snapshot paths")
    entries = {}
    total = 0
    def add(archive, source, name):
        nonlocal total
        relative(name)
        kind = source.lstat().st_mode
        if not (stat.S_ISREG(kind) or stat.S_ISDIR(kind)):
            raise ValueError("Links and special files cannot be snapshotted")
        if len(entries) >= MAX_FILES:
            raise ValueError("Snapshot file count limit")
        if stat.S_ISDIR(kind):
            info = tarfile.TarInfo("data/" + name)
            info.type, info.mode = tarfile.DIRTYPE, 0o700
            entries[name] = {"type": "directory"}
            archive.addfile(info)
            for child in sorted(source.iterdir()):
                add(archive, child, name + "/" + child.name)
        else:
            size = source.stat().st_size
            total += size
            if total > MAX_BYTES:
                raise ValueError("Snapshot byte limit")
            info = tarfile.TarInfo("data/" + name)
            info.size, info.mode = size, 0o600
            entries[name] = {"type": "file", "size": size, "sha256": checksum(source)}
            with source.open("rb") as data:
                archive.addfile(info, data)
    with tempfile.TemporaryDirectory(prefix="sp-snapshot-") as tmp:
        metadata = None
        with tarfile.open(fileobj=stream, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
            if database:
                # Reject symlinks in every component, including a parent directory.
                for part in (Path(database), *Path(database).parents):
                    if (root / part).is_symlink():
                        raise ValueError("Symlink database path")
                copied = Path(tmp) / "database.sqlite3"
                metadata = snapshot_sqlite(root / database, copied)
                add(archive, copied, database)
            for directory in paths:
                source = root / directory
                for part in (Path(directory), *Path(directory).parents):
                    if (root / part).is_symlink():
                        raise ValueError("Symlink directory path")
                if not source.is_dir():
                    raise ValueError("Declared directory missing")
                add(archive, source, directory)
            for name in regular:
                source = root / name
                for part in (Path(name), *Path(name).parents):
                    if (root / part).is_symlink():
                        raise ValueError("Symlink file path")
                if not source.is_file():
                    raise ValueError("Declared regular file missing")
                add(archive, source, name)
            manifest = {"format": 1, "uid": os.getuid(), "gid": os.getgid(),
                        "database": {"path": database, **metadata} if metadata else None,
                        "entries": entries}
            raw = json.dumps(manifest, sort_keys=True).encode()
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("Manifest too large")
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(raw), 0o600
            archive.addfile(info, io.BytesIO(raw))
        return manifest


def restore(archive_path, target, expected_sha256):
    target, archive_path = Path(target), Path(archive_path)
    if target.is_symlink() or not target.is_dir() or any(target.iterdir()):
        raise ValueError("Restore requires an empty isolated target")
    if archive_path.stat().st_size > MAX_BYTES + 32 * 1024 * 1024:
        raise ValueError("Archive byte limit")
    if checksum(archive_path) != expected_sha256:
        raise ValueError("Archive checksum mismatch")
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=target) as tmp:
        stage = Path(tmp)
        entries, manifest, total = {}, None, 0
        with tarfile.open(archive_path, "r:") as archive:
            count = 0
            for member in archive:
                count += 1
                if count > MAX_FILES + 1 or member.pax_headers:
                    raise ValueError("Archive member limit or unsupported metadata")
                if member.name == "manifest.json":
                    if manifest is not None or not member.isfile() or member.size > 8 * 1024 * 1024:
                        raise ValueError("Invalid archive manifest")
                    manifest = json.load(archive.extractfile(member))
                    continue
                if not member.name.startswith("data/"):
                    raise ValueError("Unexpected archive member")
                name = relative(member.name[5:].rstrip("/") if member.isdir() else member.name[5:])
                if name in entries or not (member.isfile() or member.isdir()):
                    raise ValueError("Duplicate, link or special archive member")
                path = stage / name
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True, mode=0o700)
                    path.chmod(0o700)
                    entries[name] = {"type": "directory"}
                else:
                    total += member.size
                    if member.size < 0 or total > MAX_BYTES:
                        raise ValueError("Archive data limit")
                    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with path.open("xb") as output:
                        os.chmod(path, 0o600)
                        shutil.copyfileobj(archive.extractfile(member), output)
                    entries[name] = {"type": "file", "size": path.stat().st_size, "sha256": checksum(path)}
        if (not isinstance(manifest, dict) or set(manifest) != {"format", "uid", "gid", "database", "entries"} or
                manifest["format"] != 1 or manifest["uid"] != os.getuid() or manifest["gid"] != os.getgid() or
                manifest["entries"] != entries):
            raise ValueError("Snapshot manifest or ownership mismatch")
        database = manifest["database"]
        if database is not None:
            path = stage / relative(database["path"])
            if database.get("engine") != "sqlite" or checksum(path) != database["sha256"]:
                raise ValueError("Database checksum mismatch")
            if verify_sqlite(path) != database["schemaVersion"]:
                raise ValueError("Database schema mismatch")
        # Implicit parent directories (for a nested database) are private too.
        for path in stage.rglob("*"):
            if path.is_dir():
                path.chmod(0o700)
        # The target must remain exclusively owned by this restore operation.
        if set(target.iterdir()) != {stage}:
            raise ValueError("Restore target changed")
        moved = []
        try:
            for child in list(stage.iterdir()):
                child.rename(target / child.name)
                moved.append(child.name)
        except BaseException:
            for name in reversed(moved):
                (target / name).rename(stage / name)
            raise
        return manifest


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    create_parser = commands.add_parser("create")
    create_parser.add_argument("root")
    create_parser.add_argument("--database")
    create_parser.add_argument("--directory", action="append", default=[])
    create_parser.add_argument("--file", action="append", default=[])
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("archive")
    restore_parser.add_argument("target")
    restore_parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.action == "create":
        create(args.root, sys.stdout.buffer, args.database, args.directory, args.file)
    else:
        restore(args.archive, args.target, args.sha256)

if __name__ == "__main__":
    main()
