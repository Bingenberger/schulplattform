import json

import pytest
from schulplattform.domains import Domains, DomainError


def test_success_invalid_change_and_failed_probe_rollback(tmp_path):
    live = {"gswb": "old.example.invalid"}
    initial = dict(live)
    calls = []
    def activate(domains):
        live.clear()
        live.update(domains)
        calls.append(dict(domains))
    driver = Domains(tmp_path, initial, "admin.example.invalid", lambda old, new: True,
                     activate, lambda domains, changed: domains["gswb"] != "broken.example.invalid")
    driver.change("gswb", "new.example.invalid")
    assert live["gswb"] == "new.example.invalid"
    with pytest.raises(ValueError):
        driver.change("gswb", "evil.invalid\nadmin off")
    assert len(calls) == 1
    with pytest.raises(DomainError, match="restored"):
        driver.change("gswb", "broken.example.invalid")
    assert live["gswb"] == "new.example.invalid"
    assert json.loads(driver.path.read_text())["domains"] == live
    with pytest.raises(ValueError, match="administrative"):
        driver.change("gswb", "admin.example.invalid")


def test_crashed_activation_recovers_before_next_change(tmp_path):
    live = {"gswb": "old.example.invalid"}
    driver = Domains(tmp_path, dict(live), "admin.example.invalid", lambda old, new: True,
                     lambda domains: live.update(domains), lambda domains, changed: True)
    old = json.loads(driver.path.read_text())
    candidate = {"generation": "synthetic", "domains": {"gswb": "interrupted.example.invalid"}}
    driver.pending.write_text(json.dumps({"old": old, "candidate": candidate, "status": "applying"}))
    live.update(candidate["domains"])
    driver.recover()
    assert live == old["domains"]
    assert json.loads(driver.pending.read_text())["status"] == "rolled-back"


def test_recovery_failure_keeps_pending_and_refuses_followup(tmp_path):
    driver = Domains(tmp_path, {"gswb": "old.example.invalid"}, "admin.example.invalid",
                     lambda old, new: True, lambda domains: None, lambda domains, changed: False)
    with pytest.raises(DomainError, match="recovery failed"):
        driver.change("gswb", "new.example.invalid")
    assert json.loads(driver.pending.read_text())["status"] == "recovery-required"
    with pytest.raises(DomainError, match="recovery failed"):
        driver.change("gswb", "other.example.invalid")


def test_domain_change_serializes_with_app_lifecycle(tmp_path):
    from schulplattform.storage import exclusive
    mutations = []
    lock = tmp_path / "shared-operation.lock"
    driver = Domains(tmp_path / "domains", {"gswb": "old.example.invalid"}, "admin.example.invalid",
                     lambda old, new: True, lambda domains: mutations.append(domains),
                     lambda domains, changed: True, operation_lock=lock)
    with exclusive(lock):
        with pytest.raises(BlockingIOError):
            driver.change("gswb", "new.example.invalid")
    assert not mutations


def test_only_the_moved_app_is_verified_and_a_stuck_recovery_heals(tmp_path):
    # Real server: 'domain-change zackboing' failed and so did its rollback, because verification
    # required every app to be active while tafel still pointed to its old server.
    live = {"zackboing": "quiz.example.invalid", "grundschultafel": "tafel.example.invalid"}
    driver = Domains(tmp_path, dict(live), "admin.example.invalid", lambda old, new: True,
                     lambda domains: live.update(domains), lambda domains, changed: changed == {"zackboing"})
    old = json.loads(driver.path.read_text())
    candidate = {"generation": "x", "domains": old["domains"] | {"zackboing": "zackboing.example.invalid"}}
    driver.pending.write_text(json.dumps({"old": old, "candidate": candidate, "status": "recovery-required"}))
    driver.change("zackboing", "zackboing.example.invalid")      # heals the stuck rollback, then moves
    assert live["zackboing"] == "zackboing.example.invalid"
    assert json.loads(driver.pending.read_text())["status"] == "committed"
