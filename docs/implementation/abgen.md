# abgen: eigenständiger PostgreSQL-/Yjs-/PDF-Stand

Die zehnte ausgewählte App hat jetzt einen geprüften eigenständigen Containerstack.
**Die Anbindung an den gemeinsamen Zehn-App-Pilot ist noch offen.**
Dies ist keine Produktionsfreigabe und kein Abschluss von A9.

Ausgangscommit: `50db999ccc689cdad3a6b2c930d24dee650eaec2`.
App-Implementierung: `e14bbe6664087aaef8ecb027913297885b4f6c13`.
[Exportierter Patch](../../patches/abgen/changes.patch),
[sauberer Replay mit identischem Git-Baum](evidence/abgen-patch-replay.json).

## Änderungen

- Bestehende pnpm-Workspaces und das native Lockfile bleiben eigenständig.
  Frozen-Install, Build und Typechecks laufen im festgelegten Node-22-Image.
  SPA und API werden gemeinsam ausgeliefert; Chromium/PDF und PostgreSQL 18
  bleiben private separate Dienste. Native Variablennamen bleiben erhalten.
- UID 10001 für API/PDF, schreibgeschütztes Rootdateisystem, begrenzte Ressourcen.
  Nur der API/SPA-Port ist auf Loopback veröffentlicht. Eigene beschränkte DB-Rolle,
  private Zugangsdatenprojektionen; PDF bekommt keinen Datenbankzugang.
- Explizite Drizzle-Migration mit exklusivem Lock und Hashprüfung.
  Unbekannte Bestandsdatenbanken ohne geprüfte Historie werden abgewiesen.
  0000–0005 und das Lockfile wurden nicht geändert. Normale Starts legen weder
  Schema noch Benutzer an; 0006 ergänzt Sitzungsbindung und Yjs-Persistenz.
- Erstadministration nur lokal mit echtem Terminal, persönlicher Identität und
  verdecktem Passwort. Öffentliche Erstanmeldung bleibt geschlossen.
  Optional geöffnete Folgeregistrierung erzeugt ausschließlich Lehrkraftkonten.
  Oberfläche bietet Registrierung nur an, wenn sie ausdrücklich geöffnet wurde.
- Gehashte native Sitzungen sind an aktuelle Zugangsdaten gebunden.
  Logout, Sperrung, Rollen- und Passwortwechsel widerrufen Sitzungen.
  Eigene Passwortänderung rotiert das Cookie. Die Sitzungserzeugung prüft
  aktuelle Zugangsdaten unter PostgreSQL-Zeilensperre erneut.
- Exakte Browser-Origin, zusätzlicher Header für Schreibanfragen,
  unterdrückte URL-/Requestprotokollierung und generische Laufzeitfehler.
  Beabsichtigte Freigabelinks und anonyme Kinder-Kurzcodes bleiben erhalten.
- Gültige Yjs-Updates werden **vor** Versand an andere Teilnehmer in PostgreSQL
  bestätigt. Neue Teilnehmer und HTTP-Dokumentabrufe lesen den dauerhaften Stand.
  Ein Raum ohne verbleibende Teilnehmer behält seine gespeicherten Änderungen.
  Revisionswiederherstellung schließt den bisherigen Raum.
  Pro Nachricht werden Sitzung und Dokumentfreigabe erneut geprüft.
- Zusammenarbeit ist auf einen API-Prozess begrenzt. Begrenzte Räume, Teilnehmer,
  Frames, Snapshots und ausstehende Nachrichten; private Loopback-Stopsteuerung
  drainiert Räume. Ein verlässliches Offline-/Reconnect-Journal fehlt.
- Ein PDF-Slot ohne Queue, zweiter Auftrag 429, begrenzte Laufzeit und Ausgabe.
  Interne Druckadresse `abgen-web` vermeidet die beobachtete HTTPS-Umleitung
  des Hostnamens `app`. Chromium lädt nur die interne App und lokale Ressourcen.
  Mediendateien werden synchronisiert und atomar veröffentlicht.

## Tatsächlich ausgeführt

