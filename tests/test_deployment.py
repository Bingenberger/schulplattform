import copy
import json
import os
import threading

import pytest
from schulplattform.deployment import Client, Gate, Server, signed_request


class Engine:
    def __init__(self):
        self.calls = []
    def execute(self, action, app):
        self.calls.append((action, app))
        return {"app": app, "running": action != "stop"}


def test_mac_expiry_replay_and_fixed_actions(tmp_path):
    now = [12345]
    key, engine = b"synthetic-deployment-key-1234567890", Engine()
    gate = Gate(tmp_path / "gate.db", key, engine, clock=lambda: now[0])
    request = signed_request(key, "start", "gswb", clock=lambda: now[0])
    wrong = copy.deepcopy(request)
    wrong["signature"] = "0"*64
    assert gate.dispatch(wrong)["error"] == "unauthorized"
    assert gate.dispatch(request)["ok"]
    assert gate.dispatch(request)["error"] == "replay"
    assert engine.calls == [("start", "gswb")]
    request = signed_request(key, "stop", "gswb", clock=lambda: now[0])
    now[0] += 61
    assert gate.dispatch(request)["error"] == "invalid-request"
    injection = signed_request(key, "stop", "gswb", clock=lambda: now[0])
    injection["argv"] = ["sh", "-c", "untrusted"]
    assert gate.dispatch(injection)["error"] == "invalid-request"
    for action, app in [("shell", "gswb"), ("stop", "../other")]:
        with pytest.raises(ValueError):
            signed_request(key, action, app)


def test_real_unix_socket_roundtrip_and_persistent_replay(tmp_path):
    key, engine = b"synthetic-deployment-key-1234567890", Engine()
    gate = Gate(tmp_path / "gate.db", key, engine)
    path = tmp_path / "deployment.sock"
    with Server(path, gate, os.getuid()) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            import socket
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as malformed:
                malformed.connect(str(path))
                malformed.sendall(b"{\"nonce\":NaN}\n")
                assert json.loads(malformed.recv(4096))["error"] == "invalid-request"
            response = Client(path, key).execute("status", "schulwissen")
            assert response["app"] == "schulwissen"
            with pytest.raises(ValueError):
                Client(path, b"wrong-key-123456789012345678901234").execute("start", "gswb")
            request = signed_request(key, "stop", "gswb")
            assert gate.dispatch(request)["ok"]
            restarted = Gate(tmp_path / "gate.db", key, engine)
            assert restarted.dispatch(request)["error"] == "replay"
        finally:
            server.shutdown()
            thread.join()
    assert not path.exists()


def test_engine_errors_do_not_expose_exception_or_credentials(tmp_path):
    class Broken:
        def execute(self, action, app):
            raise RuntimeError("synthetic-sensitive-credential")
    key = b"synthetic-deployment-key-1234567890"
    response = Gate(tmp_path / "gate.db", key, Broken()).dispatch(signed_request(key, "start", "gswb"))
    assert response == {"ok": False, "error": "operation-failed"}


def test_unix_peer_uid_is_required_even_with_valid_mac(tmp_path):
    key, engine = b"synthetic-deployment-key-1234567890", Engine()
    gate = Gate(tmp_path / "gate.db", key, engine)
    path = tmp_path / "peer.sock"
    with Server(path, gate, os.getuid() + 1) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with pytest.raises(ValueError):
                Client(path, key).execute("start", "gswb")
            assert not engine.calls
        finally:
            server.shutdown()
            thread.join()


def test_busy_workload_is_reported_without_private_exception_data(tmp_path):
    from schulplattform.deployment import DeploymentBusy
    class Busy:
        def execute(self, action, app):
            raise DeploymentBusy("synthetic-private-detail")
    key = b"synthetic-deployment-key-1234567890"
    gate = Gate(tmp_path / "gate.db", key, Busy())
    response = gate.dispatch(signed_request(key, "stop", "zackboing"))
    assert response == {"ok": False, "error": "busy"}
