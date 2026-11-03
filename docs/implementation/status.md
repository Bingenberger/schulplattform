# Umsetzungsstand vom 3. November 2026

**Der Gesamtauftrag ist weiterhin offen.** Der lokale Pilot mit schulwissen,
gswb und optional Zackboing, Schulhelfer, Losverkauf, Grundschultafel sowie Fahrradausbildung ist ausführbar und geprüft. Eine Freigabe für den leeren Ubuntu-Zielserver
oder für den gesamten Zehn-App-Stack liegt noch nicht vor.

## Beobachtet und implementiert

- Eigenständige, isolierte App-Repositories; sieben lokale App-Änderungspakete mit
  [Commits und Patches](../../patches/index.json). Keine Appquellen als Monorepo.
- gswb-Redaktion mit lokaler Anmeldung, CSRF und Pflichtsecret abgesichert;
  öffentliche Lese-API bleibt zugänglich. Kein Vertrauen in Identitätsheader.
- Zackboing hat einen isolierten Node-LTS-Container, explizite Migration,
  geschlossenen Einmalbootstrap und prüft das serverseitige Sessionalter. Grundschultafel hat einen
  lokalen, kurzlebigen, einmaligen Bootstrapcode, transaktionale private Nutzerdateien,
  widerrufbare Acht-Stunden-Sitzungen und eigentümergebundene mobile Uploadtickets.
  Losverkauf bindet seinen Verwaltungszugang an einen persönlichen Adminnamen.
- schulwissen: expliziter exklusiver Migrationsjob, getrennte Liveness/Readiness,
  Secretdateien unter bestehenden SW-Namen, explizite Proxyadressen, zwei Worker
  und ein PDF-Slot über alle Worker. Produktions-Static-Manifest beim Build.
- Schulhelfer: eigenständiger Rootless-Container, Pflichtsecret, explizite Alembic-
  Migration und persönliche lokale Erstadministration. Ein Webprozess, exklusiver
  Scheduler und ein PDF-Slot. Öffentliche Elternlinks bleiben erreichbar.
- Losverkauf: Pflicht-Session-/Elterntoken, persönliche Hashdatei, CSRF für alle
  Schreibpfade und explizite SQLite-Migration. Bekannte IDs/Bearbeitungstokens bleiben
  erhalten; unbekannte Bestandsfelder werden abgewiesen. Dauerhafte begrenzte
  Eingangs-Mailqueue und lokale Leaflet-Assets.
- Fahrradausbildung: explizite PostgreSQL-Migration, eigene beschränkte DB-Rolle,
  zwei Worker, gemeinsame Login-/Postenlimits und ein prozessübergreifender PDF-Slot.
  Öffentliche Posten-PWA und bestehende Tokens bleiben erhalten.
- Lokaler Zwei- bis Siebenerstack mit Caddy, getrennten Appnetzen, PostgreSQL und Mailpit.
  Nur Caddys TLS-Testport ist auf Host-Loopback veröffentlicht. Die Apps laufen
  ohne Rootrechte und mit schreibgeschütztem Root-Dateisystem. Die PostgreSQL-
  Approlle besitzt keine Superuser-, CREATEDB- oder CREATEROLE-Rechte.
- Persistente Installations-ID, atomare Checkpoints, Lock, unveränderter zweiter
  Lauf und Fortsetzung nach einem Prozessabbruch. Diese Mechanik steuert den
  lokalen Pilot, noch keine vollständige Ubuntu-Provisionierung.
- Domaintransaktionskern mit Journal und Rückfall. Im Pilot wurden TLS, App-URL,
  Loginseite, CSRF und der Passwort-Reset-Link im Mail-Sink nach einem Domainwechsel
  geprüft; ein erzwungener Prüffehler stellte die vorherige Domain wieder her.
- SQLite-Onlinebackup und PostgreSQL-Custom-Dump/Restore. Nichtleere Restoreziele
  werden abgewiesen. Der PostgreSQL-Nachweis betrifft eine neue, vom Netzwerk
  isolierte Datenbankinstanz mit neuem Volume und synthetischen Nutzerdaten.
- Serverseitiges Dashboard mit eigener Admin-Datenbank, TOTP, serverseitigen
  Sitzungen, CSRF und Betriebsprotokoll. Öffentliche Kacheln und bestätigte
  Zugangsprojektion sind von der Administrationsansicht getrennt.
- Separater Unix-Socket-Steuerdienst mit Peer-UID, HMAC und persistenten Nonces;
  derzeit ausschließlich Status, Start und Stop für die sieben bekannten Pilot-Apps.
  Aktive Zackboing-Spiele verweigern Stop mit sicherem 409-Hinweis und Audit.
  Das Dashboard besitzt keinen Docker-Socket.
