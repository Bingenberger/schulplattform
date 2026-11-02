"""Explicit Caddy routes; no discovery or Docker socket."""
import ipaddress
import re


def hostname(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.lower():
        raise ValueError('Expected a lowercase DNS hostname')
    if '.' not in value or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p)
                               for p in value.split('.')):
        raise ValueError('Invalid DNS hostname')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError('IP literals are not domains')


def caddyfile(routes):
    lines = ['{', '  admin localhost:2019', '}', '']
    seen = set()
    for app_id, domain, port in routes:
        hostname(domain)
        if domain in seen:
            raise ValueError('Duplicate domain')
        seen.add(domain)
        if not re.fullmatch('[a-z][a-z0-9-]{0,40}', app_id) or not 1024 <= port <= 65535:
            raise ValueError('Invalid upstream')
        lines += [f'{domain} {{', '  route {', '    request_header {',
                  '      -Forwarded', '      -X-Forwarded-*', '      -X-Real-IP',
                  '      -Remote-User', '      -Remote-Groups', '      -Remote-Email',
                  '      -X-Auth-*', '      -X-Remote-*',
                  '    }', f'    reverse_proxy {app_id}:{port}', '  }', '}', '']
    return '\n'.join(lines)
