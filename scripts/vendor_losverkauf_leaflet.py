"""Vendor the fixed official Leaflet npm archive with its license and hashes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / ".work/losverkauf-leaflet"
folder.mkdir(mode=0o755, exist_ok=True)
base = "node:22.23.4-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da"
command = ["docker", "run", "--rm", "--user", str(os.getuid()) + ":" + str(os.getgid()),
           "-e", "npm_config_cache=/tmp/npm-cache", "-v", str(folder) + ":/out", "-w", "/out",
           base, "npm", "pack", "leaflet@1.9.4", "--json"]
result = subprocess.run(command, capture_output=True, text=True, timeout=180)
assert result.returncode == 0, "Official Leaflet archive fetch failed"
record = json.loads(result.stdout)[0]
archive = folder / record["filename"]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '84c65a256e50657896f54c33bd857b6849ebe94c817803be818bf32a3dde0b77'
output = ROOT / ".work/apps/losverkauf/static/vendor/leaflet"
output.mkdir(parents=True, exist_ok=True)
inventory = {}
with tarfile.open(archive) as package:
    names = ["package/LICENSE", "package/dist/leaflet.js", "package/dist/leaflet.css"]
    names += [item.name for item in package.getmembers() if item.isfile() and item.name.startswith("package/dist/images/")]
    for name in names:
        member = package.getmember(name)
        assert member.isfile()
        target = output / ("LICENSE" if name == "package/LICENSE" else name.removeprefix("package/dist/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        content = package.extractfile(member).read()
        target.write_bytes(content)
        inventory[str(target.relative_to(output))] = hashlib.sha256(content).hexdigest()
metadata = {"package": "leaflet", "version": "1.9.4", "integrity": record["integrity"],
            "archiveSha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "files": inventory}
(output / "inventory.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps({"package": "leaflet", "version": "1.9.4", "files": len(inventory)}))
