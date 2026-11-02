import json
import multiprocessing
from pathlib import Path

import pytest

from schulplattform.state import Installation, StateError, Step
from schulplattform.storage import exclusive
from schulplattform.secrets import SecretStore, Bootstrap


def test_second_run_is_true_noop_and_preserves_id(tmp_path):
    calls = []
    def apply(identity):
        calls.append(identity)
        (tmp_path / "provisioned").write_text(identity)
    step = Step("provision", apply, lambda identity: (tmp_path / "provisioned").read_text() == identity)
    machine = Installation(tmp_path / "state")
    first = machine.run({"release": "synthetic-1"}, [step])
    before = machine.path.stat().st_mtime_ns
    assert machine.run({"release": "synthetic-1"}, [step]) == first
    assert machine.path.stat().st_mtime_ns == before
    assert calls == [first["id"]]
    with pytest.raises(StateError, match="plan changed"):
        machine.run({"release": "synthetic-2"}, [step])


def test_interrupt_after_side_effect_resumes_without_repeating(tmp_path):
    calls = []
    ready = set()
    def provision(identity):
        calls.append(identity)
        ready.add(identity)
        raise KeyboardInterrupt()
    machine = Installation(tmp_path / "state")
    step = Step("provision", provision, lambda identity: identity in ready)
    with pytest.raises(KeyboardInterrupt):
        machine.run({}, [step])
    result = machine.run({}, [step])
    assert result["status"] == "completed"
    assert calls == [result["id"]]


def test_failed_verification_blocks_next_step_and_redacts_errors(tmp_path):
    calls = []
    steps = [Step("provision", lambda identity: None, lambda identity: False),
             Step("verify", lambda identity: calls.append(identity), lambda identity: True)]
    machine = Installation(tmp_path)
    with pytest.raises(StateError):
        machine.run({}, steps)
    assert not calls
    assert json.loads(machine.path.read_text())["status"] == "failed"


def test_lock_and_corrupt_state_fail_closed(tmp_path):
    machine = Installation(tmp_path)
    steps = [Step("preflight", lambda identity: None, lambda identity: True)]
    with exclusive(tmp_path / "installation.lock"):
        with pytest.raises(BlockingIOError):
            machine.run({}, steps)
    machine.path.write_text("{broken")
    with pytest.raises(StateError):
        machine.run({}, steps)


def test_secret_reused_private_and_no_symlink_following(tmp_path):
    store = SecretStore(tmp_path / "secrets")
    first = store.get_or_create("session")
    assert store.get_or_create("session") == first
    assert store.path("session").stat().st_mode & 0o777 == 0o600
    store.path("linked").symlink_to(store.path("session"))
    with pytest.raises(ValueError):
        store.get_or_create("linked")
    with pytest.raises(ValueError):
        store.get_or_create("../escape")


def test_bootstrap_expiry_single_use_and_hash_only(tmp_path):
    now = [1000]
    bootstrap = Bootstrap(tmp_path, clock=lambda: now[0])
    token = bootstrap.issue(ttl=10)
    assert token not in (tmp_path / "bootstrap.json").read_text()
    assert not bootstrap.consume("wrong")
    assert bootstrap.consume(token)
    assert not bootstrap.consume(token)
    with pytest.raises(ValueError):
        bootstrap.issue()
    second = Bootstrap(tmp_path / "second", clock=lambda: now[0])
    expired = second.issue(ttl=1)
    now[0] += 2
    assert not second.consume(expired)


def _crash_after_effect(directory):
    import os
    root = Path(directory)
    def action(identity):
        (root / "effect").write_text(identity)
        os._exit(17)
    Installation(root / "state").run({"release": "crash-fixture"}, [
        Step("provision", action, lambda identity: (root / "effect").exists())
    ])


def test_actual_process_death_is_recoverable(tmp_path):
    process = multiprocessing.get_context("fork").Process(target=_crash_after_effect, args=(str(tmp_path),))
    process.start()
    process.join(timeout=5)
    assert process.exitcode == 17
    def forbidden_repeat(identity):
        raise AssertionError("Side effect must not be repeated")
    result = Installation(tmp_path / "state").run({"release": "crash-fixture"}, [
        Step("provision", forbidden_repeat, lambda identity: (tmp_path / "effect").read_text() == identity)
    ])
    assert result["status"] == "completed"
