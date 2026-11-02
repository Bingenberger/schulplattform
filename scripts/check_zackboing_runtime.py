"""Run the security fixtures inside the exact Node-LTS tests image."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
commands = []
for script in ("test/bootstrap.js", "test/session-expiry.js"):
    command = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--memory", "384m", "--cpus", "1", "--pids-limit", "128",
               "--tmpfs", "/tmp:size=64m,mode=1777", "zackboing-tests:0.1.0-dev", "node", script]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    commands.append("$ " + " ".join(command) + "\n" + result.stdout + result.stderr + f"\nexit_code={result.returncode}\n")
    if result.returncode:
        raise RuntimeError("Runtime security fixture failed")
(root / "docs/implementation/evidence/zackboing-runtime-security.log").write_text("\n".join(commands))
print("PASS: bootstrap and session fixtures under pinned Node 22.23.4")
