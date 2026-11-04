#!/bin/sh
# Fresh acceptance VM: create guest, test-only DNS/ACME fixtures, platform code, signed release,
# trust key and configuration. Does NOT run the installer.
#   tests/vm/prepare.sh NAME SSH_PORT RELEASE_DIR "initial dns hostnames (short names)"
set -eu
VM=${1:?name}; PORT=${2:?ssh port}; RELEASE=${3:?release dir}; NAMES=${4:-verwaltung}
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
VMPY="python3 $ROOT/tests/vm/vm.py"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
$VMPY create "$VM" --ssh-port "$PORT"
mkdir -p "$STAGE/prep/release"
cp "$ROOT/.work/vm/dl/pebble-linux-amd64.tar.gz" "$ROOT/tests/vm/fixtures.sh" "$ROOT/tests/vm/platform.toml" "$STAGE/prep/"
cp "$ROOT/release-keys/schulplattform-release.pub" "$STAGE/prep/release-trust.pub"
cp -r "$RELEASE/." "$STAGE/prep/release/"
$VMPY push "$VM" "$STAGE/prep" /root/
$VMPY ssh "$VM" -- 'cp /root/prep/pebble-linux-amd64.tar.gz /root/prep/fixtures.sh /root/ && bash /root/fixtures.sh >/root/fixtures.log 2>&1 && tail -2 /root/fixtures.log &&
  mkdir -p /etc/schulplattform /srv/backup-offsite /opt/schulplattform &&
  install -m 0644 /root/prep/platform.toml /etc/schulplattform/platform.toml &&
  install -m 0644 /root/prep/release-trust.pub /root/release-trust.pub && rm -rf /root/release && mv /root/prep/release /root/release'
for name in $NAMES; do
  $VMPY ssh "$VM" -- "echo '10.0.2.15 $name.schule.test' >> /etc/sp-test-hosts"
done
$VMPY ssh "$VM" -- 'systemctl reload sp-test-dns'
"$ROOT/tests/vm/sync.sh" "$VM"
echo "$VM prepared"
