"""Minimal OCI registry client for resolving and checking published release images.

Only anonymous pull tokens are used (public packages). An optional token file
may be supplied for private packages; its content is never logged.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
REFERENCE = re.compile(r"^(?P<host>[a-z0-9.-]+)/(?P<repo>[a-z0-9][a-z0-9._/-]*):(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]*)"
                       r"(?:@(?P<digest>sha256:[a-f0-9]{64}))?$")


class RegistryError(RuntimeError):
    pass


def parse(reference):
    match = REFERENCE.fullmatch(reference)
    if not match:
        raise ValueError("Invalid image reference")
    return match.groupdict()


def _token(host, repo, credential=None):
    query = urllib.parse.urlencode({"scope": f"repository:{repo}:pull", "service": host})
    request = urllib.request.Request(f"https://{host}/token?{query}")
    if credential:
        import base64
        request.add_header("Authorization", "Basic " + base64.b64encode(credential.encode()).decode())
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)["token"]
    except (urllib.error.URLError, KeyError, ValueError):
        raise RegistryError("Registry token unavailable (package missing or not public)") from None


def resolve(reference, credential=None):
    """Return the manifest digest the registry currently serves for host/repo:tag."""
    ref = parse(reference)
    token = _token(ref["host"], ref["repo"], credential)
    request = urllib.request.Request(f"https://{ref['host']}/v2/{ref['repo']}/manifests/{ref['tag']}",
                                     method="HEAD", headers={"Accept": ACCEPT, "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            digest = response.headers.get("Docker-Content-Digest", "")
    except urllib.error.HTTPError as exc:
        raise RegistryError(f"Image not available: HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RegistryError("Registry unreachable") from None
    if not re.fullmatch("sha256:[a-f0-9]{64}", digest):
        raise RegistryError("Registry returned no content digest")
    return digest


def _get(host, repo, kind, ref, token, accept=ACCEPT):
    request = urllib.request.Request(f"https://{host}/v2/{repo}/{kind}/{ref}",
                                     headers={"Accept": accept, "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(8 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        raise RegistryError(f"Registry object unavailable: HTTP {exc.code}") from None
    if kind == "blobs" and "sha256:" + __import__("hashlib").sha256(data).hexdigest() != ref:
        raise RegistryError("Registry blob digest mismatch")
    return json.loads(data)


def inspect(reference, credential=None):
    """Labels of the linux/amd64 image and whether SBOM/provenance attestations are attached."""
    ref = parse(reference)
    if not ref["digest"]:
        raise ValueError("inspect requires a digest-pinned reference")
    token = _token(ref["host"], ref["repo"], credential)
    index = _get(ref["host"], ref["repo"], "manifests", ref["digest"], token)
    manifests = index.get("manifests")
    attestations = []
    if manifests is None:
        image_manifest = index
    else:
        platform = [m for m in manifests if m.get("platform", {}).get("os") == "linux"
                    and m.get("platform", {}).get("architecture") == "amd64"]
        if len(platform) != 1:
            raise RegistryError("Expected exactly one linux/amd64 image in the index")
        attestations = [m for m in manifests
                        if m.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest"
                        and m.get("annotations", {}).get("vnd.docker.reference.digest") == platform[0]["digest"]]
        image_manifest = _get(ref["host"], ref["repo"], "manifests", platform[0]["digest"], token)
    config = _get(ref["host"], ref["repo"], "blobs", image_manifest["config"]["digest"], token)
    predicates = []
    for attestation in attestations:
        manifest = _get(ref["host"], ref["repo"], "manifests", attestation["digest"], token)
        predicates += [layer.get("annotations", {}).get("in-toto.io/predicate-type", "")
                       for layer in manifest.get("layers", [])]
    return {"architecture": config.get("architecture"), "os": config.get("os"),
            "labels": config.get("config", {}).get("Labels") or {},
            "user": config.get("config", {}).get("User", ""),
            "attestationPredicates": sorted(set(predicates))}


def pinned(reference, credential=None):
    """Resolve tag to 'host/repo:tag@digest'; an existing pin must still match."""
    ref = parse(reference)
    digest = resolve(f"{ref['host']}/{ref['repo']}:{ref['tag']}", credential)
    if ref["digest"] and ref["digest"] != digest:
        raise RegistryError("Published digest differs from the pinned digest")
    return f"{ref['host']}/{ref['repo']}:{ref['tag']}@{digest}"


if __name__ == "__main__":
    import sys
    for item in sys.argv[1:]:
        try:
            print(pinned(item))
        except (RegistryError, ValueError) as exc:
            print(item, "->", exc)
