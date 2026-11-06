# Schulhelfer: vierter lokaler Pilotdienst

Beobachtet am 2. November 2026. Appcommit und Patch in
[patches/index.json](../../patches/index.json). Keine Produktionsfreigabe.

## Implementiert

- Python 3.12.12, amd64, Basisimage per Digest; Runtime- und Testabhängigkeiten
  mit Version und Wheel-SHA256 gesperrt. APScheduler bleibt auf der verwendeten
  3er-API, SQLAlchemy auf der 2er-API.
- Eigenständige Compose-Datei plus Plattform-Override. UID:GID 10001:10001,
  Read-only-Root, Init, 64-MiB-tmpfs und gesetzte Limits von 384 MiB/1 CPU/128
  Prozessen. SQLite unter /app/data, Verzeichnis 0700, DB 0600.
- Kein create_all im Webstart. Expliziter Alembic-Job mit exklusivem Lock,
  SQLite BEGIN IMMEDIATE, Fremdschlüsselprüfung und user_version 1.
  Unversionierte Bestandsdaten werden ohne geprüften Adoptionspfad verweigert.
- Pflichtsecret über vorhandenes SECRET_KEY oder neue Dateioption.
  Lokaler persönlicher Erstadmin über kontrollierendes Terminal, ohne
  Standardpasswort, ohne öffentliche Registrierung und ohne Wiederholung.
- Genau ein Webprozess und ein Schedulerlock pro Datenroot. Ein PDF-Slot in
  einem Thread; Konkurrenz erhält 503 statt unbeschränkter Renderer.
- BASE_URL zur Laufzeit, Secure-Cookie bei HTTPS und explizite Proxyadressen.
  Elternlinks bleiben öffentlich. Keine Uvicorn-Accesslogs für Bearerpfade,
  no-referrer und private,no-store.
- Kurze Request-Datenbanksitzungen vor BackgroundTasks, Freigabe von
  Mail-Readern vor SMTP-await, frische Schreibtransaktion fürs Zustellprotokoll.
  Gesamtzeitlimit des SMTP-Aufrufs. Mail-Sink ohne Upstream.
- Optionaler Viererpilot; Zweier- und Dreierkonfigurationen behalten ihre Auswahl.
  Bekannte Dashboard-/Steuerdienstziele um Schulhelfer erweitert.

## Ausgeführt

| Prüfung | Beobachtetes Ergebnis |
| --- | --- |
| Runtime-Vertrag | 9 Tests bestanden: Pflichtsecret, kein Schema beim Import, explizite Migration, unbekanntes Schema verweigert, lokaler Einmalsetup, Prozesslocks, PDF-Slot, SMTP-Zeitlimit und Retention mit abhängigen Mailprotokollen |
| Vorhandene Fachsuite | 52 Tests bestanden; 109 Deprecation-Warnungen, keine Testfehler |
| Standalone ohne Plattform-Override | HTTP, lokale Anmeldung, CSRF-Negativzugriff, öffentlicher Elternlink, PDF, Sink-Zustellung und Neustart bestanden |
| Gleichzeitige Buchungen | 8 echte parallele HTTP-Anmeldungen auf eine neue Schicht mit Kapazität 1 ergeben genau 1 Buchung |
| SMTP-Ausfall | Readiness weiter 200, erfolglose Zustellung in der DB protokolliert |
| Leerer Restore | Neues Volume über generischen SQLite-Snapshot, App ohne Migration/Setup gestartet; Schema, IDs, Buchungen, Adminzuordnung, Elternlink und private Eigentümerschaft erhalten |
| Domainwechsel | Lokales TLS, Login, Mail-Link und Elternlink nach Wechsel geprüft; Manipulation von Forwarded-Host ändert die kanonische Mail-URL nicht |
| Rückfall | Erzwungener Prüffehler stellt alte Konfiguration wieder her; Originaldomain abschließend ebenfalls wiederhergestellt |
| Lebenszyklus | Zwei No-op-Installationsläufe; Stop liefert Wartung 503, Start erhält Elternlink ohne neue Migration oder Setup |
| Dashboard | Neu gebautes Image mit erneut bestandenem TLS-/Unix-Steuerdienst-Containertest; Rechteprojektion für Schulhelfer zusätzlich per Python-Test geprüft |

Rohdaten: [Runtimeimage](evidence/schulhelfer-image.json),
[Build](evidence/schulhelfer-build-final.log),
[Vertragstests](evidence/schulhelfer-contract.log),
[Fachtests](evidence/schulhelfer-functional.log),
[Standalone](evidence/schulhelfer-standalone.json),
[Standalonekommandos](evidence/schulhelfer-standalone-operations.json),
[Restore](evidence/schulhelfer-restore.json),
[Restorekommandos](evidence/schulhelfer-restore-operations.json),
[TLS/Domain/Lifecycle](evidence/schulhelfer-platform.json),
[Pilotkommandos](evidence/pilot-v7-operations.jsonl),
[Secretdatei](evidence/schulhelfer-secret-setup.json).

Ein zusätzlicher Retention-Regressionsfall prüft, dass Mailprotokolle vor den
Teilnehmern entfernt werden und die Bereinigung wiederholbar bleibt. Der
ursprüngliche Cleanup konnte an diesem Fremdschlüssel scheitern.

Die acht parallelen Buchungen prüfen eine fachliche Invariante im deklarierten
Einprozessbetrieb. Das ist keine Kapazitäts-, Last- oder Latenzmessung.

## Wiederholung

