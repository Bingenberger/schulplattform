# Outbound-only mail relay for the platform: apps hand mail to this container on
# their internal proxy network (no authentication, no internet listener); it
# queues durably and delivers to the configured upstream with TLS and SASL.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends postfix libsasl2-modules ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/share/schulplattform-relay \
    && rm -f /etc/postfix/main.cf /etc/postfix/sasl_passwd* \
    && cp -a /etc/postfix /usr/share/schulplattform-relay/etc-postfix
COPY entrypoint.sh /usr/local/bin/relay-entrypoint
RUN chmod 0755 /usr/local/bin/relay-entrypoint
EXPOSE 1025
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD postfix -c /etc/postfix status >/dev/null 2>&1
ENTRYPOINT ["/usr/local/bin/relay-entrypoint"]
