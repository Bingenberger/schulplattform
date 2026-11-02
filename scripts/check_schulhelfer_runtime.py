"""Run contract checks and the existing app suite in the fixed runtime."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
for name, folder in [("schulhelfer-contract", "contract_tests"), ("schulhelfer-functional", "tests")]:
    command = ["docker", "run", "--rm", "--read-only", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:size=64m,mode=1777", "--tmpfs", "/app/data:uid=10001,gid=10001,mode=700,size=64m",
        "-e", "SECRET_KEY=synthetic-session-fixture-key-0123456789",
        "-e", "DATABASE_URL=sqlite:////app/data/app.db", "-e", "TEST_DATABASE_URL=sqlite:////app/data/test.db",
        "schulhelfer-tests:0.1.0-dev", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", folder]
    result = subprocess.run(command, text=True, capture_output=True, timeout=180)
    (ROOT / "docs/implementation/evidence" / (name + ".log")).write_text(
        "$ " + " ".join(command) + "\n" + result.stdout + result.stderr + f"\nexit_code={result.returncode}\n")
    print(name, result.returncode, result.stdout[-500:], flush=True)
    if result.returncode:
        raise SystemExit("Runtime tests failed; inspect the fixture log")
