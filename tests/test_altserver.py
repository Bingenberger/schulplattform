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
