"""Run local Zackboing security tests; keep exact non-secret output."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
for name, script in [("zackboing-bootstrap", "test/bootstrap.js"), ("zackboing-session", "test/session-expiry.js")]:
    result = subprocess.run(["node", script], cwd=root / ".work/apps/zackboing",
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    (root / "docs/implementation/evidence" / (name + ".log")).write_text(
        "$ node " + script + "\n" + result.stdout + f"\nexit_code={result.returncode}\n")
    print(name, result.returncode, result.stdout)
    if result.returncode:
        raise SystemExit(result.returncode)
