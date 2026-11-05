"""DNS evaluation, certificate parsing, archive encryption and extended control protocol."""
from datetime import datetime, timedelta, timezone
import io
import struct

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from schulplattform import certs, dnscheck
from schulplattform.backups import MAGIC, decrypt_stream, encrypt_stream
from schulplattform.deployment import Gate, PLATFORM, signed_request, valid_params
from schulplattform.state import StateError

IP = "80.67.169.12"


def fixed(a=(), aaaa=()):
    return lambda host: {"A": sorted(a), "AAAA": sorted(aaaa)}


@pytest.mark.parametrize("resolve,ipv6,verdict", [
    (fixed([IP]), None, "ok"),
    (fixed(), None, "pending"),
    (fixed(["198.51.100.7"]), None, "wrong"),
    (fixed([IP], ["2001:db8::1"]), None, "wrong"),               # stray AAAA breaks LE validation
    (fixed([IP], ["2001:db8::1"]), "2001:db8::1", "ok"),
    (fixed([IP], ["2001:db8::2"]), "2001:db8::1", "wrong"),
    (fixed([IP, "198.51.100.7"]), None, "wrong"),
])
def test_dns_evaluation(resolve, ipv6, verdict):
    assert dnscheck.evaluate("wissen.schule.example", IP, ipv6, resolve=resolve)["dns"] == verdict


def test_resolver_disagreement_and_failure():
    ask_other = lambda resolver, host, rtype: ["198.51.100.7"] if rtype == "A" else []
    result = dnscheck.evaluate("a.schule.example", IP, None, ["9.9.9.9"], resolve=fixed([IP]), ask=ask_other)
    assert result["dns"] == "pending" and "unterschiedliche" in result["reason"]

    def broken(resolver, host, rtype):
        raise OSError("timeout")
    assert dnscheck.evaluate("a.schule.example", IP, None, ["9.9.9.9"], resolve=fixed([IP]), ask=broken)["dns"] == "error"


def test_dns_wire_encoding_rejects_bad_labels():
    assert dnscheck._encode_name("a.example") == b"\x01a\x07example\x00"
    with pytest.raises(ValueError):
        dnscheck._encode_name("a..example")


def make_cert(tmp_path, host, days=60, issuer_dir="acme-v02.api.letsencrypt.org-directory", san=None):
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
               .issuer_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Let's Encrypt")]))
               .public_key(key.public_key()).serial_number(1).not_valid_before(now - timedelta(days=1))
               .not_valid_after(now + timedelta(days=days))
               .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in (san or [host])]), False))
    certificate = builder.sign(key, hashes.SHA256())
    path = tmp_path / "caddy/certificates" / issuer_dir / host / f"{host}.crt"
    path.parent.mkdir(parents=True)
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def test_certificate_state_from_caddy_storage(tmp_path):
    assert certs.find(tmp_path, "wissen.schule.example") is None
    make_cert(tmp_path, "wissen.schule.example", days=60)
    info = certs.find(tmp_path, "wissen.schule.example")
    assert info["valid"] and info["coversHostname"] and 58 <= info["daysLeft"] <= 60 and not info["staging"]
    make_cert(tmp_path, "rad.schule.example", issuer_dir="acme-staging-v02.api.letsencrypt.org-directory",
              san=["other.schule.example"])
    info = certs.find(tmp_path, "rad.schule.example")
    assert info["staging"] and not info["valid"]


def test_archive_roundtrip_and_tamper_detection():
    key = b"k" * 32
    data = b"x" * (5 * 1024 * 1024 + 17)
    sealed = io.BytesIO()
    encrypt_stream(io.BytesIO(data), sealed, key, {"app": "gswb"})
    plain = io.BytesIO()
    assert decrypt_stream(io.BytesIO(sealed.getvalue()), plain, key)["app"] == "gswb"
    assert plain.getvalue() == data
    with pytest.raises(StateError, match="authentication"):
        decrypt_stream(io.BytesIO(sealed.getvalue()), io.BytesIO(), b"w" * 32)
    tampered = bytearray(sealed.getvalue())
    tampered[-5] ^= 1
    with pytest.raises(StateError):
        decrypt_stream(io.BytesIO(bytes(tampered)), io.BytesIO(), key)
    truncated = sealed.getvalue()[:-100]
    with pytest.raises(StateError):
        decrypt_stream(io.BytesIO(truncated), io.BytesIO(), key)
    assert sealed.getvalue().startswith(MAGIC)


