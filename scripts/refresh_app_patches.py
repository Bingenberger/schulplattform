#!/usr/bin/env python3
"""Re-export patches/<app>/changes.patch and patches/index.json from the app checkouts.

Keeps each recorded baseCommit; implementationCommit becomes the checkout HEAD,
which must descend from the base. Never commits or pushes.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    index_path = ROOT / "patches/index.json"
    index = json.loads(index_path.read_text())
    for entry in index:
        cwd = ROOT / ".work/apps" / entry["app"]
        git = lambda *a: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout
        head = git("rev-parse", "HEAD").strip()
        subprocess.run(["git", "merge-base", "--is-ancestor", entry["baseCommit"], head], cwd=cwd, check=True)
        (ROOT / entry["patch"]).write_text(git("format-patch", "--stdout", f"{entry['baseCommit']}..{head}"))
        entry["implementationCommit"] = head
        print(entry["app"], head[:7])
    index_path.write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    main()
