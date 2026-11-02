#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
  echo 'Test-/Entwicklungsstand: zuerst Python-venv und requirements-dev.txt installieren.' >&2
  exit 1
fi
exec .venv/bin/python -m schulplattform.installer "$@"
