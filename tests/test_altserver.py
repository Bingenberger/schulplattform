import json
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("altserver", ROOT / "scripts/altserver/schulplattform_altserver.py")
altserver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(altserver)


def test_database_is_reported_without_credentials():
    url = "postgresql://kompetenz_user:/ab+c/d@127.0.0.1:5432/kompetenz_manager_utf8"
    report = altserver.redacted_database(url)
    assert report == {"engine": "postgresql", "database": "kompetenz_manager_utf8"}
    assert "ab+c" not in str(report)
    assert altserver.redacted_database("") == {"engine": "sqlite"}


def test_env_values_accept_quotes_and_export(tmp_path):
    env = tmp_path / "app.env"
    env.write_text("export DATABASE_URL='postgresql://u:p@h/db'\nSECRET_KEY=\"abc\"\n# comment\n")
    assert altserver.env_values(env) == {"DATABASE_URL": "postgresql://u:p@h/db", "SECRET_KEY": "abc"}


def test_missing_tools_do_not_abort_the_inventory(monkeypatch):
    def missing(argv, **kwargs):
        raise FileNotFoundError(argv[0])
    monkeypatch.setattr(subprocess, "run", missing)
    monkeypatch.setattr(altserver.shutil, "which", lambda name: None)
    report = altserver.inventory({}, {})
    assert report["apps"]["schulwissen"]["note"] == "docker is not installed on this host"
    assert report["runningServices"] == [] and report["composeProjects"] == []


def test_service_listing_omits_arguments(monkeypatch):
    def fake(argv, **kwargs):
        if argv[:2] == ["systemctl", "list-units"]:
            out = "kompetenzkompass.service loaded active running KM\n"
        elif argv[0] == "systemctl":
            out = ("WorkingDirectory=/home/kompkomp\nUser=kompetenzkompass\n"
                   "ExecStart={ path=/home/kompkomp/venv/bin/gunicorn ; argv[]=/home/kompkomp/venv/bin/gunicorn "
                   "--password hunter2 ; ignore_errors=no }\n")
        else:
            return subprocess.CompletedProcess(argv, 1, "", "")
        return subprocess.CompletedProcess(argv, 0, out, "")
    monkeypatch.setattr(altserver, "run", fake)
    services = altserver.running_services()
    assert services == [{"unit": "kompetenzkompass.service", "user": "kompetenzkompass",
                         "workingDirectory": "/home/kompkomp", "program": "/home/kompkomp/venv/bin/gunicorn",
                         "commit": None}]
    assert altserver.unit_for(Path("/home/kompkomp")) == "kompetenzkompass.service"


