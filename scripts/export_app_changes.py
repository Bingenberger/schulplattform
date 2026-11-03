#!/usr/bin/env python3
"""Commit isolated app work and export reviewable patches, without pushing."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
rows = json.loads((ROOT / 'docs/platform-audit/evidence/repositories.json').read_text())
audited = {row['repo']: row['sha'] for row in rows}
packages = {
    'schulwissen': ('Add explicit migrations, readiness, proxy trust and bounded PDF exports', [
        'Dockerfile', 'docker-compose.yml', 'docker/start.sh',
        'schulwissen/umgebung.py', 'schulwissen/einstellungen.py', 'schulwissen/urls.py',
        'kern/health.py', 'kern/proxy.py', 'kern/export_limit.py', 'kern/export_views.py',
        'kern/prozesslesen.py', 'kern/management/commands/platform_migrate.py', 'PLATFORM.md']),
    'gswb': ('Close editor access and add isolated standalone container', [
        'grundschul_woerterbuch', 'templates/review_entry.html', '.dockerignore',
        'Dockerfile', 'docker-compose.yml', 'requirements.lock', 'PLATFORM.md']),
    'zackboing': ('Add isolated Node LTS container, explicit migration and closed bootstrap', [
        'Dockerfile', '.dockerignore', 'docker-compose.yml', 'PLATFORM.md',
        'server/auth.js', 'server/bootstrap.js', 'server/config.js', 'server/db.js',
        'server/game.js', 'server/index.js', 'server/migrate.js',
        'public/teacher.html', 'public/js/teacher.js',
        'test/session-expiry.js', 'test/bootstrap.js', 'test/e2e.js',
        'test/run-fixtures.js', 'test/platform-contract.js']),
    'fahrradausbildung': ('Add explicit PostgreSQL migration, shared worker limits and standalone isolation', [
        'Dockerfile', '.dockerignore', '.env.example', '.gitignore', 'docker-compose.yml',
        'docker/start.sh', 'docker/init-postgres.sh', 'prepare_secrets.py',
        'app/betrieb.py', 'app/migrate.py', 'app/run.py', 'app/config.py', 'app/db.py',
        'app/kartenbild.py', 'app/kommandos.py', 'app/main.py', 'app/modelle.py',
        'app/pdf.py', 'app/posten/api.py', 'app/web/anmeldung.py',
        'app/posten_app/js/main.js', 'app/posten_app/css/posten.css', 'tests/test_posten_offline.py',
        'migrations/versions/0008_betriebslimits.py', 'contract_tests',
        'PLATFORM.md', 'README.md', 'DEPLOYMENT.md']),
    'grundschultafel': ('Add isolated Next runtime, transactional files and revocable personal sessions', [
        'Dockerfile', '.dockerignore', '.gitignore', 'docker-compose.yml', 'next.config.ts', 'PLATFORM.md', 'README.md',
        'src/lib', 'src/middleware.ts', 'src/app/api', 'src/app/assets', 'src/app/health',
        'src/app/change-password/page.tsx', 'src/app/login/page.tsx', 'src/app/upload/page.tsx',
        'src/app/layout.tsx', 'src/app/globals.css', 'src/components/Toolbar.tsx',
        'public/timer/index.html', 'scripts']),
    'schulhelfer': ('Add isolated standalone runtime, explicit migrations and private local setup', [
        'Dockerfile', '.dockerignore', '.gitignore', 'docker-compose.yml',
        'requirements.txt', 'requirements.lock', 'requirements-test.lock', 'PLATFORM.md', 'README.md',
        '.env.example', 'prepare_secret.py', 'seed.py', 'schulfest-helfer.service',
        'app/config.py', 'app/database.py', 'app/dependencies.py', 'app/email_service.py',
        'app/jobs.py', 'app/main.py', 'app/scheduler.py', 'app/routers/admin.py', 'app/routers/public.py',
        'app/platform.py', 'app/migrate.py', 'app/setup_admin.py', 'app/export_limit.py', 'app/run.py',
        'migrations/env.py', 'tests/conftest.py', 'contract_tests/test_contract.py']),
    'losverkauf': ('Add isolated ticket-sale runtime, explicit migrations and durable mail dispatcher', [
        'app.py', 'mail.py', 'los_runtime.py', 'los_migrate.py', 'los_worker.py',
        'gunicorn.conf.py', 'prepare_secrets.py', 'import_streets.py', 'Dockerfile', '.dockerignore',
        '.gitignore', 'docker-compose.yml', 'requirements.lock', 'requirements-test.lock',
        'templates', 'static/app.js', 'static/vendor', 'tests', 'README.md', 'PLATFORM.md',
        'deploy/losverkauf.env.example', 'deploy/losverkauf.service', 'deploy/nginx-losverkauf.conf']),
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
