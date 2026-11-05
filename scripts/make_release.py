#!/usr/bin/env python3
"""Assemble and sign a release bundle from published GHCR images and tagged app commits.

usage: make_release.py --version 0.1.0 --signing-key ~/.config/schulplattform/release-signing-key.pem \
                       --out releases/0.1.0

Checks per app: the tag exists locally and on GitHub with the same commit; every
published image resolves to a digest, is linux/amd64, carries the tag commit as
org.opencontainers.image.revision and has SBOM and provenance attestations; the
release commit differs from the separately tested implementation commit only by
the managed release workflow. Acceptance records state "passed" only where an
evidence artifact exists; everything else is recorded as "open".
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cryptography.hazmat.primitives.serialization import load_pem_private_key  # noqa: E402
from schulplattform import registry  # noqa: E402
from schulplattform.catalogue import APPS, APP_IDS, PLATFORM_IMAGES, REGISTRY, RELEASE_IMAGES  # noqa: E402
from schulplattform.release import validate_manifest  # noqa: E402

EVIDENCE = ROOT / "docs/implementation/evidence"
WORKFLOW = ".github/workflows/release-image.yml"
SBOM = "https://spdx.dev/Document"
PROVENANCE = "https://slsa.dev/provenance/v1"

# Per-app operating facts (from the standalone compose files and app documentation).
FACTS = {
    "gswb": dict(database=("sqlite", "gswb", "gswb"), persistence=[("dictionary", "/app/data"),
                 ("images", "/app/static/images"), ("audio", "/app/static/audio"), ("uploads", "/app/static/uploads")],
                 domain=[], memory=512, cpus=1.0, workers=1, slots=0, live="/health/live"),
    "schulwissen": dict(database=("postgres16", "schulwissen", "schulwissen"),
                        persistence=[("pgdaten", "/var/lib/postgresql/data", "70:70"), ("medien", "/medien")],
                        domain=["SW_ALLOWED_HOSTS", "SW_OEFFENTLICHE_URL"], memory=768, cpus=1.0, workers=2, slots=1,
                        live="/health/live"),
    "zackboing": dict(database=("sqlite", "zackboing", "zackboing"), persistence=[("data", "/data")],
                      domain=["ZACKBOING_PUBLIC_URL"], memory=384, cpus=1.0, workers=1, slots=0, live="/health/live"),
    "schulhelfer": dict(database=("sqlite", "schulhelfer", "schulhelfer"), persistence=[("data", "/app/data")],
                        domain=["BASE_URL"], memory=384, cpus=1.0, workers=1, slots=1, live="/health/live"),
    "losverkauf": dict(database=("sqlite", "losverkauf", "losverkauf"), persistence=[("data", "/data")],
                       domain=["BASE_URL"], memory=384, cpus=1.0, workers=1, slots=1, live="/health/live"),
    "grundschultafel": dict(database=("files", "grundschultafel", "grundschultafel"), persistence=[("data", "/data")],
                            domain=["BASE_URL"], memory=512, cpus=1.0, workers=1, slots=0, live="/health/live"),
    "fahrradausbildung": dict(database=("postgres16", "fahrrad", "fahrrad"),
                              persistence=[("pgdata", "/var/lib/postgresql/data", "70:70"), ("vorlagen", "/vorlagen")],
                              domain=["FP_OEFFENTLICHE_URL"], memory=768, cpus=1.0, workers=2, slots=1,
                              live="/health/live"),
    "leseflux": dict(database=("postgres16", "leseflux", "leseflux"),
                     persistence=[("postgres_data", "/var/lib/postgresql/data", "70:70")],
                     domain=["CORS_ORIGIN"], memory=768, cpus=1.0, workers=1, slots=0, live="/health/live"),
    "kompetenz-manager": dict(database=("sqlite", "kompetenz", "kompetenz"),
                              persistence=[("instance", "/app/instance"), ("templates", "/app/odt_templates")],
                              domain=["APP_BASE_URL"], memory=1536, cpus=2.0, workers=2, slots=1, live="/health/live"),
    "abgen": dict(database=("postgres18", "abgen", "abgen"),
                  persistence=[("assets", "/app/data/assets"), ("postgres", "/var/lib/postgresql", "70:70")],
                  domain=["WEB_ORIGIN"], memory=1024, cpus=1.0, workers=1, slots=1, live="/api/health/live"),
    "fundkiste": dict(database=("sqlite", "fundkiste", "fundkiste"), persistence=[("data", "/data")],
                      domain=["FUNDKISTE_BASE_URL"], memory=256, cpus=1.0, workers=1, slots=0, live="/health/live"),
    "schuleva": dict(database=("sqlite", "schuleva", "schuleva"), persistence=[("data", "/data")],
                     domain=["BASE_URL"], memory=512, cpus=1.0, workers=1, slots=1, live="/health/live"),
}
COMPOSE_EXTRA = {"fahrradausbildung": ["docker/init-postgres.sh"], "leseflux": ["docker/init-postgres.sh"],
                 "abgen": ["docker/init-postgres.sh"]}

# Evidence produced by the earlier work packages (local builds of the implementation commits).
PREFIX = {"fahrradausbildung": "fahrrad", "kompetenz-manager": "kompetenz"}
EVIDENCE_MAP = {
    "standalone": {"gswb": ["gswb-container.json"], "grundschultafel": ["grundschultafel-standalone.log"],
                   "schulwissen": ["schulwissen-standalone.json", "schulwissen-standalone.log"]},
    "negativeAccess": {"gswb": ["pilot-checks.json"], "schulwissen": ["pilot-checks.json"]},
    "restore": {"schulwissen": ["schulwissen-http-restore.json", "pilot-postgres-restore.json"]},
    "domainRollback": {"gswb": ["pilot-domain-rollback.json"], "schulwissen": ["pilot-domain-rollback.json"],
                       "zackboing": ["zackboing-domains.json"]},
}


def run(*argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True).stdout


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Builder:
    def __init__(self, version, out):
        self.version, self.out = version, Path(out)
        self.files = {}

    def add(self, relative, data):
        if relative in self.files and self.files[relative] != data:
            raise SystemExit(f"Conflicting bundle content for {relative}")
        self.files[relative] = data
        return sha256(data)

    def evidence(self, data):
        digest = sha256(data)
        self.add("evidence/" + digest, data)
        return digest

    def record(self, app, item, status, summary, artifacts=(), extra=None):
        entries = []
        for name in artifacts:
            data = (EVIDENCE / name).read_bytes()
            entries.append({"path": f"docs/implementation/evidence/{name}", "sha256": self.evidence(data)})
        record = {"schemaVersion": 1, "app": app, "item": item, "release": self.version, "status": status,
                  "summary": summary, "artifacts": entries, **(extra or {})}
        return self.evidence(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")

    def write(self, signing_key):
        if self.out.exists():
            shutil.rmtree(self.out)
        for relative, data in self.files.items():
            path = self.out / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        metadata = {"schemaVersion": 1, "release": getattr(self, "bundle_version", self.version), "architecture": "amd64",
                    "files": {relative: sha256(data) for relative, data in sorted(self.files.items())}}
        raw = json.dumps(metadata, indent=2, sort_keys=True).encode() + b"\n"
        (self.out / "bundle.json").write_bytes(raw)
        key = load_pem_private_key(Path(signing_key).expanduser().read_bytes(), password=None)
        (self.out / "bundle.sig").write_bytes(key.sign(raw))


def app_manifest(builder, app_id, index_entry):
    cwd = ROOT / ".work/apps" / app_id
    tag = "v" + builder.version
    commit = run("git", "rev-parse", f"{tag}^{{commit}}", cwd=cwd).strip()
    remote = run("git", "ls-remote", f"https://github.com/Bingenberger/{app_id}.git", f"refs/tags/{tag}^{{}}",
                 cwd=cwd).split()
    if not remote or remote[0] != commit:
        raise SystemExit(f"{app_id}: tag {tag} on GitHub does not match local {commit[:7]}")
    implementation = index_entry["implementationCommit"]
    changed = set(run("git", "diff", "--name-only", f"{index_entry['testedCommit']}..{commit}", cwd=cwd).split())
    if not changed <= {WORKFLOW}:
        raise SystemExit(f"{app_id}: release commit differs from the tested commit beyond the release workflow: {changed}")
    images, inspections = {}, {}
    for name, _target in RELEASE_IMAGES[app_id]:
        reference = registry.pinned(f"{REGISTRY}/{name}:{builder.version}")
        info = registry.inspect(reference)
        if (info["architecture"], info["os"]) != ("amd64", "linux"):
            raise SystemExit(f"{name}: not a linux/amd64 image")
        if info["labels"].get("org.opencontainers.image.revision") != commit:
            raise SystemExit(f"{name}: image revision label does not match tag commit")
        if not {SBOM, PROVENANCE} <= set(info["attestationPredicates"]):
            raise SystemExit(f"{name}: SBOM/provenance attestations missing")
        if info["user"] in ("", "0", "root"):
            raise SystemExit(f"{name}: image runs as root")
        images[name], inspections[name] = reference, info
    compose = []
    for relative in ["docker-compose.yml", *COMPOSE_EXTRA.get(app_id, [])]:
        data = run("git", "show", f"{commit}:{relative}", cwd=cwd).encode()
        builder.add(f"compose/{app_id}/{relative}", data)
        compose.append(f"compose/{app_id}/{relative}")
    facts = FACTS[app_id]
    prefix = PREFIX.get(app_id, app_id)
    built = {"releaseCommit": commit, "testedCommit": index_entry["testedCommit"],
             "note": "Evidence was produced from local builds of testedCommit; the release image was built by "
                     "GitHub Actions from releaseCommit, which differs only by the release workflow file."}

    def existing(names):
        return [name for name in names if (EVIDENCE / name).is_file()]

    acceptance = {}
    acceptance["amd64Build"] = builder.record(
        app_id, "amd64Build", "passed", "Published linux/amd64 image(s) with revision label, SBOM and provenance.",
        existing([f"{prefix}-image.json", f"{app_id}-image.json"])[:1],
        {"images": images, "inspection": inspections, **built})
    for item, default in [("standalone", [f"{prefix}-standalone.json"]),
                          ("negativeAccess", [f"{prefix}-platform.json"]),
                          ("restore", [f"{prefix}-restore.json"]),
                          ("domainRollback", [f"{prefix}-platform.json"])]:
        artifacts = existing(EVIDENCE_MAP.get(item, {}).get(app_id, default))
        if artifacts:
            acceptance[item] = builder.record(app_id, item, "passed",
                                              f"{item} evidence from the local pilot work packages.", artifacts, built)
        else:
            acceptance[item] = builder.record(app_id, item, "open", f"No {item} evidence recorded for {app_id}.",
                                              extra=built)
    acceptance["licenses"] = builder.record(
        app_id, "licenses", "open", "Work package A0 (project licence choice and third-party material review) "
        "is open; see docs/implementation/status.md.")
    acceptance["sbom"] = builder.record(
        app_id, "sbom", "passed", "SPDX SBOM and SLSA provenance attestations attached to the published image index.",
        extra={"images": images})
    primary = RELEASE_IMAGES[app_id][0][0]
    database, name, account = facts["database"]
    manifest = {
        "schemaVersion": 1, "id": app_id, "sourceCommit": commit, "image": images[primary],
        "auxiliaryImages": {k: v for k, v in images.items() if k != primary},
        "compose": compose, "port": APPS[app_id].port,
        "database": {"engine": database, "name": name.replace("-", "_"), "account": account.replace("-", "_")},
        "persistence": [{"id": p[0].replace("_", "-"), "mount": p[1], "owner": p[2] if len(p) > 2 else "10001:10001",
                         "backup": True} for p in facts["persistence"]],
        "domainEnvironment": facts["domain"], "buildTimePublicUrl": False,
        "health": {"live": facts["live"], "ready": APPS[app_id].ready},
        "resources": {"memoryMiB": facts["memory"], "cpus": facts["cpus"], "workers": facts["workers"],
                      "exportSlotsPerProcess": facts["slots"]},
        "acceptance": acceptance,
    }
    if not manifest["auxiliaryImages"]:
        del manifest["auxiliaryImages"]
    data = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    builder.add(f"apps/{app_id}.json", data)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--signing-key", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--apps", default=",".join(APP_IDS))
    parser.add_argument("--platform-version", help="tag of the platform images (default: --version)")
    parser.add_argument("--bundle-version", help="release name of the bundle (default: --version)")
    args = parser.parse_args()
    builder = Builder(args.version, args.out)
    builder.bundle_version = args.bundle_version or args.version
    index = {entry["app"]: entry for entry in json.loads((ROOT / "patches/index.json").read_text())}
    tested = json.loads((ROOT / "patches/tested-commits.json").read_text())
    manifests = []
    for app_id in args.apps.split(","):
        entry = dict(index[app_id], testedCommit=tested[app_id])
        manifests.append(app_manifest(builder, app_id, entry))
        print(f"{app_id}: {manifests[-1]['image']}")
    platform_version = args.platform_version or args.version
    platform_commit = run("git", "rev-parse", f"v{platform_version}^{{commit}}", cwd=ROOT).strip()
    platform_images = {}
    for name in PLATFORM_IMAGES:
        reference = registry.pinned(f"{REGISTRY}/{name}:{platform_version}")
        info = registry.inspect(reference)
        if info["labels"].get("org.opencontainers.image.revision") != platform_commit:
            raise SystemExit(f"{name}: revision label does not match platform tag commit")
        platform_images[name] = reference
        print(f"{name}: {reference}")
    builder.add("platform.json", json.dumps({"schemaVersion": 1, "sourceCommit": platform_commit,
                                             "images": platform_images}, indent=2, sort_keys=True).encode() + b"\n")
    builder.write(args.signing_key)
    for manifest in manifests:
        validate_manifest(manifest, Path(args.out) / "evidence")
    print(f"Release {builder.bundle_version} written to {args.out}")


if __name__ == "__main__":
    main()
