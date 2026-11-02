"""Lock dashboard production dependencies with hashes."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
result = subprocess.run(["uv", "pip", "compile", "requirements-dashboard.in", "--generate-hashes",
                         "-o", "requirements-dashboard.lock", "--quiet"],
                        cwd=root, text=True, capture_output=True, timeout=120)
if result.returncode:
    raise SystemExit("Dashboard dependency resolution failed")
print("Dashboard hash lockfile written")
