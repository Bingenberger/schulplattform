#!/bin/sh
# Copy the current working tree (without .git/.work/.venv) to /opt/schulplattform in a test VM.
set -eu
VM=${1:?vm name}
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/sync"
tar -C "$ROOT" -cf - --exclude=.work --exclude=.venv --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache . \
  | tar -C "$STAGE/sync" -xf -
python3 "$ROOT/tests/vm/vm.py" push "$VM" "$STAGE/sync" /root/
python3 "$ROOT/tests/vm/vm.py" ssh "$VM" -- 'cp -a /root/sync/. /opt/schulplattform/ && rm -rf /root/sync && chown -R root:root /opt/schulplattform'
