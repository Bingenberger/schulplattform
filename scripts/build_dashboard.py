"""Build the dashboard without any application data or credentials."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "docs/implementation/evidence"
command = ["docker", "build", "--platform", "linux/amd64", "-f", "Dockerfile.dashboard",
           "-t", "schulplattform-dashboard:0.1.0-dev", "."]
with (out / "dashboard-build.log").open("w") as log:
    log.write("$ " + " ".join(command) + "\n")
    log.flush()
    result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    log.write(f"\nexit_code={result.returncode}\n")
if result.returncode:
    raise SystemExit("Dashboard build failed; see build log")
image = json.loads(subprocess.check_output(["docker", "image", "inspect", "schulplattform-dashboard:0.1.0-dev"], text=True))[0]
(out / "dashboard-image.json").write_text(json.dumps({key: image[key] for key in
    ["Id", "Architecture", "Os", "Size", "RepoDigests"]}, indent=2) + "\n")
print("Dashboard amd64 development image built")