def test_fundkiste_export_carries_team_key_from_unit(tmp_path, monkeypatch):
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/fundkiste"
    (base / "data/photos").mkdir(parents=True)
    sqlite3.connect(base / "data/fundkiste.db").executescript(
        "CREATE TABLE items(id TEXT PRIMARY KEY, category TEXT NOT NULL); INSERT INTO items VALUES('a','jacke');")
    (base / "data/photos/x.jpg").write_bytes(b"jpg")
    (base / "data/team_key.txt").write_text("veraltet-123")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: "fundkiste.service")
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {"FUNDKISTE_TEAM_KEY": "AusDerUnit12"})
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("fundkiste", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
        assert "./photos/x.jpg" in names and names.count("./team_key.txt") == 1
        assert inner.extractfile("./team_key.txt").read() == b"AusDerUnit12"
    assert (tmp_path / "x/sqlite/data/fundkiste.db").exists()
    assert "./fundkiste.db" not in names


def test_schuleva_export_moves_surveys_and_skips_cron_copies(tmp_path, monkeypatch):
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/schulbefragung"
    (base / "data/backups").mkdir(parents=True)
    (base / "surveys").mkdir()
    sqlite3.connect(base / "data/db.sqlite").executescript("CREATE TABLE responses(id INTEGER); INSERT INTO responses VALUES(1);")
    shutil.copy(base / "data/db.sqlite", base / "data/backups/db-20260101.sqlite")
    (base / "surveys/eltern_kl4.json").write_text('{"id": "eltern_kl4", "title": "eigene Fassung"}')
    (base / ".env").write_text("SECRET_KEY=geheim\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("schuleva", key, tmp_path / "out", path=str(base))
    assert summary["sqliteFiles"] == 1
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
        assert not any("backups" in name for name in outer.getnames())
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
        assert "./surveys/eltern_kl4.json" in names
        assert not any("backups" in name for name in names) and "./db.sqlite" not in names
    assert (tmp_path / "x/sqlite/data/db.sqlite").exists()
    assert "secrets" not in json.loads((tmp_path / "x/backup.json").read_text())


def test_schulkasse_export_carries_the_2fa_key_and_skips_own_backups(tmp_path, monkeypatch):
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/schulkasse"
    (base / "instance/belege").mkdir(parents=True)
    (base / "instance/backups").mkdir()
    sqlite3.connect(base / "instance/schulkasse.sqlite3").executescript(
        "CREATE TABLE benutzer(id INTEGER, totp_secret TEXT); INSERT INTO benutzer VALUES(1,'verschluesselt');")
    (base / "instance/belege/beleg1.pdf").write_bytes(b"%PDF")
    (base / "instance/brief.toml").write_text('schulname = "GGS"\n')
    (base / "instance/backups/schulkasse-backup-1.tar.gz").write_bytes(b"x")
    (base / ".env").write_text("SCHULKASSE_SECRET_KEY='" + "a" * 64 + "'\nSCHULKASSE_PORT=5015\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("schulkasse", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    info = json.loads((tmp_path / "x/backup.json").read_text())
    assert info["secrets"] == ["schulkasse-key"]
    assert (tmp_path / "x/secrets/schulkasse-key").read_text() == "a" * 64
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
    assert {"./belege/beleg1.pdf", "./brief.toml"} <= set(names)
    assert not any("backups" in n for n in names)
    assert (tmp_path / "x/sqlite/data/schulkasse.sqlite3").exists()


def test_schulanmeldung_export_follows_env_paths_and_takes_the_signature(tmp_path, monkeypatch):
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "home/SL-Office"
    (base / "uploads/gutachten").mkdir(parents=True)
    (base / "assets/briefkopf").mkdir(parents=True)
    store = tmp_path / "srv/sl"
    store.mkdir(parents=True)
    sqlite3.connect(store / "prod.db").executescript(
        "CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('b4c1e82f5a37');"
        "CREATE TABLE schueler(id INTEGER); INSERT INTO schueler VALUES(1),(2);")
    (base / "uploads/gutachten/a.pdf").write_bytes(b"%PDF")
    (base / "assets/briefkopf/unterschrift.png").write_bytes(b"PNG")
    (base / ".env").write_text(f"SL_OFFICE_ENV=production\nSL_OFFICE_DATABASE_URL=sqlite:///{store}/prod.db\n"
                               "SL_OFFICE_SECRET_KEY=" + "z" * 40 + "\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {})
    report = altserver.inventory({"schulanmeldung": str(base)}, {})["apps"]["schulanmeldung"]
    sources = {s["target"]: s for s in report["data"]["data"]["sources"]}
    assert sources["data:database.db"]["sqlite"][0]["tables"]["schueler"] == 2
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("schulanmeldung", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    info = json.loads((tmp_path / "x/backup.json").read_text())
    assert info["counts"]["data/database.db"]["schueler"] == 2 and info["sqlite"][0]["alembic"] == ["b4c1e82f5a37"]
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = set(inner.getnames())
    assert {"./uploads/gutachten/a.pdf", "./briefkopf/unterschrift.png"} <= names
    assert "secrets" not in info   # the session key is not needed: TOTP and parent links do not depend on it
    uploads = [r for r in summary["relocated"] if r["to"] == "data:uploads"]
    assert uploads[0]["files"] == 1                    # visible in the export output
    # Real old server: the export was tiny because the uploads were elsewhere; it must not skip them.
    (base / ".env").write_text((base / ".env").read_text() + f"SL_OFFICE_UPLOAD_FOLDER={tmp_path}/fehlt\n")
    import pytest
    with pytest.raises(SystemExit, match="fehlt.*nicht gefunden"):
        altserver.export("schulanmeldung", key, tmp_path / "out2", path=str(base))


def test_sl_journal_export_needs_stopped_service_and_carries_the_database_key(tmp_path, monkeypatch):
    import shutil
    import tarfile
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/schulleitungsjournal"
    base.mkdir(parents=True)
    instance = tmp_path / "var/lib/schulleitungsjournal"
    (instance / "attachments").mkdir(parents=True)
    (instance / "backups").mkdir()
    (instance / "journal.db").write_bytes(b"SQLCipher-verschluesselt")
    (instance / "attachments/a1").write_bytes(b"fernet-token")
    (instance / "backup.key").write_text("b" * 44)
    (instance / "backups/journal-1.backup").write_bytes(b"x")
    keyfile = tmp_path / "etc/schulleitungsjournal/master.key"
    keyfile.parent.mkdir(parents=True)
    keyfile.write_text("m" * 43 + "=\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {"JOURNAL_INSTANCE": str(instance),
                                                                "JOURNAL_KEY_FILE": str(keyfile)})
    active = {"state": "active"}
    real_run = altserver.run
    monkeypatch.setattr(altserver, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, active["state"], "")
                        if argv[:2] == ["systemctl", "is-active"] else real_run(argv, **kw))
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    with pytest.raises(SystemExit, match="läuft noch"):
        altserver.export("sl-journal", key, tmp_path / "out", path=str(base))
    active["state"] = "inactive"
    summary = altserver.export("sl-journal", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    info = json.loads((tmp_path / "x/backup.json").read_text())
    assert info["secrets"] == ["sl-journal/master-key"]
    assert (tmp_path / "x/secrets/sl-journal/master-key").read_text() == "m" * 43 + "="
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = set(inner.getnames())
    assert {"./journal.db", "./attachments/a1", "./backup.key"} <= names
    assert not any(n.startswith("./backups") or n.endswith("master.key") for n in names)


def test_zackboing_export_takes_wal_contents_and_uploads(tmp_path, monkeypatch):
    import pytest
    # Real old server: zackboing.db was 4 KiB while the rows sat in the WAL (the Node process keeps
    # the database open). The export must carry the WAL contents, not the stale main file.
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/zackboing"
    base.mkdir(parents=True)
    data = tmp_path / "var/lib/zackboing"
    (data / "uploads").mkdir(parents=True)
    (data / "uploads/bild.png").write_bytes(b"png")
    live = sqlite3.connect(data / "zackboing.db")
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT, name TEXT, pass_hash TEXT);"
                       "CREATE TABLE quizzes(id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT);")
    live.executemany("INSERT INTO quizzes(user_id, title) VALUES(1, ?)", [(f"Quiz {i}",) for i in range(33)])
    live.commit()                                   # stays in the WAL: connection open, no checkpoint
    assert (data / "zackboing.db-wal").stat().st_size > 0
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: "zackboing.service")
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    monkeypatch.setattr(altserver, "unit_environment", lambda unit: {"ZACKBOING_DATA": str(tmp_path / "fehlt")})
    with pytest.raises(SystemExit, match="kein Datenverzeichnis"):
        altserver.export("zackboing", key, tmp_path / "out", path=str(base))
    monkeypatch.setattr(altserver, "unit_environment", lambda unit: {"ZACKBOING_DATA": str(data)})
    summary = altserver.export("zackboing", key, tmp_path / "out", path=str(base))
    live.close()
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
    assert "./uploads/bild.png" in names
    assert not {"./zackboing.db", "./zackboing.db-wal", "./zackboing.db-shm"} & set(names)
    copy = sqlite3.connect(tmp_path / "x/sqlite/data/zackboing.db")
    assert copy.execute("SELECT count(*) FROM quizzes").fetchone()[0] == 33


def test_import_decrypt_error_names_the_gpg_reason(tmp_path):
    # Real server: a zackboing archive failed with only "wrong key or modified file"; gpg's own
    # message tells a wrong key from a truncated copy.
    import shutil
    import types
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    from schulplattform import importer
    from schulplattform.state import StateError
    secrets = tmp_path / "secrets"
    secrets.mkdir(mode=0o700)
    key = secrets / importer.TRANSFER_KEY
    key.write_text("k" * 48)
    key.chmod(0o600)
    platform = types.SimpleNamespace(layout=types.SimpleNamespace(secrets=secrets))
    plain = tmp_path / "plain.tar"
    plain.write_bytes(b"x" * 4096)
    archive = tmp_path / "a.tar.gpg"
    other = tmp_path / "other.key"
    other.write_text("o" * 48)
    altserver.gpg_encrypt(plain, archive, other)               # encrypted for a different server
    work = tmp_path / "work"
    work.mkdir(mode=0o700)
    # Real server: a typo in the file name was reported as a wrong transfer key.
    with pytest.raises(StateError, match="not found"):
        importer.decrypt(platform, tmp_path / "tippfehler.tar.gpg", work)
    with pytest.raises(StateError, match="gpg: .+"):
        importer.decrypt(platform, archive, work)


def test_import_reports_a_truncated_archive(tmp_path):
    import shutil
    import types
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    from schulplattform import importer
    from schulplattform.state import StateError
    secrets = tmp_path / "secrets"
    secrets.mkdir(mode=0o700)
    key = secrets / importer.TRANSFER_KEY
    key.write_text("k" * 48)
    platform = types.SimpleNamespace(layout=types.SimpleNamespace(secrets=secrets))
    source = tmp_path / "src"
    source.mkdir()
    (source / "f").write_bytes(__import__("os").urandom(100000))   # incompressible
    plain = tmp_path / "plain.tar"
    import tarfile
    with tarfile.open(plain, "w") as tar:
        tar.add(source / "f", arcname="f")
    archive = tmp_path / "a.tar.gpg"
    altserver.gpg_encrypt(plain, archive, key)
    archive.write_bytes(archive.read_bytes()[:2000])           # interrupted scp
    work = tmp_path / "work"
    work.mkdir(mode=0o700)
    with pytest.raises(StateError, match="incomplete|transfer key"):
        importer.decrypt(platform, archive, work)


def test_losverkauf_export_skips_backup_copies_and_carries_tokens(tmp_path, monkeypatch):
    # Real old server: data/backups held four older copies with personal data ('deploy.sh backup').
    import shutil
    import sqlite3
    import tarfile
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/losverkauf"
    (base / "data/backups").mkdir(parents=True)
    (base / "static").mkdir()
    sqlite3.connect(base / "data/losverkauf.db").executescript(
        "CREATE TABLE personen(id INTEGER); INSERT INTO personen VALUES(1),(2);")
    shutil.copy(base / "data/losverkauf.db", base / "data/backups/losverkauf-20260924-063156.db")
    (base / "static/bezirke.geojson").write_text("{}")
    (base / "losverkauf.env").write_text("ELTERN_TOKEN=" + "e" * 40 + "\nSECRET_KEY=" + "s" * 40 + "\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("losverkauf", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
    assert not any("backups" in name for name in names)
    assert "./maps/bezirke.geojson" in names
    assert sorted(p.name for p in (tmp_path / "x/sqlite/data").rglob("*.db")) == ["losverkauf.db"]
    assert (tmp_path / "x/secrets/losverkauf/parent-token").read_text() == "e" * 40
    assert summary["sqliteFiles"] == 1


def test_schulanmeldung_export_merges_old_default_and_configured_upload_folders(tmp_path, monkeypatch):
    # Real old server: SL_OFFICE_UPLOAD_FOLDER=/opt/SL-Office/documents held 1 PDF, the default
    # uploads/ the other 198 from before the .env change.
    import shutil
    import sqlite3
    import tarfile
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/SL-Office"
    for folder in ("uploads", "documents", "instance"):
        (base / folder).mkdir(parents=True)
    sqlite3.connect(base / "instance/database.db").executescript(
        "CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('x');")
    for name in ("alt1.pdf", "alt2.pdf"):
        (base / "uploads" / name).write_bytes(b"%PDF alt")
    (base / "documents/neu.pdf").write_bytes(b"%PDF neu")
    (base / ".env").write_text(f"SL_OFFICE_DATABASE_URL=sqlite:///{base}/instance/database.db\n"
                               f"SL_OFFICE_UPLOAD_FOLDER={base}/documents\n")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {})
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("schulanmeldung", key, tmp_path / "out", path=str(base))
    assert sorted(r["files"] for r in summary["relocated"] if r["to"] == "data:uploads") == [1, 2]
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = inner.getnames()
    assert {"./uploads/alt1.pdf", "./uploads/alt2.pdf", "./uploads/neu.pdf"} <= set(names)
    (base / "uploads/neu.pdf").write_bytes(b"%PDF andere Fassung")
    with pytest.raises(SystemExit, match="zwei Upload-Verzeichnissen"):
        altserver.export("schulanmeldung", key, tmp_path / "out2", path=str(base))


def test_grundschultafel_export_moves_public_assets_into_the_data_volume(tmp_path, monkeypatch):
    # Real old server (/var/www/tafelpopafel): notebooks and users under data/, images under
    # public/assets; the platform image ships no images and reads /data/assets.
    import shutil
    import tarfile
    import pytest
    if not shutil.which("gpg"):
        pytest.skip("gpg not installed")
    base = tmp_path / "var/www/tafelpopafel"
    uid = "0b6f5c1e-1111-4222-8333-944455556666"
    (base / "data" / uid).mkdir(parents=True)
    (base / "data/users.json").write_text('[{"id": "%s", "username": "frau.x"}]' % uid)
    (base / "data" / uid / "nb1.json").write_text("{}")
    (base / "public/assets/gallery/Mixed").mkdir(parents=True)
    (base / "public/assets/gallery/Mixed/bild.png").write_bytes(b"png")
    (base / "public/timer").mkdir(parents=True)
    (base / "public/timer/index.html").write_text("timer")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: preferred)
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {})
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("grundschultafel", key, tmp_path / "out", path=str(base))
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/data/files.tar") as inner:
        names = set(inner.getnames())
    assert {"./users.json", f"./{uid}/nb1.json", "./assets/gallery/Mixed/bild.png"} <= names
    assert not any("timer" in name for name in names)


