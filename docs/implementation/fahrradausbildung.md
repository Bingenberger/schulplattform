# Fahrradausbildung: siebte App im lokalen Pilot

Stand: 3. November 2026. Auditbasis d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207.
[Appcommit und vollständiger Patch](../../patches/index.json).
Nur synthetische Schulen, Konten, Startnummern und Ereignisse; keine
Produktivdaten, DNSänderung oder E-Mail.

## Beobachtet und implementiert

Eigenständiges Compose mit eigenem PostgreSQL 16 und eigener Rolle/Datenbank
fahrrad. Die Rolle hat weder Superuser-, CREATEDB- noch CREATEROLE-Recht.
Der Webcontainer erhält die SQLAlchemy-Verbindungsdatei, kein DB-Adminpasswort.
Vorhandene FP-Konfigurationsnamen bleiben erhalten; FP_DATABASE_URL_FILE ergänzt
die direkte URL. Private Schlüsselhelfer überschreiben keine vorhandenen Dateien.

Python 3.12.12, FastAPI 0.143.1, Uvicorn 0.54.0, SQLAlchemy 2.1.4,
psycopg 3.3.6, WeasyPrint 70.0 aus bestehendem uv.lock.
Basisimages mit Digest, lokale amd64-Entwicklungsimages.
[Image-Metadaten](evidence/fahrrad-image.json),
[Runtimebuild](evidence/fahrrad-build-runtime.log),
[Testbuild](evidence/fahrrad-build-tests.log),
[Browser-Abhängigkeiten](evidence/fahrrad-build-browser-tests.log),
[abschließender Browserbuild aus geprüftem Cache](evidence/fahrrad-build-browser-cache.log),
[Image-/Quellbaum-/Lockvergleich](evidence/fahrrad-browser-image.json).
363197786 Byte Imagegröße ist Docker-Metadatum, keine RAM-Messung.
Debian-Systempakete noch ohne vollständig gesperrten Paket-Snapshot/SBOM.

UID/GID 10001, Read-only-Root, 128 MiB /tmp, 768 MiB RAM, eine CPU, 128 PIDs.
Zwei Webworker; gemeinsame PostgreSQL-Zähler für Anmeldung/Postenanfragen,
ein gemeinsamer Dateisperren-PDF-Slot über beide Worker. Überlast 429/503,
begrenzte Eingaben/Exportgrößen und Kartenantworten. Die Grenzen sind konfiguriert,
nicht als Kapazität gemessen. Zusätzliche Appcontainer hätten weitere PDF-Slots.

Expliziter transaktional gesperrter Alembic-Job; Revision 0008 ergänzt lediglich
betriebliche Limitdaten. Keine Migration, Seeds oder Standardkonten beim Start.
Unversionierte Daten werden nicht still adoptiert. Lokale persönliche
Erstadministration verlangt ein kontrollierendes Terminal.

Readiness prüft eigene Datenbank und Revision 0008; Liveness benötigt keine
Datenbank, Karten oder SMTP. DB-Healthchecks nutzen TCP. Serverseitige Karten
standardmäßig aus; interaktive Browserkarten können weiterhin bestehende externe
Anbieter nutzen. Kein Maildienst ergänzt, weil die App keinen SMTP-Versand benötigt.

## Ausgeführte Prüfungen

- 730 Fach-/Vertragstests bestanden, fünf übersprungen, drei Browserfälle
  abgewählt. Enthalten sind Mandantengrenzen, PostgreSQL-Migrationen,
  Ereignis-Idempotenz, PDF-Erzeugung, parallele Limitreservierungen,
  prozessübergreifender Export-Slot und Bodylimit ohne Content-Length.
  [Rohlog](evidence/fahrrad-functional.log).
  Vier Skipfälle sind vorhandene Vorlagen-Sonderfälle; der fünfte war der
  PDF-QR-Decoder im Testimage ohne Poppler und wird separat im Browserimage geprüft.
- 40 Browser-/Offline-/QR-Prüfungen mit Chromium und WebKit im eigenen Image bestanden.
  Ausführung in isolierten Vierergruppen mit Init-Prozess, 1536 MiB/512 PIDs;
  ein einzelner langer Browserlauf stieß vorher an die Ressourcenbegrenzung.
  Ein internes Docker-Testnetz ließ WebKit trotz erfolgreichem lokalen API-Abruf
  dauerhaft offline melden; die Netzsimulation verwendet deshalb eine Bridge
  mit Standardroute. Die getestete App hat dadurch keine neue Internetabhängigkeit.
  Ein weiterer Fall zeigte, dass lange Warnungen den Übertragen-Knopf aus dem
  sichtbaren Bereich schoben; die Statusleiste bricht jetzt um.
  Die Offline-Assertions erlauben zusätzlich die vorhandene Warnung zum Display-
  Ruhezustand und prüfen weiterhin exakt null unübertragene Ereignisse.
  [Rohlog und tatsächlich ausgeführte Testnamen](evidence/fahrrad-browser-functional.log).
- Echtes Standalone-HTTP: Live 200/Ready 503 vor Migration, kein Standardkonto,
  zwei Worker beobachtet, Rollengrenzen/CSRF, anonymer Postentoken und PWA,
  wiederholter Eventupload ohne Duplikat, PDF-Erzeugung. Gehaltener Export-Slot
  liefert 503 bei weiter erreichbarer Liveness. Vierzehn parallele falsche
  Anmeldungen ergeben zehn 401 und vier 429. Sperre und Sitzung überstehen Neustart.
  DB-Ausfall ergibt Live 200/Ready 503, Wiederanlauf stellt Readiness wieder her.
  [Ergebnis](evidence/fahrrad-standalone.json),
  [Kommandos](evidence/fahrrad-standalone-operations.json).
