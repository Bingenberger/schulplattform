"""Explicit Caddy routes; no discovery or Docker socket."""
import ipaddress
import re


def hostname(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.lower():
        raise ValueError("Expected a lowercase DNS hostname")
    if "." not in value or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", p)
                               for p in value.split(".")):
        raise ValueError("Invalid DNS hostname")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("IP literals are not domains")


TRUST_HEADERS = ["Forwarded", "X-Forwarded-*", "X-Real-IP", "Remote-User", "Remote-Groups",
                 "Remote-Email", "X-Auth-*", "X-Remote-*"]
ACME_DIRECTORIES = {"staging": "https://acme-staging-v02.api.letsencrypt.org/directory",
                    "production": "https://acme-v02.api.letsencrypt.org/directory"}
CHECK_PREFIX = "/.well-known/schulplattform-check/"


def production_caddyfile(routes, management, email, environment, acme_ca=None, custom_root=None):
    """Explicit Caddy configuration with ACME (HTTP-01/TLS-ALPN-01), one certificate per hostname.

    routes: [(hostname, "alias:port" | None)]; None serves a maintenance 503.
    Only hostnames whose DNS check passed are passed in, so Caddy never retries
    certificate orders for names that do not point to this server yet.
    """
    if environment not in ("staging", "production", "custom"):
        raise ValueError("Unknown ACME environment")
    if not re.fullmatch(r"[^@\s{}\"]{1,64}@[a-z0-9.-]{1,253}", email or ""):
        raise ValueError("Invalid ACME contact")
    directory = acme_ca if environment == "custom" else ACME_DIRECTORIES[environment]
    if not re.fullmatch(r"https://[a-zA-Z0-9.:/_-]{1,240}", directory or ""):
        raise ValueError("Invalid ACME directory")
    lines = ["{", "  admin localhost:2019", f"  email {email}", f"  acme_ca {directory}"]
    if custom_root:
        lines.append(f"  acme_ca_root {custom_root}")
    lines += ["  servers {", "    protocols h1 h2", "  }", "}", "",
              "# Port 80: ACME HTTP-01 is answered by Caddy itself; the check path proves reachability.",
              "http:// {", f"  handle {CHECK_PREFIX}* {{", "    root * /srv/check", "    file_server", "  }",
              "  handle {", "    redir https://{host}{uri} 308", "  }", "}", ""]
    seen = set()
    entries = list(routes) + ([management] if management else [])
    for domain, upstream in entries:
        hostname(domain)
        if domain in seen:
            raise ValueError("Duplicate domain")
        seen.add(domain)
        lines += [f"{domain} {{", "  route {"]
        lines += [f"    request_header -{header}" for header in TRUST_HEADERS]
        if upstream is None:
            lines.append('    respond "Wartung" 503')
        else:
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,40}:[0-9]{2,5}", upstream):
                raise ValueError("Invalid upstream")
            lines.append(f"    reverse_proxy {upstream}")
        lines += ["  }", "  header {", "    Strict-Transport-Security \"max-age=31536000\"", "    -Server", "  }",
                  "}", ""]
    return "\n".join(lines)


def caddyfile(routes):
    lines = ["{", "  admin localhost:2019", "}", ""]
    seen = set()
    for app_id, domain, port in routes:
        hostname(domain)
        if domain in seen:
            raise ValueError("Duplicate domain")
        seen.add(domain)
        if not re.fullmatch("[a-z][a-z0-9-]{0,40}", app_id) or not 1024 <= port <= 65535:
            raise ValueError("Invalid upstream")
        lines += [f"{domain} {{", "  route {"]
        for header in ["Forwarded", "X-Forwarded-*", "X-Real-IP", "Remote-User",
                       "Remote-Groups", "Remote-Email", "X-Auth-*", "X-Remote-*"]:
            lines.append(f"    request_header -{header}")
        lines += [f"    reverse_proxy {app_id}:{port}", "  }", "}", ""]
    return "\n".join(lines)