def test_compose_app_is_not_reported_from_another_apps_database_container(monkeypatch):
    # Real old server "whiteboard": only fahrradausbildung runs there, yet schulwissen was reported
    # present because its db service name matched fahrradausbildung's container.
    labels = json.dumps({"com.docker.compose.project": "fahrradausbildung",
                         "com.docker.compose.project.working_dir": "/opt/fahrradausbildung"})
    def fake(argv, **kwargs):
        if argv[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, labels, "")
        if argv[:2] == ["docker", "exec"] and "-d" in argv and argv[argv.index("-d") + 1] != "fahrrad":
            return subprocess.CompletedProcess(argv, 2, "", "FATAL: role does not exist")
        if argv[:2] == ["docker", "exec"] and argv[-1] == "SHOW server_version":
            return subprocess.CompletedProcess(argv, 0, "16.15\n", "")
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(altserver, "run", fake)
    monkeypatch.setattr(altserver, "compose_container", lambda project, service: "c1")
    monkeypatch.setattr(altserver, "git_commit", lambda path: None)
    monkeypatch.setattr(altserver, "env_names", lambda path: [])
    monkeypatch.setattr(altserver, "running_services", lambda: [])
    monkeypatch.setattr(altserver, "compose_projects", lambda: [], raising=False)
    report = altserver.inventory({}, {})["apps"]
    assert report["schulwissen"]["present"] is False and "another app" in report["schulwissen"]["note"]
    assert report["fahrradausbildung"]["present"] is True


