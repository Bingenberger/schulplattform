"""Bounded local build with retained evidence; never publish."""
from pathlib import Path
import subprocess
import json

root = Path(__file__).resolve().parents[1]
out = root / "docs/implementation/evidence"
out.mkdir(parents=True, exist_ok=True)
argv = ["docker", "build", "--platform", "linux/amd64", "-t", "schulwissen:0.1.0-dev", "."]
with (out / "schulwissen-build.log").open("w") as log:
    log.write("$ " + " ".join(argv) + "\n")
    log.flush()
    result = subprocess.run(argv, cwd=root / ".work/apps/schulwissen",
                            stdout=log, stderr=subprocess.STDOUT, timeout=900)
    log.write(f"\nexit_code={result.returncode}\n")
if result.returncode:
    raise SystemExit(result.returncode)
image = json.loads(subprocess.check_output(["docker", "image", "inspect", "schulwissen:0.1.0-dev"], text=True))[0]
selected = {key: image[key] for key in ["Id", "Architecture", "Os", "Size", "RepoDigests"]}
(out / "schulwissen-image.json").write_text(json.dumps(selected, indent=2) + "\n")
print(json.dumps(selected))
