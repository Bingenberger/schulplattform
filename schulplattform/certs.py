"""Read certificate state from Caddy's persistent data directory (host bind mount)."""
from datetime import datetime, timezone
import json
from pathlib import Path

from cryptography import x509


def find(data_dir, hostname):
    """Return the newest certificate Caddy stored for hostname, or None."""
    base = Path(data_dir) / "caddy/certificates"
    if not base.is_dir():
        return None
    candidates = [path for path in base.glob(f"*/{hostname}/{hostname}.crt") if path.is_file() and not path.is_symlink()]
    best = None
    for path in candidates:
        try:
            certificate = x509.load_pem_x509_certificates(path.read_bytes())[0]
        except (ValueError, IndexError):
            continue
        if best is None or certificate.not_valid_after_utc > best[1].not_valid_after_utc:
            best = (path, certificate)
    if not best:
        return None
    path, certificate = best
    try:
        names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value \
            .get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        names = []
    issuer = certificate.issuer.rfc4514_string()
    meta = path.with_suffix(".json")
    issuer_key = path.parent.parent.name
    try:
        renewed = json.loads(meta.read_text()).get("issuer_data", {}) if meta.exists() else {}
    except ValueError:
        renewed = {}
    now = datetime.now(timezone.utc)
    return {"hostname": hostname, "issuer": issuer, "issuerDirectory": issuer_key,
            "notBefore": certificate.not_valid_before_utc.isoformat(),
            "notAfter": certificate.not_valid_after_utc.isoformat(),
            "daysLeft": int((certificate.not_valid_after_utc - now).total_seconds() // 86400),
            "coversHostname": hostname in names, "staging": "staging" in issuer_key or "STAGING" in issuer,
            "valid": certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc and hostname in names,
            "url": renewed.get("url", "") if isinstance(renewed, dict) else ""}
