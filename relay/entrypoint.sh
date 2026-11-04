#!/bin/sh
# Generate the relay configuration from environment and secret files, then run
# postfix in the foreground. Never prints credentials.
set -eu
: "${RELAY_UPSTREAM_HOST:?upstream host required}"
: "${RELAY_UPSTREAM_PORT:?upstream port required}"
: "${RELAY_SECURITY:?starttls or tls required}"
: "${RELAY_SENDER:?sender address required}"
: "${RELAY_NETWORKS:?client networks required}"
case "$RELAY_SECURITY" in starttls|tls) ;; *) echo "relay: invalid RELAY_SECURITY" >&2; exit 64;; esac
printf '%s' "$RELAY_UPSTREAM_HOST" | grep -Eq '^[a-z0-9.-]+$' || { echo "relay: invalid upstream host" >&2; exit 64; }
printf '%s' "$RELAY_UPSTREAM_PORT" | grep -Eq '^[0-9]{1,5}$' || { echo "relay: invalid upstream port" >&2; exit 64; }
printf '%s' "$RELAY_SENDER" | grep -Eq '^[^@[:space:]<>]+@[a-z0-9.-]+$' || { echo "relay: invalid sender" >&2; exit 64; }
printf '%s' "$RELAY_NETWORKS" | grep -Eq '^[0-9a-f.:/ ]+$' || { echo "relay: invalid client networks" >&2; exit 64; }

conf=/etc/postfix
chown postfix:postfix /var/lib/postfix
chmod 0700 /var/lib/postfix
install -d -m 0755 "$conf"
# /etc/postfix is a tmpfs on a read-only root filesystem; restore the packaged files.
cp -a /usr/share/schulplattform-relay/etc-postfix/. "$conf/"
# Listen only on the internal port used by the apps; disable the public port 25 listener.
sed -i -E 's/^smtp( +)inet/#smtp\1inet/' "$conf/master.cf"
printf '1025      inet  n       -       n       -       -       smtpd\n' >> "$conf/master.cf"
# No chroot: the container is the isolation boundary and the chroot would lack resolv.conf/CA files.
awk 'BEGIN{OFS="  "} /^[a-z0-9]/ && NF>=8 {$5="n"} {print}' "$conf/master.cf" > "$conf/master.cf.new"
mv "$conf/master.cf.new" "$conf/master.cf"

if [ "$RELAY_SECURITY" = "tls" ]; then wrapper=yes; else wrapper=no; fi
sender_name="${RELAY_SENDER_NAME:-Schulplattform}"
cat > "$conf/main.cf" <<CONF
compatibility_level = 3.6
myhostname = relay.schulplattform.invalid
mydestination =
local_transport = error:local delivery disabled
inet_interfaces = all
inet_protocols = ipv4
mynetworks = 127.0.0.0/8 $RELAY_NETWORKS
smtpd_relay_restrictions = permit_mynetworks, reject
smtpd_recipient_restrictions = permit_mynetworks, reject
smtpd_client_connection_count_limit = 20
smtpd_client_message_rate_limit = 600
message_size_limit = 26214400
relayhost = [$RELAY_UPSTREAM_HOST]:$RELAY_UPSTREAM_PORT
smtp_tls_security_level = secure
smtp_tls_wrappermode = $wrapper
smtp_tls_CAfile = ${RELAY_CA_FILE:-/etc/ssl/certs/ca-certificates.crt}
smtp_tls_mandatory_protocols = >=TLSv1.2
sender_canonical_maps = regexp:$conf/sender_canonical
smtp_header_checks = regexp:$conf/header_checks
maillog_file = /dev/stdout
bounce_queue_lifetime = 1d
maximal_queue_lifetime = 3d
CONF
printf '/.+/ %s\n' "$RELAY_SENDER" > "$conf/sender_canonical"
# Headers that would let an app impersonate another sender are normalised.
printf '/^From:.*/ REPLACE From: %s <%s>\n/^Sender:.*/ IGNORE\n' "$sender_name" "$RELAY_SENDER" > "$conf/header_checks"

if [ -n "${RELAY_USERNAME:-}" ]; then
  [ -r /run/secrets/smtp-password ] || { echo "relay: password file missing" >&2; exit 64; }
  umask 077
  printf '[%s]:%s %s:%s\n' "$RELAY_UPSTREAM_HOST" "$RELAY_UPSTREAM_PORT" "$RELAY_USERNAME" \
    "$(cat /run/secrets/smtp-password)" > "$conf/sasl_passwd"
  postmap "hash:$conf/sasl_passwd"
  rm -f "$conf/sasl_passwd"
  cat >> "$conf/main.cf" <<CONF
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:$conf/sasl_passwd
smtp_sasl_security_options = noanonymous
smtp_sasl_tls_security_options = noanonymous
CONF
fi
postfix -c "$conf" check
exec postfix -c "$conf" start-fg
