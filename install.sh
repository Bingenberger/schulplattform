#!/bin/sh
# Schulplattform installer entry point. Creates the hash-locked Python environment
# on first use (Ubuntu 24.04, root) and then runs the installer CLI.
set -eu
# Relative paths on the command line (archives, bundle, key files) refer to where the operator is.
SP_CALLER_CWD=$(pwd)
export SP_CALLER_CWD
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
  if [ "$(id -u)" -ne 0 ]; then
    echo 'Erstinstallation: bitte als root ausführen (sudo ./install.sh ...).' >&2
    exit 1
  fi
  if ! python3 -c 'import ensurepip' 2>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get update -q >&2
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends python3-venv >&2
  fi
  umask 022
  python3 -m venv .venv
  .venv/bin/pip install -q --disable-pip-version-check --require-hashes -r requirements-host.lock >&2
fi
exec .venv/bin/python -m schulplattform.installer "$@"