- Releasebundles werden mit einem unabhängig bereitgestellten Ed25519-Schlüssel
  geprüft. Signatur, Dateiinventar, Prüfsummen, Manifest-Schema und signierte
  Abnahmenachweise sind Pflicht. Es existiert noch kein freigegebenes Bundle.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis | Rohbeleg |
| --- | --- | --- |
| Python-Suite für Sicherheit, Manifeste, Signaturen, State, Domains, SQLite | 89 bestanden | [Log](evidence/python-tests.log) |
| schulwissen-Vertragstests im Produktionsimage ohne Netzwerk | 5 bestanden | [Log](evidence/schulwissen-runtime.log) |
| Zackboing-Bootstrap und Session-Negativtests | bestanden | [Bootstrap](evidence/zackboing-bootstrap.log), [Session](evidence/zackboing-session.log) |
| Zackboing amd64/Standalone | Node 22.23.4, 117 Fach-/Negativprüfungen bestanden | [Image](evidence/zackboing-image.json), [Standalone](evidence/zackboing-standalone.json) |
| Zackboing TLS, QR, WebSocket, öffentlicher PIN, Stopsperre | bestanden | [Ergebnis](evidence/zackboing-platform.json) |
| Zackboing Domainwechsel und erzwungener Rückfall | bestanden mit lokaler CA | [Ergebnis](evidence/zackboing-domains.json) |
| Zackboing kombinierter DB-/Medienrestore in neues Volume, App über HTTP geprüft | bestanden | [Ergebnis](evidence/zackboing-restore.json) |
| Dreierpilot: zwei No-op-Läufe, Stop/Start ohne Migration, Daten erhalten | bestanden | [Ergebnis](evidence/zackboing-lifecycle.json) |
| Schulhelfer-Vertrag und vorhandene Fachsuite im gepinnten Image | 9 und 52 bestanden | [Vertrag](evidence/schulhelfer-contract.log), [Fachtests](evidence/schulhelfer-functional.log) |
| Schulhelfer Standalone, Sink, SMTP-Ausfall und echte parallele Buchungen | bestanden; 8 gleichzeitige Anmeldungen auf 1 Platz ergeben 1 Buchung | [Ergebnis](evidence/schulhelfer-standalone.json) |
| Schulhelfer Restore in neues leeres Volume mit HTTP-Abnahme | bestanden | [Ergebnis](evidence/schulhelfer-restore.json) |
| Viererpilot: TLS, Mail-Domainwechsel und Rückfall, No-op, Stop/Start | bestanden | [Ergebnis](evidence/schulhelfer-platform.json) |
| Losverkauf Laufzeit/Sicherheit ohne Netzwerk | 16 bestanden | [Log](evidence/losverkauf-runtime.log) |
| Losverkauf Standalone, 8 parallele Anmeldungen auf 1 Platz, Queue-Erhalt bei Neustart | bestanden | [Ergebnis](evidence/losverkauf-standalone.json) |
| Losverkauf kombinierter DB-/Map-/Mailrestore mit HTTP-Abnahme | bestanden | [Ergebnis](evidence/losverkauf-restore.json) |
| Fünferpilot: TLS, persönliche Elternlinks, Mail-URL, Domainrückfall, No-op und Stop/Start | bestanden | [Ergebnis](evidence/losverkauf-platform.json) |
| Grundschultafel Bootstrap-/Dateitests und TypeScript | bestanden | [Nodetest](evidence/grundschultafel-users.log), [TypeScript](evidence/grundschultafel-types.log) |
| Grundschultafel Dateilaufzeit im gepinnten Node-Container ohne Netzwerk | 8 Verträge bestanden | [Rohlog](evidence/grundschultafel-runtime-contracts.log) |
| Grundschultafel Standalone, parallele Nutzeranlagen, Session-/Uploaddenials und Neustart | bestanden | [Rohlog](evidence/grundschultafel-standalone.log) |
| Grundschultafel Datei-/Medienrestore in leeres Volume mit HTTP-Abnahme | bestanden | [Ergebnis](evidence/grundschultafel-restore.json) |
| Sechserpilot: TLS, Login-/QR-Domainwechsel, Rückfall, No-op und Stop/Start | bestanden | [Ergebnis](evidence/grundschultafel-platform.json) |
| Fahrradausbildung Fach-/Vertragssuite, echte separate PostgreSQL-Instanz | 730 bestanden; Browser/QR separat | [Rohlog](evidence/fahrrad-functional.log) |
| Fahrradausbildung Chromium/WebKit, Offline und PDF-QR | 40 bestanden, isolierte Browsergruppen | [Rohlog](evidence/fahrrad-browser-functional.log) |
| Fahrradausbildung Standalone, Worker-/Limitprüfung und DB-Ausfall | bestanden | [Ergebnis](evidence/fahrrad-standalone.json) |
| Fahrradausbildung PG-/Vorlagenrestore mit HTTP-Abnahme | bestanden | [Ergebnis](evidence/fahrrad-restore.json) |
| Siebenerpilot: dekodierte QR-Domainwechsel, Rückfall, No-op und Stop/Start | bestanden | [Ergebnis](evidence/fahrrad-platform.json) |
| amd64-Builds gswb und schulwissen | bestanden, lokale Entwicklungsimages | [gswb](evidence/gswb-build.log), [schulwissen](evidence/schulwissen-build.log) |
| gswb Standalone-Start und Neustart | bestanden | [Ergebnis](evidence/gswb-container.json) |
| schulwissen Standalone ohne Plattform-Override | bestanden | [Ergebnis](evidence/schulwissen-standalone.json), [Log](evidence/schulwissen-standalone.log) |
| Zweierstack: TLS, private Backends, Negativzugriff, unveränderter Zweitlauf, DB-Rechte, Mail-Sink | bestanden | [Ergebnis](evidence/pilot-checks.json), [Kommandos](evidence/pilot-operations.jsonl) |
| Domainwechsel und erzwungener Rückfall mit echten lokalen Diensten | bestanden | [Ergebnis](evidence/pilot-domain-rollback.json) |
| pg_dump -Fc und Restore in neue leere Instanz | bestanden | [Ergebnis](evidence/pilot-postgres-restore.json) |
| Pilot stoppen/starten, Schlüssel und Daten erhalten, kein erneuter Bootstrap | bestanden | [Ergebnis](evidence/pilot-lifecycle.json) |
| Dashboard-TLS, Passwort/TOTP, CSRF, Logout, reale Start-/Stop-Aktionen über Unix-Dienst | bestanden | [Ergebnis](evidence/dashboard-container.json), [Kommandos](evidence/dashboard-container-operations.json) |

