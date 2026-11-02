"""Verify a release against an independently provisioned Ed25519 trust key."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .release import validate_release


class BundleError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BundleError("Duplicate JSON key")
        result[key] = value
    return result


def safe_file(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise BundleError("Invalid bundle path")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in ("", ".", "..") for part in relative.split("/")):
        raise BundleError("Invalid bundle path")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise BundleError("Bundle symlinks are forbidden")
    if not current.is_file():
        raise BundleError("Missing bundle file")
    if current.stat().st_size > 32 * 1024 * 1024:
        raise BundleError("Bundle metadata artifact is too large")
    return current.read_bytes()


@dataclass(frozen=True)
class VerifiedBundle:
    release: str
    digest: str
    manifests: tuple
    files: dict


def verify_bundle(directory, trusted_key):
    root = Path(directory).resolve(strict=True)
    raw = safe_file(root, "bundle.json")
    signature = safe_file(root, "bundle.sig")
    key = load_pem_public_key(Path(trusted_key).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise BundleError("Only Ed25519 release keys are supported")
    try:
        key.verify(signature, raw)
    except InvalidSignature:
        raise BundleError("Release signature verification failed") from None
    metadata = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(metadata, dict) or
            set(metadata) != {"schemaVersion", "release", "architecture", "files"} or
            metadata["schemaVersion"] != 1 or metadata["architecture"] != "amd64" or
            not isinstance(metadata["release"], str) or
            not re.fullmatch("[0-9][a-zA-Z0-9_.-]{0,63}", metadata["release"]) or
            not isinstance(metadata["files"], dict) or not metadata["files"] or
            len(metadata["files"]) > 2000):
        raise BundleError("Invalid release metadata")
    files = {}
    for relative, expected in metadata["files"].items():
        if relative in ("bundle.json", "bundle.sig"):
            raise BundleError("Bundle cannot sign itself as an artifact")
        if not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected):
            raise BundleError("Invalid artifact digest")
        data = safe_file(root, relative)
        if hashlib.sha256(data).hexdigest() != expected:
            raise BundleError("Release artifact checksum mismatch")
        files[relative] = data
    manifests = []
    for relative, data in files.items():
        if relative.startswith("apps/") and relative.endswith(".json"):
            manifest = json.loads(data, object_pairs_hook=unique_object)
            if not isinstance(manifest, dict) or not isinstance(manifest.get("acceptance"), dict):
                raise BundleError("Invalid application manifest")
            # Evidence must belong to this signed inventory, not merely exist beside it.
            for digest in manifest.get("acceptance", {}).values():
                if not isinstance(digest, str) or "evidence/" + digest not in files:
                    raise BundleError("Unsigned acceptance evidence")
            manifests.append(manifest)
    validate_release(manifests, root / "evidence")
    # Use verified byte snapshots in subsequent code, not mutable bundle files.
    return VerifiedBundle(metadata["release"], hashlib.sha256(raw).hexdigest(),
                          tuple(manifests), files)
