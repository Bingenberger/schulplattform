"""Resolve the actual Node 22 LTS base and pin its digest for the native build."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "docs/implementation/evidence"
tag = "node:22-bookworm-slim"
with (out / "zackboing-node-base.log").open("w") as log:
    argv = ["docker", "pull", "--platform", "linux/amd64", tag]
    log.write("$ " + " ".join(argv) + "\n")
    log.flush()
    result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    log.write(f"\nexit_code={result.returncode}\n")
if result.returncode:
    raise SystemExit("Node base image pull failed")
image = json.loads(subprocess.check_output(["docker", "image", "inspect", tag], text=True))[0]
assert image["Architecture"] == "amd64"
digest = image["RepoDigests"][0].split("@")[1]
version = subprocess.check_output(["docker", "run", "--rm", "--network", "none", tag, "node", "--version"], text=True).strip()
assert version.startswith("v22.")
reference = "node:" + version[1:] + "-bookworm-slim@" + digest
(root / ".work/node-base.json").write_text(json.dumps({"reference": reference, "runtime": version, "digest": digest}) + "\n")
(out / "zackboing-node-base.json").write_text(json.dumps({"reference": reference, "runtime": version, "architecture": "amd64"}, indent=2) + "\n")
print("Resolved fixed Node LTS runtime:", version)
