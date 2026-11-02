"""Read-only host inventory and fail-closed release planning.

Provisioning is intentionally unavailable until an accepted release bundle exists.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess

from .bundle import verify_bundle
from jsonschema.exceptions import ValidationError


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inventory():
    os_release = platform.freedesktop_os_release()
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal'):
            memory[key] = int(value.split()[0]) * 1024
    ports = {}
    for port in (80, 443):
        with socket.socket() as listener:
            try:
                listener.bind(('0.0.0.0', port))
                ports[str(port)] = 'free'
            except OSError:
                ports[str(port)] = 'occupied-or-unavailable'
    return {
        'os': os_release.get('ID'), 'version': os_release.get('VERSION_ID'),
        'architecture': platform.machine(), 'root': os.geteuid() == 0,
        'memory': memory, 'diskFreeBytes': shutil.disk_usage('/').free,
        'ports': ports, 'dockerInstalled': bool(shutil.which('docker')),
        'dockerVersion': command(['docker', 'version', '--format', '{{.Server.Version}}']),
        'composeVersion': command(['docker', 'compose', 'version', '--short']),
        'containers': command(['docker', 'ps', '-a', '--format', '{{.Names}}']),
        'volumes': command(['docker', 'volume', 'ls', '--format', '{{.Name}}']),
        'services': {name: command(['systemctl', 'is-active', name])
                     for name in ('nginx', 'apache2', 'caddy', 'postgresql', 'mysql')},
        'ntpSynchronized': command(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value']),
    }


def blockers(host):
    issues = []
    if (host['os'], host['version'], host['architecture']) != ('ubuntu', '24.04', 'x86_64'):
        issues.append('Requires Ubuntu 24.04 amd64')
    if not host['root']:
        issues.append('Installation requires root; inventory itself is read-only')
    if host['dockerInstalled'] or any(v == 'active' for v in host['services'].values()):
        issues.append('Existing Docker/proxy/database installation: explicit takeover plan required')
    if any(value != 'free' for value in host['ports'].values()):
        issues.append('Ports 80/443 are not available')
    if host['memory']['MemTotal'] < 15 * 1024**3:
        issues.append('Less than the estimated 16 GB host profile')
    if host['diskFreeBytes'] < 160 * 1000**3:
        issues.append('Less than the estimated 160 GB free disk profile')
    if host['ntpSynchronized'] != 'yes':
        issues.append('NTP synchronization not confirmed')
    return issues


def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "plan", "apply", "pilot-up", "pilot-start", "pilot-stop", "pilot-status"])
    parser.add_argument("--state-dir", type=Path, default=Path(".work/pilot-v2"))
    parser.add_argument("--apps", help="Pilot app selection; requires a new installation directory")
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--trusted-key', type=Path)
    args = parser.parse_args(argv)
    if args.action.startswith("pilot-"):
        from .pilot import Pilot
        selected = tuple(args.apps.split(",")) if args.apps else None
        pilot = Pilot(args.state_dir, apps=selected)
        if args.action in ("pilot-up", "pilot-start"):
            result = pilot.up() if args.action == "pilot-up" else pilot.start()
            print(json.dumps({"mode": "local-pilot", "status": result["status"], "id": result["id"],
                              "tlsPort": pilot.config["port"], "productionReady": False}, indent=2))
        elif args.action == "pilot-stop":
            pilot.stop()
            print("Pilot stopped; volumes and keys retained.")
        else:
            print(json.dumps({"ready": pilot.ready(None), "productionReady": False}, indent=2))
        return 0
    if args.action == 'preflight':
        host = inventory()
        issues = blockers(host)
        print(json.dumps({'observed': host, 'blockers': issues}, indent=2))
        return 1 if issues else 0
    if not args.bundle or not args.trusted_key:
        parser.error('--bundle and --trusted-key are required; the key must be provisioned independently')
    try:
        bundle = verify_bundle(args.bundle, args.trusted_key)
        manifests = bundle.manifests
    except ValidationError:
        parser.exit(1, 'Release blocked: manifest does not match schema version 1.\n')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Release blocked: {exc}\n')
    if args.action == 'apply':
        parser.exit(1, 'Release blocked: host provisioning/bootstrap/verification not yet implemented. No changes applied.\n')
    print(json.dumps({'status': 'signature-and-manifests-verified', 'release': bundle.release,
                      'bundleDigest': bundle.digest, 'apps': [m['id'] for m in manifests],
                      'deployable': False}, indent=2))
    return 0



def main(argv=None):
    import sys
    from .state import StateError
    try:
        return _main(argv)
    except BlockingIOError:
        print("Plattform: Eine andere Verwaltungsaktion läuft; bitte später erneut versuchen.", file=sys.stderr)
        return 1
    except StateError as exc:
        print("Plattform: " + str(exc), file=sys.stderr)
        return 1
    except (ValueError, OSError):
        print("Plattform: Konfiguration oder Dienstzugriff fehlgeschlagen; private Betriebsprotokolle prüfen.", file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
