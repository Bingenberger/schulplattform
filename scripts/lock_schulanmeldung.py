"""Resolve hash-locked app and test dependencies under the pinned Python runtime."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
app = ROOT / ".work/apps/schulanmeldung"
directory = ROOT / ".work/schulanmeldung-lock"
directory.mkdir(mode=0o755, exist_ok=True)
base = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
outputs = {}
for name, extras in [("requirements.lock", [])]:
    target = directory / (name + ".json")
    command = ["docker", "run", "--rm", "--user", str(os.getuid()) + ":" + str(os.getgid()),
               "-e", "PIP_CACHE_DIR=/tmp/pip-cache", "-v", str(app / "requirements.txt") + ":/requirements.txt:ro",
               "-v", str(directory) + ":/lock", base, "python", "-m", "pip", "install",
               "--dry-run", "--ignore-installed", "--only-binary=:all:", "--report", "/lock/" + target.name,
               "-r", "/requirements.txt", *extras]
    with (directory / (name + ".log")).open("w") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=240)
    if result.returncode:
        raise RuntimeError("Lock resolution failed")
    rows = json.loads(target.read_text())["install"]
    lock = "# Resolved under Python 3.12.12, linux/amd64; wheel hashes.\n"
    for row in sorted(rows, key=lambda x: x["metadata"]["name"].lower()):
        lock += row["metadata"]["name"] + "==" + row["metadata"]["version"] + " --hash=sha256:" + row["download_info"]["archive_info"]["hashes"]["sha256"] + "\n"
    (app / name).write_text(lock)
    outputs[name] = len(rows)
print(json.dumps(outputs))