Die Wiederaufnahmetests umfassen einen tatsächlich mit Exit 17 beendeten
Kindprozess nach erfolgter Nebenwirkung. Nach Wiederaufnahme wurde die bereits
erfolgte Aktion nicht nochmals ausgeführt. Das ist kein Nachweis eines vollständigen
Serverausfalls während einer Ubuntu-Installation.

Beim ersten gemeinsamen Start wurden ein ungültiger Caddy-Headerblock, ein
falscher Hostname im Healthcheck und die fehlende externe Proxy-Netzschnittstelle
erkannt und korrigiert. Ein Login-Test entdeckte außerdem das fehlende
Produktions-Static-Manifest im ursprünglichen schulwissen-Dockerfile.
Die anschließend ausgeführten Prüfungen beziehen sich auf die Korrekturen.

Der Dashboardversuch und seine Korrekturen sind in
[Dashboard-Prüfhinweise](dashboard-tests.md) dokumentiert; Architektur, Konten und
verbleibende Privilegien in [Dashboardbetrieb](dashboard.md).

Der Pilot und die Dashboard-Testdienste sind nach den Prüfungen gestoppt. Daten, Schlüssel und
Testvolumes bleiben erhalten. Es wurden keine globalen Docker-Aufräumkommandos
oder Löschungen von Bestandsvolumes ausgeführt.

## Noch nicht abgenommene Pakete

| Paket | Stand | Fehlend |
| --- | --- | --- |
| A0 | offen | Projektlizenzwahl, Fremdmaterialprüfung, privater Repozugang |
| A1 | lokale Sicherheitskorrekturen und Negativtests | vollständige Abnahme aller Sicherheitsanforderungen im Zieldeployment |
| A2 | Schema, Signatur- und Inventarprüfung implementiert | SBOM, veröffentlichte Registry-Digests, geprüfte Releasekombination |
| A3 | lokaler Caddy-/DB-/Sink-Verbund | produktives Relay mit dauerhafter Queue, Secretrotation, Infrastrukturabnahme |
| A4 | beide Apps standalone und gemeinsam lokal gestartet | leerer Ubuntu-Server, öffentliche TLS-/DNS-Abnahme, vollständige Fachtests |
| A5 | State-Maschine und Pilot-Lebenszyklus getestet | Host-Provisionierung, alle zehn Apps, vollständige Bootstrap-/Verify-Stufen auf Ubuntu |
| A6 | lokaler Domainwechsel mit Rückfall getestet | öffentliche DNS-/Besitz-/ACME-Prüfung, Verwaltungsdomain, alle Link-/Callback-/WS-Varianten |
| A7 | SQLite/PostgreSQL-Bausteine, Zackboing-, Schulhelfer-, Losverkauf-, Grundschultafel- und Fahrradausbildung-Apprestore getestet | Plattform-/Datei-/Secret-Gesamtbackup, Verschlüsselung und Offsite, weitere Apprestores |
| A8 | Dashboard mit TOTP und Steuerdienst für sieben Apps, Stopsperre für Spiele | produktive Serviceinstallation, Updates/Domains/Backup/SMTP-Oberfläche, tatsächliche Zugangsprojektion aller zehn Apps |
| A9 | sieben Apps lokal containerisiert und geprüft | drei weitere Apps; vollständige Release-/Lizenzabnahme |
| A10 | nicht ausgeführt | Zielservermessung, definierte Last- und Dauerläufe |
| A11 | nicht begonnen | bleibt bis zur Abnahme der Pflichtpakete zurückgestellt |