class Recorder:
    def __init__(self):
        self.calls = []

    def execute(self, action, app, params=None):
        self.calls.append((action, app, params))
        return {"ok": True}


def test_extended_actions_require_exact_parameters(tmp_path):
    key = b"synthetic-deployment-key-1234567890"
    engine = Recorder()
    gate = Gate(tmp_path / "gate.db", key, engine)
    good = signed_request(key, "domain-change", "schulwissen", params={"hostname": "wissen.schule.example"})
    assert gate.dispatch(good)["ok"]
    assert engine.calls[-1] == ("domain-change", "schulwissen", {"hostname": "wissen.schule.example"})
    for action, app, params in [
        ("domain-change", "schulwissen", {"hostname": "wissen.schule.example; rm -rf /"}),
        ("domain-change", "schulwissen", {"hostname": "wissen.schule.example", "path": "/etc"}),
        ("domain-change", PLATFORM, {"hostname": "a.example"}),
        ("smtp-test", PLATFORM, {"recipient": "a@b.example\nBcc: x@y.example"}),
        ("smtp-update", PLATFORM, {"host": "smtp.example", "port": 0, "security": "tls", "username": "",
                                   "sender": "a@b.example", "sender_name": "x"}),
        ("overview", "gswb", {}),
        ("start", "gswb", {"argv": ["sh"]}),
    ]:
        assert not valid_params(action, app, params)
        with pytest.raises(ValueError):
            signed_request(key, action, app, params=params)
    forged = signed_request(key, "maintenance", "gswb", params={"enabled": True})
    forged["params"] = {"enabled": False}
    assert gate.dispatch(forged)["error"] == "unauthorized"
    smuggled = signed_request(key, "overview", PLATFORM, params={})
    smuggled["params"] = {"x": 1}
    assert gate.dispatch(smuggled)["error"] == "invalid-request"


def test_staging_certificate_does_not_count_after_switching_to_production(tmp_path):
    # Real server: after acme_environment staging -> production only staging certificates existed,
    # the status showed them as valid and the apps as "fehler".
    from schulplattform.proxy import issuer_key
    make_cert(tmp_path, "quiz.schule.example", issuer_dir=issuer_key("staging"))
    assert certs.find(tmp_path, "quiz.schule.example", issuer_key("staging"))["valid"]
    assert certs.find(tmp_path, "quiz.schule.example", issuer_key("production")) is None
    make_cert(tmp_path, "quiz.schule.example", issuer_dir=issuer_key("production"))
    assert not certs.find(tmp_path, "quiz.schule.example", issuer_key("production"))["staging"]
    assert issuer_key("custom") is None


def test_backup_sqlite_copy_leaves_encrypted_databases_to_the_file_snapshot(tmp_path):
    # Real server: sl-journal's journal.db is SQLCipher; the SQLite copy failed on it, so no
    # sl-journal backup was ever written and the import refused at its pre-import backup.
    import json
    import sqlite3
    import subprocess
    import sys
    from schulplattform.backups import SQLITE_SCRIPT
    src, out = tmp_path / "src", tmp_path / "out"
    (src / "instance").mkdir(parents=True)
    out.mkdir()
    (src / "instance/journal.db").write_bytes(b"\x8f\x13" + bytes(range(200)) * 20)   # encrypted
    plain = sqlite3.connect(src / "app.db")
    plain.executescript("CREATE TABLE t(x); INSERT INTO t VALUES(1);")
    plain.close()
    result = subprocess.run([sys.executable, "-c", SQLITE_SCRIPT, str(src), str(out)],
                            capture_output=True, text=True, check=True)
    assert [c["file"] for c in json.loads(result.stdout)] == ["app.db"]
    assert not (out / "instance/journal.db").exists()
