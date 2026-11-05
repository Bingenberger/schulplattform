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
