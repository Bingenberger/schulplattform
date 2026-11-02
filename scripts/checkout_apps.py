#!/usr/bin/env python3
"""Isolated, resumable checkouts of audited commits, without changing existing work."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def checkout(root, selected):
    rows = json.loads((ROOT / 'docs/platform-audit/evidence/repositories.json').read_text())
    failures = []
    for row in rows:
        name, sha = row['repo'], row['sha']
        if selected and name not in selected:
            continue
        dest = root / name
        env = os.environ | {'GIT_TERMINAL_PROMPT': '0',
                            'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes'}
        def git(*args, check=True):
            return subprocess.run(['git', '-C', str(dest), *args], env=env,
                                  text=True, capture_output=True, check=check, timeout=180)
        try:
            if dest.exists() and not (dest / '.git').is_dir():
                raise ValueError('existing non-repository directory; refusing overwrite')
            if not dest.exists():
                dest.mkdir(parents=True)
                git('init')
                url = (f'git@github.com:Bingenberger/{name}.git' if name == 'schulanmeldung'
                       else f'https://github.com/Bingenberger/{name}.git')
                git('remote', 'add', 'origin', url)
            head = git('rev-parse', '--verify', 'HEAD', check=False)
            if head.returncode == 0:
                if head.stdout.strip() != sha:
                    raise ValueError('different HEAD; preserving existing work')
                print(f'{name}: audited HEAD already present', flush=True)
                continue
            if git('status', '--porcelain').stdout.strip():
                raise ValueError('uncommitted files; refusing checkout')
            git('fetch', '--depth=1', 'origin', sha)
            git('checkout', '--detach', sha)
            print(f'{name}: {sha}', flush=True)
        except (ValueError, subprocess.SubprocessError) as exc:
            failures.append(name)
            print(f'{name}: BLOCKED: {exc}', flush=True)
    return bool(failures)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / '.work/apps')
    parser.add_argument('apps', nargs='*')
    args = parser.parse_args()
    raise SystemExit(checkout(args.root, args.apps))
