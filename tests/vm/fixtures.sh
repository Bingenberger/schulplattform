#!/bin/bash
# Test-only environment inside the acceptance VM: simulated public DNS for *.schule.test
# (dnsmasq on the guest address) and a local ACME CA (Pebble v2.10.1 binary, no Docker).
# Run as root BEFORE the installer; it never installs Docker, nginx or a database.
set -euo pipefail
GUEST=10.0.2.15
UPSTREAM=10.0.2.3
HOSTS=/etc/sp-test-hosts
P=/opt/pebble

# --- DNS -------------------------------------------------------------------------
if [ ! -f /etc/systemd/system/sp-test-dns.service ]; then
  DEBIAN_FRONTEND=noninteractive apt-get update -q
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends dnsmasq-base
  touch "$HOSTS"
  printf 'listen-address=%s\nbind-interfaces\nno-resolv\nserver=%s\naddn-hosts=%s\nlocal=/schule.test/\nuser=nobody\n' \
    "$GUEST" "$UPSTREAM" "$HOSTS" > /etc/sp-test-dns.conf
  printf '%s\n' '[Unit]' 'Description=Test-only DNS for *.schule.test (simulates the provider DNS)' \
    'After=network-online.target' '[Service]' \
    'ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/etc/sp-test-dns.conf' \
    'ExecReload=/bin/kill -HUP $MAINPID' 'Restart=on-failure' '[Install]' 'WantedBy=multi-user.target' \
    > /etc/systemd/system/sp-test-dns.service
  systemctl daemon-reload
  systemctl enable --now sp-test-dns.service
fi
grep -q "acme.schule.test" "$HOSTS" || echo "$GUEST acme.schule.test" >> "$HOSTS"
systemctl reload-or-restart sp-test-dns.service
mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNS=%s\nDomains=~.\n' "$GUEST" > /etc/systemd/resolved.conf.d/schulplattform-test.conf
systemctl restart systemd-resolved

# --- Pebble ----------------------------------------------------------------------
if [ ! -x $P/pebble ]; then
  mkdir -p $P
  tar -xzf /root/pebble-linux-amd64.tar.gz -C /tmp
  install -m 0755 /tmp/pebble-linux-amd64/linux/amd64/pebble $P/pebble
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 30 -subj "/CN=Schulplattform Test ACME CA" \
    -keyout $P/ca.key -out $P/ca.pem 2>/dev/null
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj "/CN=acme.schule.test" \
    -keyout $P/key.pem -out $P/server.csr 2>/dev/null
  printf 'subjectAltName=DNS:acme.schule.test\n' > $P/ext.cnf
  openssl x509 -req -in $P/server.csr -CA $P/ca.pem -CAkey $P/ca.key -CAcreateserial -days 30 \
    -extfile $P/ext.cnf -out $P/cert.pem 2>/dev/null
  cat > $P/pebble.json <<EOF
{"pebble": {"listenAddress": "0.0.0.0:14000", "managementListenAddress": "0.0.0.0:15000",
  "certificate": "$P/cert.pem", "privateKey": "$P/key.pem", "httpPort": 80, "tlsPort": 443,
  "ocspResponderURL": "", "externalAccountBindingRequired": false,
  "retryAfter": {"authz": 3, "order": 5}, "certificateValidityPeriod": 7776000}}
EOF
  cat > /etc/systemd/system/sp-test-pebble.service <<EOF
[Unit]
Description=Test-only ACME CA (Pebble) for Schulplattform acceptance
After=network-online.target sp-test-dns.service
[Service]
Environment=PEBBLE_VA_NOSLEEP=1 PEBBLE_WFE_NONCEREJECT=0 PEBBLE_AUTHZREUSE=0
ExecStart=$P/pebble -config $P/pebble.json -dnsserver $GUEST:53
ExecStartPost=/bin/sh -c 'sleep 2; curl -sk https://127.0.0.1:15000/roots/0 >> $P/issued-roots.pem'
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now sp-test-pebble.service
fi
# Containers reach DNS and the test CA on the guest address; the platform's ufw policy
# would otherwise reject them. These two rules are test-only and documented.
ufw allow from 172.16.0.0/12 to $GUEST port 53 proto udp >/dev/null
ufw allow from 172.16.0.0/12 to $GUEST port 14000 proto tcp >/dev/null
ufw allow from 10.231.0.0/16 to $GUEST port 53 proto udp >/dev/null
ufw allow from 10.231.0.0/16 to $GUEST port 14000 proto tcp >/dev/null
sleep 2
curl -sf --cacert $P/ca.pem https://acme.schule.test:14000/dir >/dev/null && echo "pebble: directory reachable"
getent hosts acme.schule.test