```sh
.venv/bin/python scripts/build_schulhelfer.py
.venv/bin/python scripts/check_schulhelfer_runtime.py
.venv/bin/python scripts/verify_schulhelfer_standalone.py
.venv/bin/python scripts/verify_schulhelfer_restore.py
./install.sh pilot-up --state-dir .work/pilot-v7 --apps gswb,schulwissen,zackboing,schulhelfer
.venv/bin/python scripts/verify_schulhelfer_platform.py
```

Der Restoretreiber verwendet die zuletzt erfolgreich erzeugte private
Standalonefixture. Der Plattformtreiber verwendet ein separates synthetisches
Konto und eine lokale Caddy-CA mit echter Zertifikatsprüfung. Keine produktiven
Konten, E-Mails, DNSänderungen oder globalen CA-Einträge.

In frühen Parallelversuchen fehlten Zustellprotokolle beziehungsweise liefen
SMTP-Aufrufe ins Zeitlimit. Request- und Hintergrundsitzungen blieben über
Netzwerk-awaits offen. Die nachfolgenden Korrekturen schließen diese Sitzungen
früher und schreiben Zustellprotokolle separat; danach sind die obigen Versuche
erfolgreich durchgelaufen. Die Rohbelege gehören zu diesem korrigierten Image.

Zwischen Testgenerationen waren Dockers Standard-Adresspools ausgeschöpft.
Ausschließlich eigene, bereits gestoppte Pilotgenerationen wurden mit Compose
down abgebaut. Datenvolumes und Schlüssel bleiben erhalten; kein globales
Prune, kein down -v. Ältere Testgenerationen werden nicht als neu freigegeben.

## Offen und begrenzt

- Kein freigegebenes Bundle, keine Projektlizenzfreigabe, keine SBOM und kein
  veröffentlichter Registrydigest; Image-IDs sind lokale Build-Identitäten.
- Öffentliche DNS-/Besitz-/ACME-Prüfung und separate Managementdomain fehlen.
  Dieser Appflow hat keine QR-, WebSocket- oder OIDC-Funktion.
- Persönlicher Erstadmin wird lokal eingerichtet; der vollständige Installer-
  Bootstrap ist noch nicht automatisiert. Kein allgemeiner Legacy-Adoptionspfad.
- Keine persistente Mail-Outbox. Ein Prozessabbruch kann BackgroundTasks verlieren;
  für Bestätigungsmails bleibt der vorhandene manuelle Wiederholungsweg.
  Stop wartet begrenzt, ist kein belegter verlustfreier Drain für Massenversand.
- Restore prüft das App-SQLite mit bereitgestellter ursprünglicher Konfiguration
  und Schlüsseldatei. Noch kein verschlüsseltes Offsite-/Secretstore-Gesamtbackup,
  keine Retention-/Rotations-/Alarmierungsabnahme.
- App-Retention über 24 Stunden und vollständiger Massenversand nicht abgenommen.
  Die Fachsuite enthält Deprecation-Warnungen.
- Pico-CSS wird in bestehenden Templates noch von jsDelivr geladen. Lokales
  Vendoring mit Lizenznachweis und Browserabnahme steht aus; HTTP-Tests laden
  keine externen Browserassets.
- Keine zentrale Sperrung und keine zentrale Logout-Revokation der signierten
  Appcookies. Eltern-Capabilities stehen wie bisher für Wiederholversand auch
  im Klartext in der privaten DB; keine Tokenwerte in Berichten.
- Keine ARM64-, Ubuntu-Zielserver-, Leerlauf-, Last- oder Dauerlaufabnahme.

Die Testdienste sind gestoppt; Testdaten und Sicherungsarchive bleiben erhalten.
Sechs weitere Apps und die übergreifenden Pflichtpakete bleiben offen.

## Release 0.1.1 (5. November 2026): Übernahme der Altdatenbank

Die alte Version legte ihre Tabellen bei jedem Start mit `create_all` an und stempelte Alembic nie.
Die explizite Migration von 0.1.0 verweigerte darum jede bestehende Datenbank („Unversioned existing
database“). Commit `a30453e` vergleicht die Struktur einer solchen Datenbank mit dem, was die
mitgelieferten Migrationen je Revision erzeugen: Tabellen, Spalten mit Typ, Pflichtfeld und
Primärschlüssel, Fremdschlüssel und eindeutige Spaltengruppen. Bei exakter Übereinstimmung mit
`b7c2e9a41d38` oder `a5ef5d7feb55` wird diese Revision gestempelt und vorwärts migriert. Sonst bricht
die Migration ab und nennt die abweichenden Tabellen, ohne etwas zu ändern. Die Abbruchmeldung des
Migrationsjobs enthält jetzt den Grund.

Tests (Test-Image, read-only, ohne Netz): 64/64, davon neu eine `create_all`-Datenbank des
Basis-Commits, eine ohne die Spalte `token` und eine mit fremder Spalte, die abgelehnt wird.

## Release 0.1.2 (6. November 2026)

Übernimmt `7327c7c` und `c3bfdb7` vom Nutzer: optische Überarbeitung. Pico (indigo) und die Phosphor-Icons (MIT, regular und fill) liegen jetzt unter `static/vendor`. Die App lädt keine Stylesheets mehr von jsDelivr. Das Makro `icon()` maskiert Name und Klasse. Die Tests setzen `BASE_URL` und `SECRET_KEY` vor dem App-Import.

Tests im Test-Image (ohne Netz): 64/64. `verify_schulhelfer_standalone.py` ist grün: Buchung, Mail an den Sink, parallele Anfragen und SMTP-Ausfall.
