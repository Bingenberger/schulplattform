#!/usr/bin/env python3
"""Write the managed release workflow into each isolated app checkout and commit it.

Does not push. Image names and Dockerfile targets come from RELEASE_IMAGES.
usage: install_release_workflows.py [APP ...]   (default: every app)
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schulplattform.catalogue import RELEASE_IMAGES  # noqa: E402

TEMPLATE = (ROOT / "templates/release/app-release-workflow.yml").read_text()
TARGET = ".github/workflows/release-image.yml"
MESSAGE = ("Publish versioned amd64 release images to GHCR on version tags\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")


def main():
    selected = sys.argv[1:] or list(RELEASE_IMAGES)
    for app in selected:
        images = RELEASE_IMAGES[app]
        cwd = ROOT / ".work/apps" / app
        spec = " ".join(f"{name}={target or '-'}" for name, target in images)
        path = cwd / TARGET
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE.replace("__IMAGES__", spec))
        git = lambda *a: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout
        git("add", TARGET)
        if git("diff", "--cached", "--name-only").strip():
            git("commit", "-q", "-m", MESSAGE)
        print(app, git("rev-parse", "--short", "HEAD").strip(), spec)


if __name__ == "__main__":
    main()
