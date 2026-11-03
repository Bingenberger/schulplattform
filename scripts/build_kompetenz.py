"""Build the isolated app and run original functional tests with SMTP disabled."""
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "docs/implementation/evidence"
for target, tag in [("runtime", "kompetenz-manager:0.1.0-dev"), ("tests", "kompetenz-manager-tests:0.1.0-dev")]:
    command = ["docker", "build", "--platform", "linux/amd64", "--memory", "1024m",
               "--target", target, "-t", tag, "."]
    with (out / ("kompetenz-manager-build-" + target + ".log")).open("w") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        result = subprocess.run(command, cwd=ROOT / ".work/apps/kompetenz-manager", stdout=log,
                                stderr=subprocess.STDOUT, timeout=600)
        log.write(f"\nexit_code={result.returncode}\n")
    if result.returncode:
        raise SystemExit("Build failed; see stage log")
image = json.loads(subprocess.check_output(["docker", "image", "inspect", "kompetenz-manager:0.1.0-dev"], text=True))[0]
runtime = json.loads(subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--read-only",
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "kompetenz-manager:0.1.0-dev", "python", "-c",
    "import sys,sqlite3,json,importlib.metadata as m;print(json.dumps({'python':sys.version.split()[0],'sqlite':sqlite3.sqlite_version,**{name:m.version(name) for name in ['Flask','Flask-SQLAlchemy','SQLAlchemy','gunicorn','Pillow']}}))"], text=True))
report = {key: image[key] for key in ["Id", "Architecture", "Os", "Size", "RepoDigests"]}
report["runtime"] = runtime
report["libreoffice"] = subprocess.check_output(["docker","run","--rm","--read-only","--network","none",
    "kompetenz-manager:0.1.0-dev","soffice","--version"],text=True).strip()

(out / "kompetenz-manager-image.json").write_text(json.dumps(report, indent=2) + "\n")
print("Built amd64 runtime and test images")
