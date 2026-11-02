#!/usr/bin/env python3
"""Record the local amd64 development build; does not publish images."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/implementation/evidence'
OUT.mkdir(parents=True, exist_ok=True)
command = ['docker', 'build', '--platform', 'linux/amd64', '-t', 'gswb:0.1.0-dev', '.']
result = subprocess.run(command, cwd=ROOT / '.work/apps/gswb', text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
(OUT / 'gswb-build.log').write_text('$ ' + ' '.join(command) + '\n' + result.stdout + f'\nexit_code={result.returncode}\n')
if result.returncode:
    raise SystemExit(result.returncode)
data = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'gswb:0.1.0-dev'], text=True))[0]
selected = {key: data[key] for key in ['Id', 'Architecture', 'Os', 'Size', 'RepoDigests']}
selected['note'] = 'Local image ID is not a registry distribution digest; no published release.'
(OUT / 'gswb-image.json').write_text(json.dumps(selected, indent=2) + '\n')
print(json.dumps(selected))
