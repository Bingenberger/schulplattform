import io
import json
from pathlib import Path
import sqlite3
import tarfile

import pytest

from schulplattform.snapshot import create, restore, checksum


def fixture(root):
    (root / "uploads/empty").mkdir(parents=True)
    (root / "uploads/media.png").write_bytes(b"synthetic media")
    with sqlite3.connect(root / "app.db") as db:
        db.executescript("PRAGMA journal_mode=WAL; PRAGMA user_version=3; CREATE TABLE users(id INTEGER PRIMARY KEY);"
                         "CREATE TABLE owned(user INTEGER REFERENCES users(id)); INSERT INTO users VALUES(7); INSERT INTO owned VALUES(7);")


def test_combined_restore_preserves_schema_owners_media_and_private_permissions(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    fixture(source)
    archive = tmp_path / "snapshot.tar"
    with archive.open("wb") as stream:
        create(source, stream, "app.db", ["uploads"])
    manifest = restore(archive, target, checksum(archive))
    assert manifest["database"]["schemaVersion"] == 3
    with sqlite3.connect(target / "app.db") as db:
        assert db.execute("SELECT user FROM owned").fetchall() == [(7,)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (target / "uploads/media.png").read_bytes() == b"synthetic media"
    assert (target / "uploads/empty").is_dir()
    assert (target / "uploads").stat().st_mode & 0o777 == 0o700
    assert (target / "uploads/media.png").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="empty"):
        restore(archive, target, checksum(archive))


def test_directory_only_and_checksum_failure_leave_target_empty(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "files").mkdir()
    (source / "files/a").write_text("synthetic")
    archive = tmp_path / "snapshot.tar"
    with archive.open("wb") as stream:
        create(source, stream, directories=["files"])
    with pytest.raises(ValueError, match="checksum"):
        restore(archive, target, "0" * 64)
    assert list(target.iterdir()) == []
    assert restore(archive, target, checksum(archive))["database"] is None


@pytest.mark.parametrize("kind", ["traversal", "symlink", "hardlink", "duplicate", "hash"])
def test_untrusted_archive_members_rejected_without_partial_restore(tmp_path, kind):
    archive, target = tmp_path / "bad.tar", tmp_path / "target"
    target.mkdir()
    with tarfile.open(archive, "w") as tar:
        info = tarfile.TarInfo("data/../escape" if kind == "traversal" else "data/a")
        info.size = 1
        if kind in ("symlink", "hardlink"):
            info.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        else:
            tar.addfile(info, io.BytesIO(b"x"))
            if kind == "duplicate":
                tar.addfile(info, io.BytesIO(b"x"))
            # A valid outer checksum does not excuse missing/incorrect content inventory.
            raw = json.dumps({"format": 1, "uid": __import__("os").getuid(), "gid": __import__("os").getgid(),
                              "database": None, "entries": {}}).encode()
            manifest = tarfile.TarInfo("manifest.json")
            manifest.size = len(raw)
            tar.addfile(manifest, io.BytesIO(raw))
    with pytest.raises(ValueError):
        restore(archive, target, checksum(archive))
    assert list(target.iterdir()) == []
    assert not (tmp_path / "escape").exists()


def test_snapshot_rejects_source_symlinks_and_overlapping_database_selection(tmp_path):
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads/link").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="Links"):
        create(tmp_path, io.BytesIO(), directories=["uploads"])
    with pytest.raises(ValueError, match="Overlapping"):
        create(tmp_path, io.BytesIO(), "uploads/db", ["uploads"])
