"""Import of data exported from the old server (scripts/altserver/schulplattform_altserver.py).

  ./install.sh import-key                      create the transfer key (copy it securely to the old server)
  ./install.sh import APP ARCHIVE --dry-run    decrypt and report; changes nothing
  ./install.sh import APP ARCHIVE --confirm-replace

The dry run reports source version, storage, schema revision, row counts and
whether a reviewed adoption path exists. The import replaces only that app's
data (restore_directory), carries over link-relevant secrets, runs the app's
explicit migration job (which refuses unknown schemas), starts the app and
compares row counts of every table that existed on the old server.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .backups import BackupService, restore_directory
from .secrets import SecretStore
from .state import StateError

TRANSFER_KEY = "import-transfer-key"

# Known adoption situations per app (from the apps' migration code and UPGRADE.md).
ADOPTION = {
    "schulhelfer": "Unversionierte create_all-Datenbank wird nur über einen geprüften Adoptionspfad übernommen.",
    "fahrradausbildung": "Alembic-Revisionen bis 0008 werden auf 0009 angehoben; unversionierte Datenbanken werden abgewiesen.",
    "abgen": "Drizzle-Journal muss zur bekannten Historie passen; unbekannte Historie wird abgewiesen.",
    "kompetenz-manager": "Nur ein vollständiger, zur Baseline passender Ausgangsstand wird übernommen.",
    "losverkauf": "Bekannte Legacy-Felder werden umgewandelt; IDs und edit_tokens bleiben erhalten; "
                  "Elterntoken unter 32 Zeichen müssen ersetzt und Links neu verteilt werden.",
    "zackboing": "Bestehende Tabellen und Nutzer-IDs bleiben; die Legacy-Migration setzt user_version 1.",
    "grundschultafel": "Benutzer-UUIDs und Notizbücher bleiben; Bilder aus public/assets liegen danach in data/assets; alle melden sich neu an.",
    "leseflux": "AuthSession-Tabelle wird ergänzt; alte JWTs verlangen erneute Anmeldung.",
    "schulwissen": "Django-Migrationen laufen vorwärts; Rollen werden eingerichtet.",
    "gswb": "SQLite user_version wird durch den Migrationsjob gesetzt.",
    "fundkiste": "Tabellen items/requests werden übernommen (claimed_by wird bei Bedarf ergänzt); "
                 "der Team-Schlüssel kommt mit, ausgehängte QR-Codes bleiben gültig.",
    "schuleva": "Bekannte Anhebungen (Rolle lehrer, anon_names, share_grants) laufen idempotent; "
                "eigene Fragebögen ziehen nach data/surveys um; Konten und Freigabelinks bleiben.",
    "schulkasse": "Nummerierte Migrationen laufen weiter; der alte SCHULKASSE_SECRET_KEY muss mitkommen, "
                  "sonst sind die Zwei-Faktor-Geheimnisse nicht mehr lesbar; Belege und brief.toml ziehen mit.",
    "schulanmeldung": "Alembic-Migrationen laufen vorwärts (Altbestand muss gestempelt sein); "
                      "Uploads und Unterschrift ziehen mit; Eltern-Zugangslinks bleiben gültig.",
    "sl-journal": "Verschlüsselte Datenbank wird unverändert übernommen; der Original-Datenbankschlüssel "
                  "kommt als Secret mit. Passwort und Authenticator bleiben, Sitzungen und App-Geräte nicht.",
    "bildergalerie": "Altdatenbank wird nach Strukturprüfung übernommen (IDs, Dateinamen und Konten bleiben); "
                     "Originale, Anzeige- und Vorschaubilder ziehen mit und werden per SHA-256 geprüft; "
                     "alle melden sich neu an.",
}


def create_transfer_key(platform):
    store = SecretStore(platform.layout.secrets)
    path = store.path(TRANSFER_KEY)
    value = store.get_or_create(TRANSFER_KEY)
    return path, value


def decrypt(platform, archive, destination):
    if not Path(archive).is_file():
        raise StateError(f"Archive {archive} not found (check the file name)")
    key = SecretStore(platform.layout.secrets).path(TRANSFER_KEY)
    if not key.exists():
        raise StateError("No transfer key on this server; run './install.sh import-key' first")
    unpacked = Path(destination) / "unpacked"
    unpacked.mkdir(mode=0o700)
    import tarfile
    # Decrypt straight into the extraction (no plaintext copy of a possibly very large archive on disk).
    process = subprocess.Popen(["gpg", "--batch", "--quiet", "--no-tty", "--homedir", str(destination),
                                "--passphrase-file", str(key), "--decrypt", str(archive)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    broken = None
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as tar:
            tar.extractall(unpacked, filter="data")
        while process.stdout.read(1 << 20):
            pass
    except (tarfile.TarError, EOFError) as exc:
        broken = exc
    finally:
        process.stdout.close()
        stderr = process.stderr.read()
        process.wait(timeout=7200)
    if process.returncode:
        # gpg's own message (no key material) tells a wrong key from a truncated or foreign file.
        detail = " ".join(stderr.decode(errors="replace").split())[-300:]
        raise StateError("Archive could not be decrypted (wrong transfer key or modified file)"
                         + (f"; gpg: {detail}" if detail else ""))
    if broken is not None:
        # gpg exits 0 on a truncated file and emits what it got; the tar then breaks off.
        raise StateError(f"Archive is incomplete (interrupted copy?); compare its sha256 with the export: {broken}")
    return unpacked


def report(platform, app_id, work):
    info = json.loads((Path(work) / "backup.json").read_text())
    if info.get("app") != app_id:
        raise StateError("Archive belongs to a different app")
    manifest = platform.release.manifests.get(app_id)
    lines = {"app": app_id, "source": {"host": info.get("sourceHost"), "commit": info.get("sourceCommit"),
                                       "createdAt": info.get("createdAt")},
             "engine": info.get("engine"), "targetEngine": manifest["database"]["engine"] if manifest else None,
             "schema": info.get("schema") or [{"file": s["file"], "userVersion": s.get("userVersion"),
                                                "alembic": s.get("alembic")} for s in info.get("sqlite", [])],
             "volumes": info.get("volumes", []), "carriedSecrets": info.get("secrets", []),
             "tables": {group: len(tables) for group, tables in info.get("counts", {}).items()},
             "rows": {group: sum(v or 0 for v in tables.values()) for group, tables in info.get("counts", {}).items()},
             "adoption": ADOPTION.get(app_id, "")}
    return info, lines


def compare_counts(platform, app_id, info, facts):
    """Every table that existed on the old server must hold at least as many rows afterwards."""
    differences = {}
    if "postgres" in info.get("counts", {}):
        after = facts.get("postgres", {}).get("tables", {})
        for table, rows in info["counts"]["postgres"].items():
            if rows is not None and after.get(table) is not None and after[table] < rows:
                differences[table] = {"before": rows, "after": after[table]}
            elif table not in after:
                differences[table] = {"before": rows, "after": "fehlt"}
    else:
        service = BackupService(platform)
        for group, tables in info.get("counts", {}).items():
            volume, relative = group.split("/", 1)
            after = sqlite_counts(service, app_id, volume, relative)
            for table, rows in tables.items():
                if table not in after:
                    differences[f"{group}:{table}"] = {"before": rows, "after": "fehlt"}
                elif after[table] < rows:
                    differences[f"{group}:{table}"] = {"before": rows, "after": after[table]}
    return differences


def sqlite_counts(service, app_id, volume, relative):
    from .backups import APP_UID, HELPER
    script = ("import json,sqlite3,sys;c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);"
              "t=[r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\")];"
              "print(json.dumps({x:c.execute('SELECT count(*) FROM \"'+x+'\"').fetchone()[0] for x in t}))")
    output = service.stack.command([service.stack.docker, "run", "--rm", "--network", "none", "--read-only",
                                    "--user", APP_UID, "--cap-drop", "ALL", "-v", f"sp-{app_id}_{volume}:/data:ro",
                                    HELPER, "python", "-c", script, f"/data/{relative}"])
    return json.loads(output or "{}")


CHECKSUM_SCRIPT = (
    "import hashlib,json,os,sys\n"
    "files=json.load(open('/manifest.json'))\n"
    "missing,different=[],[]\n"
    "for name,expected in sorted(files.items()):\n"
    "    path=os.path.normpath(os.path.join('/data',name))\n"
    "    if not path.startswith('/data/') or not os.path.isfile(path):\n"
    "        missing.append(name);continue\n"
    "    h=hashlib.sha256()\n"
    "    with open(path,'rb') as f:\n"
    "        for b in iter(lambda:f.read(1<<20),b''):h.update(b)\n"
    "    if h.hexdigest()!=expected:different.append(name)\n"
    "print(json.dumps({'checked':len(files),'missing':missing[:20],'different':different[:20],"
    "'missingCount':len(missing),'differentCount':len(different)}))\n")


def verify_checksums(service, app_id, info, work):
    """Compare every file recorded with SHA-256 in the export against the imported volume."""
    from .backups import APP_UID, HELPER
    results = {}
    for volume, files in info.get("checksums", {}).items():
        manifest = Path(work) / f"checksums-{volume}.json"
        manifest.write_text(json.dumps(files))
        os.chmod(manifest, 0o644)
        output = service.stack.command([service.stack.docker, "run", "--rm", "--network", "none", "--read-only",
                                        "--user", APP_UID, "--cap-drop", "ALL",
                                        "-v", f"sp-{app_id}_{volume}:/data:ro", "-v", f"{manifest}:/manifest.json:ro",
                                        HELPER, "python", "-c", CHECKSUM_SCRIPT], timeout=7200)
        results[volume] = json.loads(output or "{}")
    return results


def run_import(platform, app_id, archive, confirm=False):
    if app_id not in platform.stack.apps:
        raise StateError("App is not installed on this server")
    service = BackupService(platform)
    work = Path(tempfile.mkdtemp(prefix=f".import-{app_id}-", dir=platform.layout.backups))
    try:
        os.chmod(work, 0o700)
        unpacked = decrypt(platform, archive, work)
        info, summary = report(platform, app_id, unpacked)
        if not confirm:
            summary["mode"] = "Trockenlauf – nichts geändert"
            return summary
        if not platform.stack.healthy(app_id):
            status = json.loads(service.status_path.read_text()) if service.status_path.exists() else {}
            good = status.get(app_id, {}).get("lastHealthyArchive", "keine")
            raise StateError(f"{app_id} ist nicht gesund; zuerst die letzte gesunde Sicherung ({good}) mit "
                             "'./install.sh restore' zurückspielen")
        safety = service.backup(app_id)  # healthy state of the new server, for rollback
        summary["preImportBackup"] = safety["archive"]
        facts = restore_directory(service, app_id, unpacked, legacy=True)
        summary["result"] = facts
        summary["countDifferences"] = compare_counts(platform, app_id, info, facts)
        deviations = bool(summary["countDifferences"])
        if info.get("checksums"):
            summary["checksums"] = verify_checksums(service, app_id, info, work)
            deviations |= any(r.get("missingCount") or r.get("differentCount") or r.get("checked") is None
                              for r in summary["checksums"].values())
        summary["mode"] = "Übernommen" if not deviations else "Übernommen mit Abweichungen"
        return summary
    finally:
        shutil.rmtree(work, ignore_errors=True)