- Generischer pg_dump-Custom-Restore plus Dateisnapshot in separate frische
  PostgreSQL-Instanz und leeres Vorlagenvolume, Originalcredentials separat.
  Sämtliche synthetischen Fachzeilen/IDs/Rollen/Tokens/Ereignisse stimmen überein.
  Fremdschlüssel validiert, Ereignis-Trigger aktiv, Approlle beschränkt.
  Nutzerlogin, PDF und Postentoken funktionieren; anonymer/fremder Schulzugriff
  sowie vorher gesperrte Anmeldung bleiben abgewiesen. Kein Seed/Migrationsjob
  beim Restore. Zweiter Restore ins nichtleere Ziel scheitert.
  [Ergebnis](evidence/fahrrad-restore.json),
  [Kommandos](evidence/fahrrad-restore-operations.json).
  Der erste Testtransport übergab keine Standardeingabe an docker exec;
  mit -i wurde der vollständige Restore erneut erfolgreich geprüft.
- Sieben-App-TLS-Pilot mit verifizierter lokaler CA: private Rootless-Backends,
  Login, Secure-Cookie, CSRF und fremde Schule abgewiesen, öffentlicher Posten
  und Service Worker erhalten. Domainwechsel einschließlich tatsächlicher
  Rasterung und Dekodierung des QR-Codes aus dem erzeugten PDF.
  URL enthält neue Laufzeit-Origin und denselben bestehenden Postentoken.
  Erzwungener Prüffehler rollt zurück. Zwei No-op-Läufe erhalten Container,
  Schlüssel und Checkpoints. Stop 503, Start ohne Migration, ein identisches
  Ereignis nach allen Wiederholungen.
  [Ergebnis](evidence/fahrrad-platform.json),
  [Kommandos](evidence/pilot-v14-operations.jsonl).
- Reales Dashboard steuert Start/Stop der Fahrradausbildung über authentifizierten
  Unix-Dienst: TOTP, CSRF, unbekannte Aktionen abgewiesen, kein Docker-Socket,
  keine automatische Fachzugangsberechtigung.
  [Ergebnis](evidence/dashboard-container.json).

Zusätzlich ignoriert Pilot-Stop nun bereits gestoppte Zackboing-Container beim
Drain. Wiederholter Stop ist dadurch auch in diesem Zustand möglich; Regression
in der Plattformtestsuite. 89 Plattformtests bestanden.

- Vollständiger Patch auf Auditbasis angewendet; resultierender Git-Quellbaum
  identisch. [Replay](evidence/fahrrad-patch-replay.log),
  [Appcommits](evidence/fahrrad-app-commit.log),
  [Secretprüfung](evidence/fahrrad-secret-scan.log).

## Reproduktion

Nach Checkout und Anwendung der Apppatches:

~~~sh
.venv/bin/python scripts/build_fahrradausbildung.py --browser
.venv/bin/python scripts/check_fahrradausbildung_runtime.py
.venv/bin/python scripts/check_fahrradausbildung_runtime.py --browser
.venv/bin/python scripts/verify_fahrradausbildung_standalone.py
.venv/bin/python scripts/verify_fahrradausbildung_restore.py
./install.sh pilot-up --state-dir .work/pilot-neu --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung
~~~

Sechs weitere Images und gepinnte Infrastruktur/Compose gemäß [Pilotanleitung](pilot.md)
vorher bereitstellen. Neue Auswahl/neue Image-IDs benötigen neuen Zustandsordner;
dies übernimmt keine Altvolumes. Der Domainversuch ist ein synthetischer
Fixturelauf für .work/pilot-v14, kein allgemeiner produktiver Domaincontroller.

## Offen und Grenzen

Posten-PWA/IndexedDB gehört zur Browser-Origin. Nicht synchronisierte lokale
Erfassungen sind weder im Serverbackup noch automatisch auf neuer Domain vorhanden.
Vor Umstellung alle Geräte online synchronisieren und danach neu einrichten.
Die Browseremulation ersetzt keine reale iPad-/Safari-Abnahme.

Keine öffentliche DNS-/Besitz-/ACME- oder Ubuntu-Neuinstallationsabnahme,
ARM64-Abnahme, Kapazitäts-/Dauerlastmessung oder signiertes Registry-Release.
App-/Fremdmaterial-Lizenz und Kartenanbieterfreigabe bleiben offen.
Kein automatischer Import einer produktiven Altinstallation.

Backups bisher lokal und unverschlüsselt. Secretstore-/Plattform-/Offsite-Gesamtbackup,
Rotation und Alarmierung fehlen. Restore kann alte Sitzungs-/Postenzugänge
reaktivieren; produktiv Widerruf/Neuverteilung planen. Keine zentrale Sperrung.

Eigene Testdienste nach den Prüfungen gestoppt; Daten und Credentials erhalten.
Eigene gestoppte alte Testcontainer und Netze gezielt entfernt, um lokale
Docker-Subnetze freizugeben; keine fremden Dienste oder Bestandsvolumes gelöscht.
Drei weitere Appintegrationen und die vollständige Produktionsabnahme bleiben offen.

Plattform-Quellpaket: 85585f7; [Commit-Rohbeleg](evidence/fahrrad-work-package-commit.log).
