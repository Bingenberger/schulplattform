import hashlib
import json
from pathlib import Path

import pytest
import schulplattform.pilot as module
from schulplattform.pilot import Pilot
from schulplattform.state import StateError


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    work = tmp_path / ".work"
    work.mkdir()
    (work / "docker-compose").write_bytes(b"synthetic executable fixture; never run")
    (work / "docker-compose.sha256").write_text(hashlib.sha256((work / "docker-compose").read_bytes()).hexdigest())
    return work


def test_legacy_configuration_keeps_two_apps_without_rewrite(root):
    directory = root / "legacy"
    directory.mkdir()
    config = directory / "config.json"
    config.write_text(json.dumps({"project": "sp-pilot-aabbccddeeff", "port": 4443}))
    before = config.read_bytes()
    assert Pilot(directory).apps == ("gswb", "schulwissen")
    assert config.read_bytes() == before
    with pytest.raises(StateError, match="selection changed"):
        Pilot(directory, apps=("gswb", "schulwissen", "zackboing"))
    assert config.read_bytes() == before


@pytest.mark.parametrize("selected", module.APP_SELECTIONS[1:])
def test_optional_apps_persist_and_excluded_app_never_creates_state(root, selected):
    directory = root / "three"
    assert Pilot(directory, apps=selected).apps == selected
    assert Pilot(directory).apps == selected
    forbidden = root / "forbidden"
    with pytest.raises(ValueError):
        Pilot(forbidden, apps=("gswb", "schulwissen", "schulkasse"))
    assert not forbidden.exists()


def test_uninstalled_app_status_does_not_run_compose(root):
    from schulplattform.pilot_engine import PilotEngine
    pilot = Pilot(root / "two")
    (pilot.directory / "state").mkdir()
    (pilot.directory / "state/installation.json").write_text('{"status":"completed"}')
    def forbidden(*args):
        raise AssertionError("Must not inspect an app outside the selected installation")
    pilot.inspect_service = forbidden
    assert PilotEngine(pilot).status("zackboing")["installed"] is False

def test_zackboing_stop_route_uses_its_declared_port(root):
    pilot = Pilot(root / "routes", apps=("gswb", "schulwissen", "zackboing"))
    def service(app, name):
        if app == "infra":
            return {"Id": "synthetic-proxy"}
        return {"State": {"Running": True}}
    pilot.inspect_service = service
    pilot.command = lambda *args, **kwargs: ""
    pilot.refresh_routes({"zackboing"})
    config = (pilot.directory / "Caddyfile").read_text()
    assert "reverse_proxy zackboing:3000" not in config
    assert 'respond "Wartung" 503' in config
    assert "reverse_proxy schulwissen:8000" in config


def test_stopping_already_stopped_quiz_does_not_call_private_control(root):
    pilot = Pilot(root / "stopped", apps=("gswb", "schulwissen", "zackboing"))
    pilot.inspect_service = lambda *args: {"State": {"Running": False}}
    def forbidden(*args):
        raise AssertionError("Cannot drain a stopped container")
    pilot.quiz_control = forbidden
    pilot.stop()
    pilot.stop()


def test_private_projections_work_under_restrictive_umask(root):
    import os
    pilot = Pilot(root / "restrictive", apps=module.APP_SELECTIONS[-1])
    previous = os.umask(0o077)
    try:
        pilot.materialize()
    finally:
        os.umask(previous)
    runtime = pilot.directory / "runtime"
    assert runtime.stat().st_mode & 0o777 == 0o700
    for app in ("leseflux", "fahrrad", "losverkauf", "abgen"):
        assert (runtime / app).stat().st_mode & 0o777 == 0o700
    for path in runtime.rglob("*"):
        if path.is_file():
            assert path.stat().st_mode & 0o777 == 0o444
    assert all(path.stat().st_mode & 0o777 == 0o600
               for path in (pilot.directory / "secrets").iterdir() if path.is_file())