| Prüfung | Beobachtung |
| --- | --- |
| [Builds / Images](evidence/abgen-images.json) | linux/amd64; API Node 22.23.4, PDF-Basis Node 26.13.0 |
| [Native Tests](evidence/abgen-functional.log) | 623 Tests in sechs Workspaces bestanden, offline |
| [ESLint](evidence/abgen-eslint.log) | nativer vollständiger Lauf ohne Fehler/Warnungen |
| [Standalone](evidence/abgen-standalone.json) | echter Start ohne Plattform, Migration zweimal, null Standardkonten, verdeckte Terminaleinrichtung, Wiederholung/headless verweigert |
| [Fach-/Negativtests](evidence/abgen-contracts.log) | Eigentümerschaft, Lehrer/Admin, fremde Origins, Header, anonyme/fremde WebSockets, echte PDF-Konkurrenz, Kinderabgabe und Asset-Upload |
| [Yjs-Abbruch](evidence/abgen-restart.log) | harter API-Prozessabbruch; HTTP und neue Peers laden dauerhaften Stand |
| [Leeres Restore](evidence/abgen-restore.json) | alle Fachzeilen und Migrationshistorie identisch; nichtleere DB-Ziele werden verweigert; getrenntes frisches Asset-Volume mit identischen Bytes/UID |
| [Restaurierte Zugänge](evidence/abgen-restored-http.log) | ursprünglicher Freigabelink/Kurzcode, gesperrte Sitzung, Mediendatei, Yjs und echter PDF-Druck ohne Migration/Seed geprüft |
| [Browser](evidence/abgen-browser.log) | Chromium: zwei echte Editor-Peers und erneuter Einstieg; WebKit: Anmeldung und Zusammenarbeit |

Erzwungener PostgreSQL-Schreibfehler: kein Broadcast und kein Überschreiben.
Fehlerhafter Yjs-Dokumentkörper: unveränderter dauerhafter Stand.
Kontosperrung widerruft HTTP-Zugriff sofort und bestehende WebSocket-Zugriffe
bei der nächsten Nachricht. Öffentliche Kinderzugänge eröffnen keine Ergebnis-
oder Administrationsrechte. DB-Ausfall: API-Liveness 200, Readiness 503, kein
Prozessneustart; Wiederaufnahme ohne Bootstrap. PDF-Ausfall wird separat sichtbar.
Migrationsdrift blockiert Readiness und den Migrationsjob, ohne Historie umzuschreiben.
Restore umfasst PostgreSQL samt Yjs **und** die atomar veröffentlichten Assetdateien.
Die isolierten Quell-, Browser- und Restore-Dienste sind gestoppt; Volumes und private
Schlüssel wurden erhalten. Fremde Docker-Dienste wurden nicht verändert.

Beobachtete Imagegrößen: API rund 537 MB, PDF rund 2,85 GB.
Das festgelegte Playwright-Basisimage allein umfasst 2.542.930.822 Bytes.
Das sind Imagegrößen, keine Zielserver- oder Arbeitsspeichermessung.

## Noch erforderlich

- Abgen-Adapter, eigener PostgreSQL-18-Dienst und PDF-Lebenszyklus im Zehn-App-Pilot;
  Readiness einschließlich PDF, TLS-Proxy, Domaintransaktion mit Rückfall und
  Dashboardsteuerung müssen noch integriert und tatsächlich geprüft werden.
- Vollständige native Playwright-Suite, visuelle Druck-/Offline-Abnahme,
  Last-/Ressourcenmessung und Crash-/Netzwerkrennen über die geprüften Fälle hinaus.
  Keine Mehrprozess-/Clusterfreigabe und kein zugesicherter Verlustschutz für
  lediglich lokal angezeigte, unbestätigte Browseränderungen.
- Die eigene Erstinstallation ist geprüft; reale Bestandsübernahme und
  zukünftige Schemaänderungen benötigen jeweils eine geprüfte Migrationsfreigabe.
- Ubuntu-24.04-Zielserver, signierte veröffentlichte Releases, Lizenzfreigaben,
  Offsite-Backupziel und bestätigte RPO/RTO bleiben offen. Elf von zwölf nativen
  Schriftfamilien liegen vor; Gruschudru Basic bleibt ausdrücklich fehlend.
  Keine Fremdlizenz erfunden, keine fehlende Schrift nachgeladen.
- SSO bleibt zuletzt; kein zentraler Logout und keine zentrale Sperrung behauptet.

Reproduzierbare lokale Reihenfolge:
`scripts/build_abgen.py`, `scripts/check_abgen_runtime.py`,
`scripts/verify_abgen_standalone.py`, `scripts/verify_abgen_restore.py`,
`scripts/verify_abgen_browser.py`, `scripts/verify_abgen_patch.py`.
Alle Fixturekonten und Daten sind synthetisch; private Zugangsdaten und
Freigabefähigkeiten bleiben ausschließlich unter ignorierten 0700-Verzeichnissen.
