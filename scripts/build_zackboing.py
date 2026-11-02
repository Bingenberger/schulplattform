"""Build native dependencies under the fixed Node LTS; no host toolchain use."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "docs/implementation/evidence"
for stage, tag in [("runtime", "zackboing:0.1.0-dev"), ("tests", "zackboing-tests:0.1.0-dev")]:
    argv = ["docker", "build", "--platform", "linux/amd64", "--memory", "1024m", "--target", stage, "-t", tag, "."]
    with (out / ("zackboing-build-" + stage + ".log")).open("w") as log:
        log.write("$ " + " ".join(argv) + "\n")
        log.flush()
        result = subprocess.run(argv, cwd=root / ".work/apps/zackboing", stdout=log, stderr=subprocess.STDOUT, timeout=900)
        log.write(f"\nexit_code={result.returncode}\n")
    if result.returncode:
        raise SystemExit("Zackboing build failed; see stage log")
image = json.loads(subprocess.check_output(["docker", "image", "inspect", "zackboing:0.1.0-dev"], text=True))[0]
native = "const db=require('better-sqlite3')(':memory:');console.log(JSON.stringify({node:process.version,abi:process.versions.modules,betterSqlite:require('better-sqlite3/package.json').version,sqlite:db.prepare('select sqlite_version() as version').get().version}));db.close();"
runtime = json.loads(subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--read-only",
    "--tmpfs", "/tmp:size=32m,mode=1777", "zackboing:0.1.0-dev", "node", "-e", native], text=True))
report = {key: image[key] for key in ["Id", "Architecture", "Os", "Size", "RepoDigests"]}
report["runtime"] = runtime
(out / "zackboing-image.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
