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


@pytest.mark.parametrize("selected", [("gswb", "schulwissen", "zackboing"), ("gswb", "schulwissen", "zackboing", "schulhelfer"), ("gswb", "schulwissen", "zackboing", "schulhelfer", "losverkauf")])
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
