"""DNS and reachability checks before any certificate order.

The server's own public address comes from the operator's configuration (the
hoster's documentation), not from an external "what is my IP" service. Names
are resolved through the host resolver and, if configured, additionally
through explicitly listed resolvers using a minimal stub client; all answers
must agree. A hostname is "ok" only if every A record equals public_ipv4 and
AAAA records are either absent (when no IPv6 is configured) or equal
public_ipv6 - Let's Encrypt prefers IPv6, so a stray AAAA record breaks
validation even when the A record is right.
"""
import ipaddress
import os
from pathlib import Path
import secrets
import socket
import struct

CHECK_DIR = ".well-known/schulplattform-check"


def system_resolve(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return {"A": [], "AAAA": []}
    result = {"A": set(), "AAAA": set()}
    for family, *_rest, address in infos:
        if family == socket.AF_INET:
            result["A"].add(address[0])
        elif family == socket.AF_INET6:
            result["AAAA"].add(ipaddress.IPv6Address(address[0]).compressed)
    return {key: sorted(value) for key, value in result.items()}


def _encode_name(hostname):
    out = b""
    for label in hostname.rstrip(".").split("."):
        raw = label.encode("ascii")
        if not 0 < len(raw) < 64:
            raise ValueError("Invalid label")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def _skip_name(message, offset):
    while True:
        length = message[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            return offset + 2
        offset += 1 + length


def query(resolver, hostname, rtype, timeout=3.0):
    """Minimal recursive-desired DNS query over UDP; returns sorted addresses."""
    code = {"A": 1, "AAAA": 28}[rtype]
    identifier = secrets.randbits(16)
    packet = struct.pack(">HHHHHH", identifier, 0x0100, 1, 0, 0, 0) + _encode_name(hostname) + struct.pack(">HH", code, 1)
    family = socket.AF_INET6 if ":" in resolver else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (resolver, 53))
        message, _ = sock.recvfrom(4096)
    ident, flags, qdcount, ancount, _ns, _ar = struct.unpack(">HHHHHH", message[:12])
    if ident != identifier or not flags & 0x8000:
        raise OSError("Unexpected DNS response")
    rcode = flags & 0x000F
    if rcode == 3:
        return []
    if rcode != 0:
        raise OSError(f"DNS error rcode {rcode}")
    offset = 12
    for _ in range(qdcount):
        offset = _skip_name(message, offset) + 4
    addresses = set()
    for _ in range(ancount):
        offset = _skip_name(message, offset)
        atype, _cls, _ttl, length = struct.unpack(">HHIH", message[offset:offset + 10])
        offset += 10
        data = message[offset:offset + length]
        offset += length
        if atype == code == 1 and length == 4:
            addresses.add(str(ipaddress.IPv4Address(data)))
        elif atype == code == 28 and length == 16:
            addresses.add(ipaddress.IPv6Address(data).compressed)
    return sorted(addresses)


def evaluate(hostname, public_ipv4, public_ipv6=None, resolvers=(), resolve=system_resolve, ask=query):
    answers = {"system": resolve(hostname)}
    for resolver in resolvers:
        try:
            answers[resolver] = {"A": ask(resolver, hostname, "A"), "AAAA": ask(resolver, hostname, "AAAA")}
        except (OSError, ValueError):
            answers[resolver] = None
    expected_v6 = ipaddress.IPv6Address(public_ipv6).compressed if public_ipv6 else None
    unreachable = [name for name, answer in answers.items() if answer is None]
    distinct = {(tuple(a["A"]), tuple(a["AAAA"])) for a in answers.values() if a is not None}
    if len(distinct) == 1:
        a_tuple, aaaa_tuple = next(iter(distinct))
        a_records, aaaa_records = list(a_tuple), list(aaaa_tuple)
    else:
        a_records, aaaa_records = [], []
    if unreachable:
        verdict, reason = "error", "Resolver nicht erreichbar: " + ", ".join(unreachable)
    elif len(distinct) > 1:
        verdict, reason = "pending", "Resolver liefern unterschiedliche Antworten (TTL/Propagation abwarten)"
    elif not a_records and not aaaa_records:
        verdict, reason = "pending", "Kein A-/AAAA-Eintrag vorhanden"
    elif a_records != [public_ipv4]:
        verdict, reason = "wrong", f"A-Eintrag zeigt auf {', '.join(a_records) or '–'} statt {public_ipv4}"
    elif aaaa_records and aaaa_records != ([expected_v6] if expected_v6 else []):
        verdict, reason = "wrong", (f"AAAA-Eintrag {', '.join(aaaa_records)} zeigt nicht auf diesen Server"
                                    if expected_v6 else "AAAA-Eintrag vorhanden, aber keine IPv6 konfiguriert")
    elif expected_v6 and not aaaa_records:
        verdict, reason = "ok", "A-Eintrag korrekt; kein AAAA-Eintrag (nur IPv4)"
    else:
        verdict, reason = "ok", "DNS zeigt auf diesen Server"
    return {"hostname": hostname, "dns": verdict, "reason": reason, "A": list(a_records),
            "AAAA": list(aaaa_records)}


class ReachabilityProbe:
    """Serve a one-time token through Caddy's port 80 check path and fetch it via the public address."""

    def __init__(self, check_root):
        self.root = Path(check_root) / CHECK_DIR

    def probe(self, hostname, address, port=80, timeout=5.0):
        import http.client
        self.root.mkdir(parents=True, exist_ok=True, mode=0o755)
        token = secrets.token_hex(16)
        path = self.root / token
        path.write_text(token)
        os.chmod(path, 0o644)
        try:
            connection = http.client.HTTPConnection(address, port, timeout=timeout)
            connection.request("GET", f"/{CHECK_DIR}/{token}", headers={"Host": hostname})
            response = connection.getresponse()
            body = response.read(256).decode(errors="replace")
            return "ok" if response.status == 200 and body == token else "unverified"
        except OSError:
            return "unverified"
        finally:
            path.unlink(missing_ok=True)
