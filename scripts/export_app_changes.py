#!/usr/bin/env python3
"""Commit isolated app work and export reviewable patches, without pushing."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
rows = json.loads((ROOT / 'docs/platform-audit/evidence/repositories.json').read_text())
audited = {row['repo']: row['sha'] for row in rows}
packages = {
    'gswb': ('Close editor access and add isolated standalone container', [
        'grundschul_woerterbuch', 'templates/review_entry.html', '.dockerignore',
        'Dockerfile', 'docker-compose.yml', 'requirements.lock', 'PLATFORM.md']),
    'zackboing': ('Reject expired and invalid server sessions', ['server/auth.js', 'test/session-expiry.js']),
    'grundschultafel': ('Replace default login with local single-use bootstrap', [
        'src/lib/users.ts', 'src/app/api/auth/change-password/route.ts',
        'src/app/api/auth/login/route.ts', 'src/app/change-password/page.tsx',
        'src/app/login/page.tsx', 'scripts/bootstrap.mjs', 'scripts/test-users.cjs', 'PLATFORM.md']),
    'losverkauf': ('Bind administrative login to a personal identity', [
        'app.py', 'templates/login.html', 'deploy/losverkauf.env.example', 'PLATFORM.md']),
}
index = []
for app, (message, files) in packages.items():
    cwd = ROOT / '.work/apps' / app
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True)
    git('diff', '--check')
    git('add', '--', *files)
    if git('diff', '--cached', '--name-only').strip():
        print(git('commit', '-m', message), flush=True)
    commit = git('rev-parse', 'HEAD').strip()
    output = ROOT / 'patches' / app
    output.mkdir(parents=True, exist_ok=True)
    (output / 'changes.patch').write_text(git('format-patch', '--stdout', f'{audited[app]}..HEAD'))
    index.append(dict(app=app, baseCommit=audited[app], implementationCommit=commit,
                      patch=f'patches/{app}/changes.patch'))
(ROOT / 'patches/index.json').write_text(json.dumps(index, indent=2) + '\n')
