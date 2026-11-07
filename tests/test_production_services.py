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


def test_backup_waits_until_a_paused_app_is_healthy_again(monkeypatch):
    # Real server: right after 'backup --app sl-journal' the import refused with "nicht gesund"
    # because the health check had failed while the app was paused for the file snapshot.
    from schulplattform import backups
    answers = iter([False, False, True])
    service = backups.BackupService.__new__(backups.BackupService)
    service.stack = type("S", (), {"healthy": lambda self, app: next(answers)})()
    monkeypatch.setattr(backups.time, "sleep", lambda seconds: None)
    assert service._await_health("sl-journal") is True
    service.stack = type("S", (), {"healthy": lambda self, app: False})()
    clock = iter(range(0, 1000, 50))
    monkeypatch.setattr(backups.time, "monotonic", lambda: next(clock))
    assert service._await_health("sl-journal", seconds=150) is False


def test_restore_accepts_the_printed_archive_name(tmp_path):
    from types import SimpleNamespace
    import pytest
    from schulplattform.backups import resolve_archive
    from schulplattform.state import StateError
    folder = tmp_path / "backups" / "bildergalerie"
    folder.mkdir(parents=True)
    archive = folder / "bildergalerie-20261107T161626Z.spbk"
    archive.write_bytes(b"x")
    service = SimpleNamespace(layout=SimpleNamespace(backups=tmp_path / "backups"))
    assert resolve_archive(service, "bildergalerie", "bildergalerie-20261107T161626Z.spbk") == archive
    assert resolve_archive(service, "bildergalerie", str(archive)) == archive
    with pytest.raises(StateError, match="nicht gefunden"):
        resolve_archive(service, "bildergalerie", "fehlt.spbk")
    with pytest.raises(StateError, match="nicht gefunden"):
        resolve_archive(service, "bildergalerie", "../bildergalerie/fehlt.spbk")


def _backup_service(tmp_path):
    from types import SimpleNamespace
    from schulplattform.backups import BackupService
    service = BackupService.__new__(BackupService)
    service.layout = SimpleNamespace(backups=tmp_path / "backups")
    service.status_path = service.layout.backups / "status.json"
    service.platform = SimpleNamespace(config={"backup": {"retention_days": 14}})
    service.key = lambda: b"k" * 32
    (service.layout.backups / "bildergalerie").mkdir(parents=True)
    return service


def _archive(service, name, header_extra=None, files=None):
    import io, json, tarfile
    from schulplattform.backups import encrypt_stream
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for path, data in (files or {"backup.json": b"{}"}).items():
            info = tarfile.TarInfo(path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    buffer.seek(0)
    path = service.layout.backups / "bildergalerie" / name
    with path.open("wb") as out:
        encrypt_stream(buffer, out, service.key(), {"app": "bildergalerie", **(header_extra or {})})
    return path


def _stamp(days_ago):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y%m%dT%H%M%SZ")


def test_incremental_plan_against_the_last_full_copy(tmp_path):
    import json
    service = _backup_service(tmp_path)
    base = _archive(service, f"bildergalerie-{_stamp(3)}.spbk")
    listing = {f"uploads/{n}.png": [1000, n] for n in range(10)}
    service._write_manifest(base, "media", listing)
    service.status_path.write_text(json.dumps({"bildergalerie": {"volumeBases": {"media": base.name}}}))
    now = _stamp(0)
    current = dict(listing)
    current["uploads/new.png"] = [500, 1]                     # added
    current["uploads/3.png"] = [1000, 99]                     # changed (mtime)
    del current["uploads/7.png"]                              # deleted
    plan = service._incremental_plan("bildergalerie", "media", current, now)
    assert plan == {"base": base.name, "changed": ["uploads/3.png", "uploads/new.png"], "deleted": ["uploads/7.png"]}
    # more than half of the bytes changed -> full copy
    changed = {p: [m[0], m[1] + 1] for p, m in listing.items()}
    assert service._incremental_plan("bildergalerie", "media", changed, now) is None
    # full copy older than FULL_COPY_DAYS -> full copy
    old = _archive(service, f"bildergalerie-{_stamp(30)}.spbk")
    service._write_manifest(old, "media", listing)
    service.status_path.write_text(json.dumps({"bildergalerie": {"volumeBases": {"media": old.name}}}))
    assert service._incremental_plan("bildergalerie", "media", listing, now) is None
    # missing or foreign manifest -> full copy
    service.status_path.write_text(json.dumps({"bildergalerie": {"volumeBases": {"media": base.name}}}))
    base.with_name(f"{base.stem}.media.manifest").write_bytes(b"kaputt")
    assert service._incremental_plan("bildergalerie", "media", listing, now) is None


def test_rotation_keeps_full_copies_that_kept_archives_reference(tmp_path):
    service = _backup_service(tmp_path)
    folder = service.layout.backups / "bildergalerie"
    base = _archive(service, f"bildergalerie-{_stamp(25)}.spbk")
    service._write_manifest(base, "media", {})
    stale = _archive(service, f"bildergalerie-{_stamp(20)}.spbk", {"bases": [base.name]})
    recent = _archive(service, f"bildergalerie-{_stamp(1)}.spbk", {"bases": [base.name]})
    other_full = _archive(service, f"bildergalerie-{_stamp(40)}.spbk")
    service._write_manifest(other_full, "media", {})
    service.rotate("bildergalerie")
    names = sorted(p.name for p in folder.iterdir())
    assert names == sorted([base.name, f"{base.stem}.media.manifest", recent.name])
    assert not stale.exists() and not other_full.exists()


def test_streaming_unpack_extracts_and_rejects_tampering(tmp_path):
    import pytest
    from schulplattform.state import StateError
    service = _backup_service(tmp_path)
    big = bytes(range(256)) * 40000                            # > one 4 MiB chunk
    archive = _archive(service, f"bildergalerie-{_stamp(0)}.spbk",
                       files={"backup.json": b"{}", "volumes/media/files.tar": big})
    header = service.unpack(archive, tmp_path / "out")
    assert header["app"] == "bildergalerie"
    assert (tmp_path / "out/volumes/media/files.tar").read_bytes() == big
    data = bytearray(archive.read_bytes())
    data[-100] ^= 1                                            # flip a bit in the last chunk
    archive.write_bytes(bytes(data))
    with pytest.raises(StateError, match="authentication"):
        service.unpack(archive, tmp_path / "out2")
    assert not (tmp_path / "out2").exists()


def test_unpack_bases_refuses_missing_and_foreign_references(tmp_path):
    import json
    import pytest
    from schulplattform.state import StateError
    service = _backup_service(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    for ref, message in (("bildergalerie-20990101T000000Z.spbk", "Vollkopie"), ("../x.spbk", "Invalid"),
                         ("schulkasse-20260101T000000Z.spbk", "Invalid")):
        (work / "backup.json").write_text(json.dumps({"volumeRefs": {"media": {"base": ref, "deleted": [], "changed": 0}}}))
        with pytest.raises(StateError, match=message):
            service.unpack_bases("bildergalerie", work)
    incremental = _archive(service, f"bildergalerie-{_stamp(2)}.spbk",
                           files={"backup.json": json.dumps({"app": "bildergalerie", "volumeRefs": {"m": {}}}).encode()})
    (work / "backup.json").write_text(json.dumps({"volumeRefs": {"media": {"base": incremental.name, "deleted": [], "changed": 0}}}))
    with pytest.raises(StateError, match="no full copy"):
        service.unpack_bases("bildergalerie", work)
