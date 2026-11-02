"""Check a stopped pilot produces a clear CLI failure without a traceback."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
command = [str(root / ".venv/bin/python"), "-m", "schulplattform.installer",
           "pilot-up", "--state-dir", ".work/pilot-v2"]
result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=30)
output = result.stdout + result.stderr
assert result.returncode == 1
assert "not ready" in output and "Traceback" not in output
(root / "docs/implementation/evidence/pilot-cli-error.log").write_text(
    "$ " + " ".join(command) + "\n" + output + f"\nexit_code={result.returncode}\n")
print("Stopped pilot CLI fails clearly without traceback")