def test_competency_stop_pauses_background_writer_before_web(root):
    from schulplattform.pilot_engine import PilotEngine
    pilot=Pilot(root/"background",apps=module.APP_SELECTIONS[-1])
    (pilot.directory/"state").mkdir()
    (pilot.directory/"state/installation.json").write_text('{"status":"completed"}')
    commands=[]
    pilot.refresh_routes=lambda maintenance:None
    pilot.compose_command=lambda *args:commands.append(args)
    pilot.inspect_service=lambda *args:None
    PilotEngine(pilot).execute("stop","kompetenz-manager")
    assert [cmd[-1] for cmd in commands]==["worker","app"]

def test_competency_failed_worker_degrades_running_app(root):
    from schulplattform.pilot_engine import PilotEngine
    pilot=Pilot(root/"degraded",apps=module.APP_SELECTIONS[-1])
    (pilot.directory/"state").mkdir()
    (pilot.directory/"state/installation.json").write_text('{"status":"completed"}')
    def inspect(app,service):
        return {"Image":"synthetic-image","State":{"Running":service=="app","Health":{"Status":"healthy"}}}
    pilot.inspect_service=inspect
    status=PilotEngine(pilot).status("kompetenz-manager")
    assert status["running"] and status["health"]=="degraded"
    assert not pilot.ready("synthetic-installation")


@pytest.mark.parametrize("failed", ["pdf", "postgres"])
def test_worksheet_auxiliary_failure_degrades_whole_app(root, failed):
    from schulplattform.pilot_engine import PilotEngine
    pilot=Pilot(root/"worksheet-health",apps=module.APP_SELECTIONS[-1])
    (pilot.directory/"state").mkdir()
    (pilot.directory/"state/installation.json").write_text('{"status":"completed"}')
    def inspect(app,service):
        return {"Image":"synthetic-image","State":{"Running":service!=failed,
                "Health":{"Status":"healthy"}}}
    pilot.inspect_service=inspect
    status=PilotEngine(pilot).status("abgen")
    assert status["running"] and status["health"]=="degraded"
    assert not pilot.ready("synthetic-installation")


def test_worksheet_stop_drains_before_web_and_pdf_stop(root):
    from schulplattform.pilot_engine import PilotEngine
    pilot=Pilot(root/"worksheet-stop",apps=module.APP_SELECTIONS[-1])
    (pilot.directory/"state").mkdir()
    (pilot.directory/"state/installation.json").write_text('{"status":"completed"}')
    operations=[]
    pilot.inspect_service=lambda *args: {"Image":"synthetic","State":{"Running":True,"Health":{"Status":"healthy"}}}
    pilot.refresh_routes=lambda maintenance:operations.append(("routes",maintenance))
    pilot.abgen_control=lambda action:operations.append(("control",action))
    pilot.compose_command=lambda *args:operations.append(args)
    PilotEngine(pilot).execute("stop","abgen")
    assert operations==[("routes",{"abgen"}),("control","prepare-stop"),
                        ("abgen","stop","--timeout","130","app"),
                        ("abgen","stop","--timeout","60","pdf")]


@pytest.mark.parametrize("selected", [module.APP_SELECTIONS[-2],module.APP_SELECTIONS[-1]])
def test_worksheet_plan_binds_auxiliary_images_only_when_selected(root,monkeypatch,selected):
    pilot=Pilot(root/"worksheet-images",apps=selected)
    captured={}
    class Installation:
        def __init__(self,*args):pass
        def run(self,plan,steps):
            captured.update(plan)
            return {"id":"synthetic","status":"completed"}
    monkeypatch.setattr(module,"Installation",Installation)
    pilot.command=lambda command:json.dumps([{"Id":"synthetic-id-for-"+command[-1]}])
    pilot.up(check_running=False)
    auxiliary={"abgen-pdf","abgen-postgres"} & set(captured["images"])
    assert auxiliary==({"abgen-pdf","abgen-postgres"} if "abgen" in selected else set())
    assert len(captured["images"])==len(selected)+len(auxiliary)
