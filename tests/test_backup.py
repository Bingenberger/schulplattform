from pathlib import Path
import sqlite3

import pytest
from schulplattform.backup import restore_sqlite, snapshot_sqlite


def test_wal_snapshot_restore_and_nonempty_refusal(tmp_path):
    source, snapshot, restored = [tmp_path / name for name in ('live.db', 'snapshot.db', 'restored.db')]
    with sqlite3.connect(source) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA user_version=7')
        db.execute('CREATE TABLE owners(id INTEGER PRIMARY KEY)')
        db.execute('CREATE TABLE records(owner INTEGER REFERENCES owners(id), value TEXT)')
        db.execute('INSERT INTO owners VALUES(3)')
        db.execute("INSERT INTO records VALUES(3, 'synthetic')")
        db.commit()
        metadata = snapshot_sqlite(source, snapshot)
        restore_sqlite(snapshot, restored, metadata)
        with sqlite3.connect(restored) as check:
            assert check.execute('SELECT * FROM records').fetchall() == [(3, 'synthetic')]
            assert check.execute('PRAGMA user_version').fetchone() == (7,)
        with pytest.raises(FileExistsError):
            restore_sqlite(snapshot, restored, metadata)


def test_corrupt_and_foreign_key_invalid_snapshots_rejected(tmp_path):
    source = tmp_path / 'invalid.db'
    with sqlite3.connect(source) as db:
        db.executescript('CREATE TABLE p(id INTEGER PRIMARY KEY); CREATE TABLE c(p REFERENCES p(id)); INSERT INTO c VALUES(9);')
    with pytest.raises(ValueError, match='foreign key'):
        snapshot_sqlite(source, tmp_path / 'snapshot.db')
    assert not (tmp_path / 'snapshot.db').exists()
