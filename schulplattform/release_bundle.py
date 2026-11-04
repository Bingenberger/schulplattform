"""Verified release access for the production stack.

A release bundle (see scripts/make_release.py) contains per-app manifests with
image references pinned by version and digest, the apps' unchanged standalone
compose files from the tagged commit, platform image references and
content-addressed acceptance records. Everything is covered by one Ed25519
signature checked against an independently provisioned trust key.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

from .bundle import BundleError, unique_object, verify_bundle
from .catalogue import APP_IDS, INFRASTRUCTURE, PLATFORM_IMAGES, RELEASE_IMAGES


def key_fingerprint(path):
    key = load_pem_public_key(Path(path).read_bytes())
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return "SHA256:" + hashlib.sha256(raw).hexdigest()


class Release:
    def __init__(self, directory, trusted_key):
        self.directory = Path(directory)
        self.verified = verify_bundle(directory, trusted_key)
        self.version = self.verified.release
        self.digest = self.verified.digest
        self.manifests = {m["id"]: m for m in self.verified.manifests}
        try:
            platform = json.loads(self.verified.files["platform.json"], object_pairs_hook=unique_object)
        except KeyError:
            raise BundleError("Release lacks platform.json") from None
        if set(platform) != {"schemaVersion", "images", "sourceCommit"} or platform["schemaVersion"] != 1:
            raise BundleError("Invalid platform.json")
        self.platform = platform
        self.images = {}
        for app_id, manifest in self.manifests.items():
            expected = [name for name, _ in RELEASE_IMAGES[app_id]]
            names = [expected[0], *sorted(manifest.get("auxiliaryImages", {}))]
            if sorted(names) != sorted(expected):
                raise BundleError(f"Release images for {app_id} do not match the catalogue")
            self.images[expected[0]] = manifest["image"]
            self.images.update(manifest.get("auxiliaryImages", {}))
        if set(platform["images"]) != set(PLATFORM_IMAGES):
            raise BundleError("Release lacks platform images")
        for name, reference in platform["images"].items():
            if "@sha256:" not in reference or reference.split("@")[0].endswith(":latest"):
                raise BundleError("Platform images must be pinned by version and digest")
            self.images[name] = reference

    @property
    def apps(self):
        return tuple(app for app in APP_IDS if app in self.manifests)

    def image(self, name):
        try:
            return self.images[name]
        except KeyError:
            raise BundleError(f"Release does not contain image {name}") from None

    def all_images(self, apps, mail_mode):
        images = [self.image("schulplattform-dashboard"), INFRASTRUCTURE["caddy"]]
        if mail_mode == "relay":
            images.append(self.image("schulplattform-relay"))
        elif mail_mode == "sink":
            images.append(INFRASTRUCTURE["mailpit"])
        for app_id in apps:
            if app_id not in self.manifests:
                raise BundleError(f"App {app_id} is not part of release {self.version}")
            for name, _ in RELEASE_IMAGES[app_id]:
                images.append(self.image(name))
            engine = self.manifests[app_id]["database"]["engine"]
            if engine in ("postgres16", "postgres18"):
                images.append(INFRASTRUCTURE[engine])
        return images

    def install_compose(self, app_id, target):
        """Write the app's standalone compose files exactly as signed in the release."""
        manifest = self.manifests.get(app_id)
        if not manifest:
            raise BundleError(f"App {app_id} is not part of release {self.version}")
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True, mode=0o755)
        prefix = f"compose/{app_id}/"
        for relative in manifest["compose"]:
            if not relative.startswith(prefix):
                raise BundleError("Compose file outside the app directory")
            inner = PurePosixPath(relative[len(prefix):])
            if inner.is_absolute() or ".." in inner.parts:
                raise BundleError("Invalid compose path")
            destination = target.joinpath(*inner.parts)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            if destination.is_symlink():
                raise BundleError("Symlink in compose target refused")
            data = self.verified.files[relative]
            if not destination.exists() or destination.read_bytes() != data:
                temporary = destination.with_name("." + destination.name + ".new")
                temporary.write_bytes(data)
                os.chmod(temporary, 0o755 if inner.suffix == ".sh" else 0o644)
                os.replace(temporary, destination)

    def acceptance(self):
        """{app: {item: record}} with each record's status (passed/open) and summary."""
        result = {}
        for app_id, manifest in self.manifests.items():
            result[app_id] = {}
            for item, digest in manifest["acceptance"].items():
                record = json.loads(self.verified.files["evidence/" + digest])
                result[app_id][item] = {"status": record.get("status"), "summary": record.get("summary", "")}
        return result

    def open_items(self):
        return [(app, item, record["summary"]) for app, items in self.acceptance().items()
                for item, record in items.items() if record["status"] != "passed"]

    def store(self, releases_dir):
        """Keep a verified copy of the bundle on the host (for rollback and audit)."""
        destination = Path(releases_dir) / self.version
        if destination.exists():
            existing = hashlib.sha256((destination / "bundle.json").read_bytes()).hexdigest()
            if existing != self.digest:
                raise BundleError("A different bundle with the same version is already installed")
            return destination
        temporary = Path(releases_dir) / ("." + self.version + ".new")
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True, mode=0o700)
        for name in ("bundle.json", "bundle.sig"):
            shutil.copyfile(self.directory / name, temporary / name)
        for relative, data in self.verified.files.items():
            path = temporary.joinpath(*PurePosixPath(relative).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        os.replace(temporary, destination)
        return destination
