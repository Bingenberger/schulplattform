"""Consistent SQLite staging. Call only during a coordinated writer pause.

This is a local snapshot primitive, not an encrypted offsite backup service.
The orchestrator must pause writers across the DB and all associated files.
"""
import hashlib
from pathlib import Path
import sqlite3
import os


def verify_sqlite(path: Path):
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key check failed')
        return db.execute('PRAGMA user_version').fetchone()[0]


def snapshot_sqlite(source: Path, destination: Path):
    if not source.is_file():
        raise ValueError('Source database does not exist')
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
        version = verify_sqlite(destination)
        with destination.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return {'engine': 'sqlite', 'schemaVersion': version, 'sha256': digest}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def restore_sqlite(source: Path, destination: Path, expected: dict):
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected['sha256']:
            raise ValueError('Snapshot checksum mismatch')
    if verify_sqlite(source) != expected['schemaVersion']:
        raise ValueError('Snapshot schema version mismatch')
    # O_EXCL in snapshot_sqlite rejects any existing destination, including links.
    return snapshot_sqlite(source, destination)