Keine App erfüllt bereits die gesamte Fertigdefinition des Auftrags. Der
PostgreSQL-Test prüft Schema, Fremdschlüssel, Eigentümer sowie Nutzer-/Rollen-IDs;
eine wiederhergestellte schulwissen-App wurde dabei noch nicht per HTTP gestartet.
Für Zackboing ist dagegen der kombinierte SQLite-/Medienrestore samt neu gestarteter
App, Nutzer-/Rollenprüfung und verweigerten Adminzugriffen nachgewiesen.
[Zackboing-Abnahme und Grenzen](zackboing.md).
Auch Schulhelfer wurde nach Restore mit unveränderten Admin-/Fach-IDs,
Buchungen, privater Eigentümerschaft und öffentlichem Elternlink geprüft.
[Schulhelfer-Abnahme und Grenzen](schulhelfer.md).
Losverkauf wurde mit gleicher Anmeldung, Personen-/Queue-IDs, bestehenden
Bearbeitungstokens sowie Karten- und privaten Maildateien wiederhergestellt.
[Losverkauf-Abnahme und Grenzen](losverkauf.md).
Grundschultafel wurde als Dateistore mit Nutzer-/Notizbuch-IDs und privaten
Uploadbildern in einem neuen Volume wiederhergestellt.
[Grundschultafel-Abnahme und Grenzen](grundschultafel.md).
Fahrradausbildung wurde mit eigenem PostgreSQL-Cluster und Vorlagenvolume,
identischen Fachzeilen sowie Rollen-/Token-/Ereignisprüfung wiederhergestellt.
[Fahrradausbildung-Abnahme und Grenzen](fahrradausbildung.md).
Der Domainversuch verwendet lokale Testnamen und eine lokale CA; er ersetzt
keinen Nachweis öffentlicher DNS-/ACME-Konfiguration. Im geprüften schulwissen-
Passwort-Reset-Flow gibt es keinen QR-Code und keine aktivierten OIDC-Callbacks.

## Offene Entscheidungen und Grenzen

- Lizenzwahl und Ubuntu-Testserver/Testdomains wurden angefragt; keine Antwort
  liegt vor. Kein Lizenztext erfunden, kein Image veröffentlicht.
- Offsite-Backupziel wurde angefragt. Bis zur Festlegung ausschließlich lokale,
  synthetische Sicherungsprüfungen. RPO 24 h und RTO 4 h bleiben unbestätigte Ziele.
- 16 GB RAM, 4 dedizierte vCPU und 160–200 GB SSD für zehn Apps bleiben Schätzungen.
  Es gibt noch keine neue Leerlauf- oder Kapazitätsmessung.
- Keine zentrale Sperrung und kein zentraler Logout. Die
  [Austrittschecklisten](departure-checklists.md) bleiben notwendig.
- Schulhelfer hat noch keine persistente Mail-Outbox oder vollständige
  Massenversand-/Retentionabnahme. Lokales Vendoring der bestehenden Pico-CDN-
  Stylesheets mit Lizenznachweis steht aus. Der Retention-Fremdschlüssel-Regressionsfall ist geprüft.
- Losverkaufs Queue sichert Eingangsbestätigungen; andere Mailaktionen sind
  teilweise synchron. SMTP-Absturzrennen können Duplikate erzeugen. Keine zentrale
  Queue-/Retry-/Alarmierungsoberfläche oder Browserabnahme; native Alt-Automationen
  sind für den geänderten Vertrag noch nicht abgenommen.
- Grundschultafel prüft zusätzliches Gerätecookie und serverseitige Sitzungen;
  das ist keine Hardwarebindung. Visuelle Canvas-/QR-Kameraabnahme
  und Lizenzprüfung der Unterrichtsmedien bleiben offen. gswb-Login-Drosselung ist offen.
- Fahrradausbildung: lokale ungesendete PWA-/IndexedDB-Daten sind nicht im Serverbackup
  und wechseln die Origin nicht automatisch. Vor Domainwechsel vollständig synchronisieren.
- Keine Produktivumstellung, keine DNSänderung, keine echten Benutzerkonten und
  keine echten E-Mails. Mailpit hat keinen externen SMTP-Upstream.
