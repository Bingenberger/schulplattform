"""Installer CLI: read-only preflight, signed release planning and production apply.

Production commands (root on Ubuntu 24.04):
  configure [--check]          create/validate /etc/schulplattform/platform.toml (console wizard)
  preflight                    read-only host inventory and blockers
  plan    --bundle B --trusted-key K
  apply   --bundle B --trusted-key K [--reconfigure]
  status | reconcile [--app X] | domain-change APP HOST | start APP | stop APP
  admin-setup | app-setup APP | smtp-password | backup [--app X|--all] | restore-probe APP
The local pilot commands (pilot-*) remain for development.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys

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
        'platformOwnsDocker': _platform_owns_docker(),
    }


def _platform_owns_docker(root=Path('/var/lib/schulplattform')):
    try:
        return json.loads((root / 'state/host.json').read_text()).get('dockerInstalledByPlatform') is True
    except (OSError, ValueError):
        return False


def blockers(host):
    issues = []
    if (host['os'], host['version'], host['architecture']) != ('ubuntu', '24.04', 'x86_64'):
        issues.append('Requires Ubuntu 24.04 amd64')
    if not host['root']:
        issues.append('Installation requires root; inventory itself is read-only')
    owned = host.get('platformOwnsDocker', False)
    if (host['dockerInstalled'] and not owned) or any(v == 'active' for v in host['services'].values()):
        issues.append('Existing Docker/proxy/database installation: explicit takeover plan required')
    if any(value != 'free' for value in host['ports'].values()) and not owned:
        issues.append('Ports 80/443 are not available')
    if host['ntpSynchronized'] != 'yes':
        issues.append('NTP synchronization not confirmed')
    return issues


def warnings(host):
    """Sizing is an estimate (scope decision), so it warns instead of blocking."""
    notes = []
    if host['memory']['MemTotal'] < 15 * 1024**3:
        notes.append('Less than the estimated 16 GB host profile (estimate, not measured)')
    if host['diskFreeBytes'] < 160 * 1000**3:
        notes.append('Less than the estimated 160 GB free disk profile (estimate, not measured)')
    if not host['memory'].get('SwapTotal'):
        notes.append('No swap configured')
    return notes


PRODUCTION = ["configure", "plan", "apply", "status", "reconcile", "domain-change", "start", "stop",
              "admin-setup", "app-setup", "smtp-password", "backup", "restore-probe", "restore"]


def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["preflight", *PRODUCTION, "pilot-up", "pilot-start", "pilot-stop",
                                           "pilot-status"])
    parser.add_argument("target", nargs="*", help="APP [HOSTNAME] for app-specific commands")
    parser.add_argument("--state-dir", type=Path, default=Path(".work/pilot-v2"))
    parser.add_argument("--apps", help="Pilot app selection; requires a new installation directory")
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--trusted-key', type=Path)
    parser.add_argument('--config', type=Path, default=Path('/etc/schulplattform/platform.toml'))
    parser.add_argument('--root', type=Path, default=Path('/var/lib/schulplattform'))
    parser.add_argument('--check', action='store_true', help='configure: validate only')
    parser.add_argument('--reconfigure', action='store_true', help='apply: accept a changed plan, keep data')
    parser.add_argument('--app', help='reconcile/backup: limit to one app')
    parser.add_argument('--all', action='store_true', help='backup: every installed app')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--confirm-replace', action='store_true', help="restore: replace this app's data")
    parser.add_argument('--no-host', action='store_true', help=argparse.SUPPRESS)
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
        print(json.dumps({'observed': host, 'blockers': issues, 'warnings': warnings(host)}, indent=2))
        return 1 if issues else 0
    if args.action == 'configure':
        from . import config as cfg
        if args.check:
            cfg.load(args.config)
            print(f"{args.config}: gültig")
            return 0
        existing = cfg.load(args.config) if args.config.exists() else None
        cfg.wizard(args.config, existing)
        print(f"Konfiguration gespeichert: {args.config}")
        return 0
    if not args.bundle or not args.trusted_key:
        bundle, key = _installed_release(args.root)
        args.bundle = args.bundle or bundle
        args.trusted_key = args.trusted_key or key
    if not args.bundle or not args.trusted_key:
        parser.error('--bundle and --trusted-key are required; the key must be provisioned independently')
    try:
        bundle = verify_bundle(args.bundle, args.trusted_key)
    except ValidationError:
        parser.exit(1, 'Release blocked: manifest does not match schema version 1.\n')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Release blocked: {exc}\n')
    if args.action == 'plan':
        from .release_bundle import Release, key_fingerprint
        report = {'status': 'signature-and-manifests-verified', 'release': bundle.release,
                  'bundleDigest': bundle.digest, 'trustedKey': key_fingerprint(args.trusted_key),
                  'apps': [m['id'] for m in bundle.manifests]}
        try:
            release = Release(args.bundle, args.trusted_key)
            report.update(deployable=True, images=release.images,
                          openAcceptanceItems=[list(i) for i in release.open_items()])
        except (ValueError, KeyError) as exc:
            report.update(deployable=False, reason=str(exc))
        print(json.dumps(report, indent=2))
        return 0
    from .production import Platform
    if args.action == 'apply':
        host = inventory()
        issues = [i for i in blockers(host) if not (args.no_host and 'root' in i)]
        if issues and not host.get('platformOwnsDocker'):
            print(json.dumps({'blockers': issues, 'warnings': warnings(host)}, indent=2), file=sys.stderr)
            parser.exit(1, 'Installation blocked by preflight; nothing was changed.\n')
        platform_ = Platform(args.config, args.root, args.bundle, args.trusted_key, provision_host=not args.no_host)
        for app, item, summary in platform_.release.open_items():
            print(f"OFFEN  {app:18} {item:15} {summary}")
        result = platform_.apply(reconfigure=args.reconfigure)
        _print_status(platform_, result)
        return 0
    platform_ = Platform(args.config, args.root, args.bundle, args.trusted_key, provision_host=False)
    target = args.target
    if args.action == 'status':
        _print_status(platform_, None)
    elif args.action == 'reconcile':
        platform_.router().reconcile(only={args.app} if args.app else None,
                                     wait_seconds=int(os.environ.get('SP_CERT_WAIT', '150')))
        if not args.quiet:
            _print_status(platform_, None)
    elif args.action == 'domain-change':
        if len(target) != 2:
            parser.error('domain-change APP HOSTNAME')
        platform_.change_domain(target[0], target[1])
        _print_status(platform_, None)
    elif args.action in ('start', 'stop'):
        from .deployment_service import ProductionEngine
        if len(target) != 1:
            parser.error(f'{args.action} APP')
        engine = ProductionEngine(lambda: Platform(args.config, args.root, args.bundle, args.trusted_key,
                                                   provision_host=False))
        print(json.dumps(engine.execute(args.action, target[0]), indent=2, ensure_ascii=False))
    elif args.action == 'admin-setup':
        platform_.setup_dashboard_admin(target[0] if target else None)
        _mark_bootstrap(platform_, dashboardAdmin=True)
    elif args.action == 'app-setup':
        if len(target) != 1:
            parser.error('app-setup APP')
        from .appsetup import setup_app
        setup_app(platform_, target[0])
        _mark_bootstrap(platform_, app=target[0])
    elif args.action == 'smtp-password':
        import getpass
        from .secrets import SecretStore
        with open('/dev/tty', 'r+') as tty:
            first = getpass.getpass('SMTP-Passwort (Eingabe unsichtbar): ', stream=tty)
            second = getpass.getpass('Wiederholen: ', stream=tty)
        if not first or first != second:
            parser.exit(1, 'Passwörter stimmen nicht überein; nichts geändert.\n')
        SecretStore(platform_.layout.secrets).replace('smtp-password', first)
        print('SMTP-Passwort gespeichert.')
    elif args.action == 'backup':
        from .backups import BackupService
        service = BackupService(platform_)
        apps = platform_.stack.apps if args.all or not (args.app or target) else [args.app or target[0]]
        failures = 0
        for app in apps:
            try:
                result = service.backup(app)
                if not args.quiet:
                    print(json.dumps(result, ensure_ascii=False))
            except Exception as exc:
                failures += 1
                service._record(app, lastFailure=_now(), failure=type(exc).__name__)
                print(f"{app}: Sicherung fehlgeschlagen ({type(exc).__name__})", file=sys.stderr)
        return 1 if failures else 0
    elif args.action == 'restore':
        from .backups import BackupService, restore
        if len(target) != 2:
            parser.error('restore APP ARCHIVE --confirm-replace')
        facts = restore(BackupService(platform_), target[0], Path(target[1]), confirm=args.confirm_replace)
        print(json.dumps(facts, indent=2, ensure_ascii=False))
    elif args.action == 'restore-probe':
        from .backups import BackupService
        if len(target) != 1:
            parser.error('restore-probe APP')
        print(json.dumps(BackupService(platform_).restore_probe(target[0]), indent=2, ensure_ascii=False))
    return 0


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _installed_release(root):
    state = Path(root) / 'state/installation.json'
    key = Path(root) / 'state/release-trust.pub'
    if not state.exists() or not key.exists():
        return None, None
    try:
        version = json.loads((Path(root) / 'state/verified.json').read_text())['release']
    except (OSError, ValueError, KeyError):
        return None, None
    return Path(root) / 'releases' / version, key


def _mark_bootstrap(platform_, dashboardAdmin=None, app=None):
    from .storage import atomic_json
    path = platform_.layout.state / 'bootstrap.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    if dashboardAdmin:
        data['dashboardAdmin'] = True
    if app:
        data.setdefault('appSetup', {})[app] = True
    atomic_json(path, data)


def _print_status(platform_, result):
    from .routing import MANAGEMENT
    status = platform_.router().load()
    domains = platform_.current_domains()
    ip4 = platform_.config['platform']['public_ipv4']
    ip6 = platform_.config['platform'].get('public_ipv6')
    lines = []
    if result:
        lines.append(f"Installation {result['id']}: {result['status']} (Release {platform_.release.version})")
    for key in [MANAGEMENT, *platform_.stack.apps]:
        entry = status.get(key, {})
        name = 'verwaltung' if key == MANAGEMENT else key
        host = entry.get('hostname') or (domains.get(key) if key != MANAGEMENT
                                         else platform_.config['platform']['management_domain'])
        health = '' if key == MANAGEMENT else ('läuft' if platform_.stack.healthy(key) else 'nicht bereit')
        cert = entry.get('certificate') or {}
        expiry = f" Zertifikat bis {cert['notAfter'][:10]}" if cert.get('valid') else ''
        lines.append(f"  {name:18} {host:40} {entry.get('phase', 'unbekannt'):22} {health}{expiry}")
        if entry.get('phase') == 'dns-ausstehend':
            wanted = f"A {ip4}" + (f" / AAAA {ip6}" if ip6 else '')
            lines.append(f"  {'':18} -> DNS beim Provider setzen: {host}  {wanted}   ({entry.get('reason', '')})")
    bootstrap = platform_.layout.state / 'bootstrap.json'
    if bootstrap.exists():
        data = json.loads(bootstrap.read_text())
        if not data.get('dashboardAdmin'):
            lines.append("Nächster Schritt: ./install.sh admin-setup   (persönlicher Plattform-Admin mit TOTP)")
        pending = [app for app, done in data.get('appSetup', {}).items() if not done]
        if pending:
            lines.append("Erstzugang je App bei Bedarf: ./install.sh app-setup <app>   offen: " + ", ".join(pending))
    print("\n".join(lines))


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
