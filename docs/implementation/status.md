# Umsetzungsstand vom 2. November 2026

**Der Gesamtauftrag ist weiterhin offen.** Der lokale Pilot mit schulwissen und
gswb ist ausführbar und geprüft. Eine Freigabe für den leeren Ubuntu-Zielserver
oder für den gesamten Zehn-App-Stack liegt noch nicht vor.

## Beobachtet und implementiert

- Eigenständige, isolierte App-Repositories; fünf lokale App-Änderungspakete mit
  [Commits und Patches](../../patches/index.json). Keine Appquellen als Monorepo.
- gswb-Redaktion mit lokaler Anmeldung, CSRF und Pflichtsecret abgesichert;
  öffentliche Lese-API bleibt zugänglich. Kein Vertrauen in Identitätsheader.
- Zackboing prüft das serverseitige Sessionalter. Grundschultafel hat einen
  lokalen, kurzlebigen, einmaligen Bootstrapcode und atomare private Nutzerdateien.
  Losverkauf bindet seinen Verwaltungszugang an einen persönlichen Adminnamen.
- schulwissen: expliziter exklusiver Migrationsjob, getrennte Liveness/Readiness,
  Secretdateien unter bestehenden SW-Namen, explizite Proxyadressen, zwei Worker
  und ein PDF-Slot über alle Worker. Produktions-Static-Manifest beim Build.
- Lokaler Zweierstack mit Caddy, getrennten Appnetzen, PostgreSQL und Mailpit.
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
  derzeit ausschließlich Status, Start und Stop für die zwei bekannten Pilot-Apps.
  Das Dashboard besitzt keinen Docker-Socket.
- Releasebundles werden mit einem unabhängig bereitgestellten Ed25519-Schlüssel
  geprüft. Signatur, Dateiinventar, Prüfsummen, Manifest-Schema und signierte
  Abnahmenachweise sind Pflicht. Es existiert noch kein freigegebenes Bundle.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis | Rohbeleg |
| --- | --- | --- |
| Python-Suite für Sicherheit, Manifeste, Signaturen, State, Domains, SQLite | 64 bestanden | [Log](evidence/python-tests.log) |
| schulwissen-Vertragstests im Produktionsimage ohne Netzwerk | 5 bestanden | [Log](evidence/schulwissen-runtime.log) |
| Zackboing-Session-Negativtests | bestanden | [Log](evidence/zackboing-session.log) |
| Grundschultafel Bootstrap-/Dateitests und TypeScript | bestanden | [Nodetest](evidence/grundschultafel-users.log), [TypeScript](evidence/grundschultafel-types.log) |
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
| A7 | SQLite und PostgreSQL als Bausteine getestet | konsistentes DB-/Datei-/Secret-Gesamtbackup, Verschlüsselung und Offsite, vollständiger Apprestore |
| A8 | Zweierpilot mit TOTP und eingeschränktem Steuerdienst getestet | produktive Serviceinstallation, Updates/Domains/Backup/SMTP-Oberfläche, tatsächliche Zugangsprojektion aller zehn Apps |
| A9 | offen | Containerisierung und vollständige Abnahme der übrigen acht Apps |
| A10 | nicht ausgeführt | Zielservermessung, definierte Last- und Dauerläufe |
| A11 | nicht begonnen | bleibt bis zur Abnahme der Pflichtpakete zurückgestellt |

Keine App erfüllt bereits die gesamte Fertigdefinition des Auftrags. Der
PostgreSQL-Test prüft Schema, Fremdschlüssel, Eigentümer sowie Nutzer-/Rollen-IDs;
eine wiederhergestellte App wurde dabei noch nicht per HTTP gestartet.
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
- Gerätebindung der Grundschultafel-Sitzung und transaktionale parallele Änderungen
  vollständiger Nutzerlisten sind offen. gswb-Login-Drosselung ist offen.
- Keine Produktivumstellung, keine DNSänderung, keine echten Benutzerkonten und
  keine echten E-Mails. Mailpit hat keinen externen SMTP-Upstream.