def test_bildergalerie_export_moves_static_images_with_checksums(tmp_path, monkeypatch):
    import hashlib
    import shutil
    import sqlite3
    import tarfile
    if not shutil.which("gpg"):
        import pytest
        pytest.skip("gpg not installed")
    base = tmp_path / "opt/bildergalerie"
    (base / "instance").mkdir(parents=True)
    sqlite3.connect(base / "instance/gallery.db").executescript(
        "CREATE TABLE image(id INTEGER PRIMARY KEY, filename TEXT); INSERT INTO image VALUES(311,'Apfel_f807ab63.png');")
    for kind, name, data in (("uploads", "Apfel_f807ab63.png", b"png"), ("display", "Apfel_f807ab63.webp", b"d"),
                             ("thumbnails", "Apfel_f807ab63.webp", b"t")):
        (base / "static" / kind).mkdir(parents=True)
        (base / "static" / kind / name).write_bytes(data)
    (base / "static/style.css").write_text("css")                # code assets stay behind
    (base / ".env").write_text("DATABASE_URL=sqlite:///gallery.db\nSECRET_KEY=geheim\n")
    (base / "key3.json").write_text("{}")
    monkeypatch.setattr(altserver, "unit_for", lambda base, preferred=None: "bildergalerie.service")
    monkeypatch.setattr(altserver, "unit_values", lambda unit: {})
    key = tmp_path / "transfer.key"
    key.write_text("k" * 48)
    summary = altserver.export("bildergalerie", key, tmp_path / "out", path=str(base))
    assert summary["volumes"] == ["db", "media"]
    plain = tmp_path / "plain.tar"
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase-file", str(key), "-o", str(plain), "-d",
                    summary["archive"]], check=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    with tarfile.open(plain) as outer:
        outer.extractall(tmp_path / "x", filter="data")
    with tarfile.open(tmp_path / "x/volumes/media/files.tar") as inner:
        files = sorted(n for n in inner.getnames() if inner.getmember(n).isfile())
    assert files == ["./display/Apfel_f807ab63.webp", "./thumbnails/Apfel_f807ab63.webp", "./uploads/Apfel_f807ab63.png"]
    assert sqlite3.connect(tmp_path / "x/sqlite/db/gallery.db").execute("SELECT id FROM image").fetchall() == [(311,)]
    info = json.loads((tmp_path / "x/backup.json").read_text())
    assert info["checksums"]["media"]["uploads/Apfel_f807ab63.png"] == hashlib.sha256(b"png").hexdigest()
    assert len(info["checksums"]["media"]) == 3
    assert not info.get("secrets")                               # session key and AI key stay behind
    assert summary["sha256"] == hashlib.sha256(Path(summary["archive"]).read_bytes()).hexdigest()


