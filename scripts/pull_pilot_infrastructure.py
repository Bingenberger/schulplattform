"""Pull only audit-pinned infrastructure images; capture exact outcomes."""
from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
rows = json.loads((root / "docs/platform-audit/evidence/prototype-images.json").read_text())
selected = []
with (root / "docs/implementation/evidence/pilot-infrastructure.log").open("w") as log:
    for row in rows:
        if "keycloak" in row["tag"]:
            continue
        digest = row["repo_digests"][0].split("@")[1]
        reference = row["tag"] + "@" + digest
        log.write("$ docker pull " + reference + "\n")
        log.flush()
        result = subprocess.run(["docker", "pull", reference], stdout=log,
                                stderr=subprocess.STDOUT, timeout=300)
        log.write(f"exit_code={result.returncode}\n")
        if result.returncode:
            raise SystemExit(result.returncode)
        selected.append({"reference": reference, "architecture": row["architecture"]})
(root / "docs/implementation/evidence/pilot-infrastructure.json").write_text(json.dumps(selected, indent=2) + "\n")
print("Pinned PostgreSQL, Caddy and Mailpit images available")
