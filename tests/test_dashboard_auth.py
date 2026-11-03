import base64
import sqlite3

import pytest
from schulplattform.dashboard_auth import AdminStore, otp

SEED = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize("timestamp,expected", [(59,"94287082"), (1111111109,"07081804"),
    (1111111111,"14050471"), (1234567890,"89005924"), (2000000000,"69279037"), (20000000000,"65353130")])
def test_rfc6238_sha1_vectors(timestamp, expected):
    assert otp(SEED, timestamp // 30, 8) == expected


def test_password_totp_replay_expiry_and_revocation(tmp_path):
    now = [1234567890]
    store = AdminStore(tmp_path / "admin", clock=lambda: now[0], initialize=True)
    identity = store.create_admin("synthetic.operator", "synthetic-password-123", SEED)
    code = otp(SEED, now[0] // 30)
    assert store.login("synthetic.operator", "wrong", code) is None
    assert store.login("synthetic.operator", "synthetic-password-123", "000000") is None
    token = store.login("synthetic.operator", "synthetic-password-123", code)
    assert store.authenticate(token)["id"] == identity
    assert store.login("synthetic.operator", "synthetic-password-123", code) is None
    assert token.encode() not in store.path.read_bytes()
    assert SEED.encode() not in store.path.read_bytes()
    now[0] += 3601
    assert store.authenticate(token) is None
    token = store.login("synthetic.operator", "synthetic-password-123", otp(SEED, now[0] // 30))
    assert token
    store.logout(token)
    assert store.authenticate(token) is None


def test_rate_limit_persists_and_unknown_buckets_are_bounded(tmp_path):
    now = [1234567890]
    store = AdminStore(tmp_path / "admin", clock=lambda: now[0], initialize=True)
    store.create_admin("synthetic.operator", "synthetic-password-123", SEED)
    for _ in range(5):
        assert store.login("synthetic.operator", "wrong", "000000") is None
    assert store.login("synthetic.operator", "synthetic-password-123", otp(SEED, now[0] // 30)) is None
    for number in range(15):
        assert store.login("unknown" + str(number), "wrong", "000000") is None
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 2
    restarted = AdminStore(tmp_path / "admin", clock=lambda: now[0])
    assert restarted.login("synthetic.operator", "synthetic-password-123", otp(SEED, now[0] // 30)) is None
    now[0] += 901
    assert restarted.login("synthetic.operator", "synthetic-password-123", otp(SEED, now[0] // 30))


def test_existing_database_never_gets_replacement_keys(tmp_path):
    store = AdminStore(tmp_path / "admin", initialize=True)
    store.secrets.path("totp-wrapping-key").unlink()
    with pytest.raises(ValueError, match="recovery"):
        AdminStore(tmp_path / "admin")
    assert not store.secrets.path("totp-wrapping-key").exists()


@pytest.mark.parametrize("app_id", ["schulhelfer", "losverkauf", "grundschultafel"])
def test_optional_app_access_is_explicit_and_operations_are_audited(tmp_path, app_id):
    store = AdminStore(tmp_path / "admin", initialize=True)
    identity = store.create_admin("synthetic.operator", "synthetic-password-123", SEED)
    assert app_id not in store.access(identity)
    store.confirm_access(identity, app_id)
    assert store.access(identity) == {app_id}
    store.audit(identity, "stop", app_id, "completed")
    with store.connect() as db:
        assert tuple(db.execute("SELECT actor,action,app_id,outcome FROM audit").fetchone()) == (
            identity, "stop", app_id, "completed")
