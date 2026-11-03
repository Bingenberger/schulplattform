"""Build the isolated app and run original functional tests with SMTP disabled."""
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "docs/implementation/evidence"
for target, tag in [("final", "losverkauf:0.1.0-dev"), ("tests", "losverkauf-tests:0.1.0-dev")]:
    command = ["docker", "build", "--platform", "linux/amd64", "--memory", "1024m",
               "--target", target, "-t", tag, "."]
    with (out / ("losverkauf-build-" + target + ".log")).open("w") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        result = subprocess.run(command, cwd=ROOT / ".work/apps/losverkauf", stdout=log,
                                stderr=subprocess.STDOUT, timeout=600)
        log.write(f"\nexit_code={result.returncode}\n")
    if result.returncode:
        raise SystemExit("Build failed; see stage log")
image = json.loads(subprocess.check_output(["docker", "image", "inspect", "losverkauf:0.1.0-dev"], text=True))[0]
runtime = json.loads(subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--read-only",
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "losverkauf:0.1.0-dev", "python", "-c",
    "import sys,sqlite3,json,importlib.metadata as m;print(json.dumps({'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,**{name:m.version(name) for name in ['flask','gunicorn','reportlab']}}))"], text=True))
report = {key: image[key] for key in ["Id", "Architecture", "Os", "Size", "RepoDigests"]}
report["runtime"] = runtime
(out / "losverkauf-image.json").write_text(json.dumps(report, indent=2) + "\n")
print("Built amd64 runtime and test images")
