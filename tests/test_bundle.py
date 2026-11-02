import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from schulplattform.bundle import BundleError, safe_file, verify_bundle


@pytest.fixture
def signed(tmp_path):
    key = Ed25519PrivateKey.generate()
    public = tmp_path / "trusted.pem"
    public.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    root = tmp_path / "bundle"
    (root / "apps").mkdir(parents=True)
    (root / "evidence").mkdir()
    evidence = b"synthetic bundle unit-test artifact, not release acceptance"
    digest = hashlib.sha256(evidence).hexdigest()
    (root / "evidence" / digest).write_bytes(evidence)
    manifest = dict(schemaVersion=1, id="gswb", sourceCommit="a"*40,
        image="registry.example.invalid/gswb:1.0@sha256:"+"b"*64, port=8000,
        database=dict(engine="sqlite", name="gswb", account="gswb"),
        persistence=[dict(id="data", mount="/data", owner="10001:10001", backup=True)],
        domainEnvironment=[], buildTimePublicUrl=False,
        health=dict(live="/health/live", ready="/health/ready"),
        resources=dict(memoryMiB=512, cpus=1, workers=2, exportSlotsPerProcess=0),
        acceptance={name:digest for name in ["amd64Build","standalone","negativeAccess","restore",
                                           "domainRollback","licenses","sbom"]})
    (root / "apps/gswb.json").write_text(json.dumps(manifest))
    inventory = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                 for name in ["apps/gswb.json", "evidence/"+digest]}
    metadata = dict(schemaVersion=1, release="0.1.0-test", architecture="amd64", files=inventory)
    def sign(meta):
        raw = json.dumps(meta).encode()
        (root / "bundle.json").write_bytes(raw)
        (root / "bundle.sig").write_bytes(key.sign(raw))
    sign(metadata)
    return root, public, metadata, sign


def test_verified_bytes_and_external_key(signed, tmp_path):
    root, public, metadata, sign = signed
    verified = verify_bundle(root, public)
    assert verified.release == "0.1.0-test"
    assert verified.manifests[0]["id"] == "gswb"
    wrong = Ed25519PrivateKey.generate()
    public.write_bytes(wrong.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    with pytest.raises(BundleError, match="signature"):
        verify_bundle(root, public)


def test_changed_file_rejected(signed):
    root, public, metadata, sign = signed
    (root / "apps/gswb.json").write_text("{}")
    with pytest.raises(BundleError, match="checksum"):
        verify_bundle(root, public)


def test_unsigned_acceptance_artifact_rejected(signed):
    root, public, metadata, sign = signed
    metadata["files"] = {k:v for k,v in metadata["files"].items() if k.startswith("apps/")}
    sign(metadata)
    with pytest.raises(BundleError, match="Unsigned"):
        verify_bundle(root, public)


@pytest.mark.parametrize("name", ["../escape", "/etc/passwd", "apps/../secret", "apps//gswb.json", "apps\\gswb.json"])
def test_invalid_paths(signed, name):
    root, public, metadata, sign = signed
    with pytest.raises(BundleError):
        safe_file(root, name)


def test_symlink_artifact_rejected(signed):
    root, public, metadata, sign = signed
    original = root / "apps/gswb.json"
    data = original.read_bytes()
    original.unlink()
    (root / "actual").write_bytes(data)
    original.symlink_to(root / "actual")
    with pytest.raises(BundleError, match="symlink"):
        verify_bundle(root, public)


def test_installer_plan_checks_signature(signed, capsys):
    from schulplattform.installer import main
    root, public, metadata, sign = signed
    assert main(["plan", "--bundle", str(root), "--trusted-key", str(public)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "signature-and-manifests-verified"
    assert output["deployable"] is False
    (root / "bundle.sig").write_bytes(b"invalid")
    with pytest.raises(SystemExit) as failure:
        main(["plan", "--bundle", str(root), "--trusted-key", str(public)])
    assert failure.value.code == 1


def test_installer_never_trusts_a_key_from_bundle_implicitly(signed):
    from schulplattform.installer import main
    root, public, metadata, sign = signed
    with pytest.raises(SystemExit) as failure:
        main(["plan", "--bundle", str(root)])
    assert failure.value.code == 2
