#!/usr/bin/env python3
"""Run bounded local checks and save exact output without environment/secret dumps."""
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation/evidence'
OUT.mkdir(parents=True, exist_ok=True)
checks = [
    ('python-tests', ROOT, [str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', 'tests']),
    ('zackboing-session', ROOT / '.work/apps/zackboing', ['node', 'test/session-expiry.js']),
    ('grundschultafel-users', ROOT / '.work/apps/grundschultafel', ['node', 'scripts/test-users.cjs']),
    ('grundschultafel-types', ROOT / '.work/apps/grundschultafel', ['node', 'node_modules/typescript/bin/tsc', '--noEmit']),
]
summary = []
for name, cwd, argv in checks:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180)
    (OUT / f'{name}.log').write_text('$ ' + ' '.join(argv) + '\n' + result.stdout + f'\nexit_code={result.returncode}\n')
    summary.append(dict(check=name, started=started, exitCode=result.returncode))
    print(name, result.returncode, result.stdout[-2000:], flush=True)
(OUT / 'checks.json').write_text(json.dumps(summary, indent=2) + '\n')
raise SystemExit(any(item['exitCode'] for item in summary))
