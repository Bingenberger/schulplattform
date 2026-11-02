#!/usr/bin/env python3
"""Isolated standalone Compose smoke; never uses existing deployment data."""
import json
import hashlib
import os
from pathlib import Path
import secrets
import socket
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation/evidence'
OUT.mkdir(parents=True, exist_ok=True)
project = 'sp-gswb-test-' + secrets.token_hex(4)
work = ROOT / '.work' / project
work.mkdir(mode=0o700)
for filename, value in [('session', secrets.token_urlsafe(48)), ('editor', '')]:
    path = work / filename
    path.write_text(value)
    path.chmod(0o444)  # container UID can read; parent directory remains host-private
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
env = os.environ | dict(GSWB_SECRET_FILE=str(work / 'session'),
    GSWB_EDITOR_HASH_FILE=str(work / 'editor'), GSWB_PORT=str(port), HANDWRITING_MODE='mock')
compose = ROOT / '.work/docker-compose'
expected = (ROOT / '.work/docker-compose.sha256').read_text().split()[0]
with compose.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, 'Compose checksum mismatch'
compose.chmod(0o755)
base = [str(compose), '-p', project, '-f', str(ROOT / '.work/apps/gswb/docker-compose.yml')]
log = []


def run(args):
    result = subprocess.run(args, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180)
    log.append('$ ' + ' '.join(args) + '\n' + result.stdout + f'\nexit_code={result.returncode}')
    if result.returncode:
        raise RuntimeError('Command failed; see evidence log')
    return result.stdout


def status(path, method='GET'):
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', method=method,
                                     headers={'X-Forwarded-User': 'admin'})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as response:
        return response.code


try:
    run(base + ['run', '--rm', '--no-deps', 'app', 'python', '-m', 'grundschul_woerterbuch.migrate'])
    run(base + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '90'])
    results = {path: status(path) for path in ['/', '/health/live', '/health/ready', '/review']}
    results['anonymous-write'] = status('/review/synthetic/approve', 'POST')
    assert results == {'/': 200, '/health/live': 200, '/health/ready': 200,
                       '/review': 401, 'anonymous-write': 401}, results
    cid = run(base + ['ps', '-q', 'app']).strip()
    run(['docker', 'inspect', '--format', '{{.Config.User}} readOnly={{.HostConfig.ReadonlyRootfs}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}', cid])
    run(base + ['restart', 'app'])
    run(base + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '90'])
    assert status('/health/ready') == 200
    (OUT / 'gswb-container.json').write_text(json.dumps({'project': project, 'results': results,
        'restartReady': True, 'scope': 'standalone local smoke; no TLS/platform/domain/restore acceptance'}, indent=2) + '\n')
    print(json.dumps(results))
finally:
    try:
        run(base + ['down'])  # retain data; never use down -v
    finally:
        (OUT / f'{project}.log').write_text('\n\n'.join(log) + '\n')