def test_import_checksum_verification_finds_missing_and_changed_files(tmp_path):
    import hashlib
    import sys
    from types import SimpleNamespace
    from schulplattform import importer
    volume = tmp_path / "volume"
    (volume / "uploads").mkdir(parents=True)
    (volume / "uploads/a.png").write_bytes(b"a")
    (volume / "uploads/b.png").write_bytes(b"changed")
    files = {"uploads/a.png": hashlib.sha256(b"a").hexdigest(), "uploads/b.png": hashlib.sha256(b"b").hexdigest(),
             "uploads/c.png": hashlib.sha256(b"c").hexdigest(), "../../etc/passwd": "0" * 64}

    def command(argv, timeout=None):
        # run the helper's script locally against the temporary "volume"
        manifest = next(a.split(":")[0] for a in argv if a.endswith(":/manifest.json:ro"))
        script = argv[-1].replace("'/manifest.json'", repr(manifest)).replace("'/data'", repr(str(volume))) \
            .replace("'/data/'", repr(str(volume) + "/"))
        return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True).stdout

    service = SimpleNamespace(stack=SimpleNamespace(docker="docker", command=command))
    result = importer.verify_checksums(service, "bildergalerie", {"checksums": {"media": files}}, tmp_path)
    assert result["media"]["checked"] == 4
    assert result["media"]["different"] == ["uploads/b.png"]
    assert sorted(result["media"]["missing"]) == ["../../etc/passwd", "uploads/c.png"]
