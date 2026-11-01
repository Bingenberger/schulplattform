# Umsetzungsauftrag für einen Coding-Agenten: gemeinsame Schulplattform

Stand: 1. November 2026. Auftraggeber: Florian Emrich.

Dieser Auftrag folgt auf den abgeschlossenen Prüfauftrag. Das Audit liegt unter `docs/platform-audit/`, der verbindliche Umfang in `docs/platform-audit/scope-decision.md`.

## 1. Auftrag

Du baust eine selbst gehostete Schulplattform, die alle ausgewählten Apps gebündelt auf einem nackten Linux-Server installiert und zentral wartbar macht. Du führst die Umsetzung aus, nicht nur eine Planung.

**Priorität, in genau dieser Reihenfolge:**

1. Ein **Installationsskript**, das alle Dienste gebündelt auf einen leeren Server bringt.
2. **Zentrale Wartung**: Domain- und Basis-URL-Verwaltung, Updates, Backup, Zustandsübersicht.
3. **Standalone-Betrieb jeder App bleibt erhalten.** Harte Anforderung.
4. **SSO ist Kür** und betrifft nur zwei Apps.

Wenn du zwischen Priorität 1–3 und der Kür abwägen musst, gewinnt immer 1–3. Wenn du zwischen Integrationskomfort und Standalone-Fähigkeit abwägen musst, gewinnt Standalone.

## 2. Arbeitsweise

Lies zuerst `docs/platform-audit/scope-decision.md`, dann `README.md`, `architecture.md`, `integration-contract.md`, `operations.md` und `server-sizing.md` im selben Verzeichnis. Die Nachträge am Dateianfang nennen, was durch den Umfangsbeschluss überholt ist. Die Einzelberichte in `docs/platform-audit/apps/` enthalten commitgebundene Codeanker pro App; nutze sie, statt erneut zu suchen.

Die 14 Repositories liegen unter `https://github.com/Bingenberger/<name>`; `schulanmeldung` ist privat und nur über SSH erreichbar. `docs/platform-audit/scripts/checkout.py` holt genau die geprüften Commits in isolierte Verzeichnisse und überschreibt nichts. Arbeite in isolierten Checkouts oder Worktrees und erhalte bestehende Änderungen. Lies vorhandene `AGENTS.md` und `CLAUDE.md` je Repository.

Ändere keine produktiven Systeme, keine DNS-Einträge, keine echten Benutzerkonten. Versende keine echten E-Mails; in Tests ausschließlich Mail-Sink. Nutze synthetische Testdaten. Konfiguriere keinen externen SMTP-Upstream.

Arbeite in nachvollziehbaren Commits pro Arbeitspaket. Belege jedes abgeschlossene Paket mit ausgeführten Kommandos und deren Ausgabe. Trenne in Berichten **beobachtet** (durch Code/Konfiguration/Test belegt), **gemessen** (mit Aufbau und Rohdaten), **geschätzt** (Annahme mit Bandbreite) und **offen/blockiert**. Nenne keine erfundenen Messwerte. Ein nicht ausgeführter Test ist als nicht ausgeführt zu melden, nicht als bestanden.

Stelle höchstens fünf entscheidungsrelevante Fragen, falls die Antwort nicht aus den Auditdokumenten hervorgeht. Warte mit unabhängiger Arbeit nicht auf Antworten.

## 3. Harte Randbedingungen

### Standalone bleibt erhalten

Jede App behält eine eigenständig funktionsfähige `docker-compose.yml`. Die Plattform legt eine Override-Datei darüber:

```
docker compose -f docker-compose.yml                  # standalone, muss funktionieren
docker compose -f docker-compose.yml -f platform.yml  # in der Plattform
```

Daraus folgt:

- **Die Plattform ergänzt, sie erzwingt nicht.** Jede App behält ihre eigenen Env-Namen (`SW_*`, `SL_OFFICE_*`, …). Ein Adapter übersetzt plattformseitig in diese Namen. Benenne keine App-Variable auf einen plattformweiten Namen um.
- **Eigene Datenbank und eigener Datenbankbenutzer je App.** Ein gemeinsamer Postgres-Server ist erlaubt, ein gemeinsames Schema nicht. Schema-Migrationsrecht nur für die eigene Datenbank. Ein `pg_dump` muss die App vollständig herauslösen.
- **OIDC bleibt optional**, lokale Anmeldung bleibt daneben erhalten. Keine App darf ohne Identity Provider unbenutzbar werden.
- Keine Verschmelzung fachlicher Tabellen in eine gemeinsame Datenbank.

### Nicht tun

- Kein Monorepo. Die Apps bleiben eigenständige Repositories mit versionierten Images.
- **Kein Keycloak** in dieser Ausbaustufe, siehe D2 im Umfangsbeschluss.
- Kein unbeschränkter Docker-Socket am Dashboard, keine frei formulierbaren Shell-Kommandos aus der Oberfläche.
- Keine `latest`-Tags. Images werden über Version **und** Digest fixiert.
- Kein `compose down -v` als Deaktivierungsweg.
- Kein öffentliches offenes Mail-Relay, kein Internet-MX.
- Keine Secrets in Git, im Frontend, in Logs oder im Dashboard-HTML.
- Bestehende Firewall, SSH-Konfiguration, Docker-Installation oder Datenbestände nicht blind überschreiben.
- Kein SSO vor Routen, die bewusst öffentlich sind: Elternlinks, Kinder-Codes, QR-Zugänge, TAN, Posten-PWA, Spiel-PINs, Kioskbetrieb, Offline-Funktionen.

## 4. Umfang

### Zu migrieren, zehn Apps

schulwissen, kompetenz-manager, abgen, fahrradausbildung, leseflux, zackboing, gswb, grundschultafel, schulhelfer, losverkauf.

### Zunächst nicht migrieren, vier Apps

SL-Journal, schulanmeldung, schulkasse, schuleva. Diese bleiben auf ihrem heutigen Deployment. Fasse sie nicht an, außer für die Sicherheitspunkte in Abschnitt 10.

### Login je App

| App | Anmeldung in dieser Ausbaustufe |
| --- | --- |
| schulwissen | **OIDC gegen die vorhandene Schul-Nextcloud** plus lokaler Login |
| gswb | **Proxy/BFF-Auth nur für die Redaktion**; Wörterbuchsuche bleibt öffentlich |
| grundschultafel | lokaler **Kurz-PIN pro Lehrkraft**, kein gemeinsames Gerätekonto |
| alle übrigen | lokale Anmeldung unverändert |

## 5. Container-Vertrag

**Beobachtet im Audit:** Vier Apps haben Dockerfile und Compose (abgen, leseflux, fahrradausbildung, schulwissen), schulhelfer hat ein Dockerfile ohne Compose. Neun Apps haben **keinerlei Dockerfile**: kompetenz-manager, losverkauf, schulanmeldung, schuleva, schulkasse, SL-Journal, zackboing, grundschultafel, gswb.

Sieben davon haben stattdessen ein `deploy/`-Verzeichnis mit systemd-Units, Timern, nginx-vhosts und teils eigenen `install.sh` (schulkasse, zackboing, kompetenz-manager). **Nutze dieses Material als Quelle**: Pfade, Env-Variablen, Startreihenfolge, Backup-Timer und Routing sind dort schon durchdacht. Übersetze, erfinde nicht neu.

Jedes App-Image erfüllt:

- Nicht-Root-Systembenutzer, möglichst read-only Root-Dateisystem, begrenztes tmpfs, keine privilegierten Container, Uploads niemals ausführbar.
- Festgelegte Laufzeitversion. Die Apps verwenden ihre jeweils passende Python- oder Node-Version; es gibt keine plattformweite Einheitsversion.
- Reproduzierbare Installation aus dem vorhandenen Lockfile (`uv.lock`, `pnpm-lock.yaml`, `package-lock.json`, `requirements.txt`).
- **Liveness** ohne Abhängigkeit von externer KI oder SMTP. **Readiness** mit eigener Datenbank und Migrationsstand. Ein externer Dienstausfall führt zu `degraded`, nicht zu einer Neustartschleife. Vorhandene Pfade (`/gesund`, `/healthz`, `/api/health`) nur nach Prüfung ihrer Semantik verwenden.
- Migration als expliziter, exklusiver Job aus einem geprüften Release, nicht automatisch beim Containerstart.
- Deklarierte persistente Pfade mit Eigentümerangabe.
- Ressourcenlimits und begrenzte Export-Slots. Bei Überlast `429`/`503` statt unbegrenztem Chromium- oder LibreOffice-Start. Slots werden je Prozess gezählt; mehrere Worker multiplizieren eine lokale Semaphore.

**Worker-Zahl:** Keine App hat eine Job-Queue; WeasyPrint und LibreOffice laufen synchron im Request. Setze für schulwissen, fahrradausbildung und kompetenz-manager mindestens zwei Worker, sonst blockiert ein Export die App für alle. abgen hat den PDF-Dienst bereits als eigenen Container, dort bleibt es dabei.

**ARM64** erst behaupten, wenn SQLCipher, better-sqlite3, `@node-rs/argon2`, Prisma, Pillow/Pango, LibreOffice und Chromium erfolgreich gebaut und getestet sind. Zunächst nur amd64. Ziel-OS ist Ubuntu Server 24.04 LTS.

**Bekannte Hürde:** Der native Build von zackboing ist im Audit gescheitert (npm 12 verlangt eine spezifische Script-Freigabe, danach fehlte unter Node 26 ein Prebuilt und der node-gyp-Cache lag außerhalb erlaubter Schreibpfade). Das ist kein Beleg für Inkompatibilität. Löse es im Containerbuild mit einer festgelegten Node-LTS-Version und schreibbarem Cache-Verzeichnis.

## 6. Installationsskript

Idempotente Zustandsmaschine `preflight → plan → provision → bootstrap → verify → completed`. Die Spezifikation in `operations.md` ist gut durchdacht und wird übernommen. Kern:

1. **Preflight:** Rechte, Distribution, Architektur, RAM, Swap, freier Speicher, Ports 80/443, vorhandene Docker-/Proxy-/Datenbankdienste, Namens- und Volume-Kollisionen, DNS-Auflösung der gewählten Domains, Uhrzeit/NTP, Erreichbarkeit von Registry und Paketquellen. Bei Fremdbeständen abbrechen oder einen expliziten Übernahmeplan verlangen.
2. **Plan:** Releasebundle mit Digests, erlaubten Aktionen, Konfigurationsschema und Platzbedarf validieren. Kein `curl | sh`.
3. **Provision:** persistente State-ID, Lockdatei, atomarer Fortschritt, versionierte Konfiguration. Vorhandene Volumes und Schlüssel erkennen und wiederverwenden. Wiederholte Ausführung ist ein No-op ohne Versionswechsel; nach Unterbrechung wird am letzten nachgewiesenen Schritt fortgesetzt.
4. **Bootstrap:** einmalig, zufällig, kurzlebig, über lokalen Konsolenkanal. **Kein Standardpasswort.** Initialwert nicht in Logs oder Shell-History. Bootstrap danach unbrauchbar machen. Die offene Erstregistrierung bei zackboing und abgen sowie der Erstzugang bei grundschultafel werden dabei geschlossen.
5. **Verify:** Readiness, Negativzugriff, Mail in den Sink, Backup und Restore. Ein fehlgeschlagener Test blockiert das Release.

**Abnahme:** zweimaliges Ausführen auf einem leeren Ubuntu-24.04-System ändert beim zweiten Lauf nichts; ein mittendrin abgebrochener Lauf lässt sich fortsetzen; ein Lauf gegen ein System mit bereits vorhandenem Docker und fremdem nginx bricht mit klarer Meldung ab, statt etwas zu überschreiben.

## 7. Zentrale Domainverwaltung

Caddy als Proxy mit explizit erzeugter Konfiguration, keine Docker-Discovery, Admin-API nur intern, Zertifikatszustand persistent.

Ein Domainwechsel ist eine **Transaktion mit Rückfall**, Ablauf nach `operations.md`: Syntax-, Besitz-, DNS- und Portprüfung → lesbare Vorschau und Konfigurationsdiff ohne Secrets → Snapshot der alten Konfiguration und Recoverylink über separate Verwaltungsdomain → Zertifikat anfordern und Callback-URIs vorregistrieren → neue Proxy- und App-Konfiguration atomar anwenden → Login, Callback, API, CSRF, Mail-Sink und WebSocket prüfen → bei Fehler automatisch zurückrollen.

Gleichzeitig zu berücksichtigen: Proxy-Route, Zertifikat, App-Basis-URL, Redirect- und Post-Logout-URIs, Mail-, QR- und Elternlinks, CORS/CSRF, WebSocket-Origin und beim Build eingebrannte öffentliche Werte. Wo eine Vite- oder Next-App ihre öffentliche URL zur Buildzeit einbrennt, kennzeichne das im Manifest und löse es entweder durch Laufzeitkonfiguration oder durch einen Rebuild als Teil der Transaktion. DNS bleibt manuelle Aufgabe beim Provider. Behalte bei fehlerhaften Änderungen einen administrativen Zugangsweg.

**Abnahme:** Domainwechsel einer migrierten App von `alt.example.invalid` auf `neu.example.invalid` einschließlich Login, Mail-Link und QR-Code; anschließend eine absichtlich ungültige Änderung, die automatisch auf die alte Konfiguration zurückfällt.

## 8. Backup und Wiederherstellung

Generisch nach Speichertyp, nicht als Adapter pro App. Das Manifest deklariert Engine, Datenbankname und persistente Pfade; ein zentraler Dienst bedient drei Muster:

- **PostgreSQL:** `pg_dump -Fc`, konsistent.
- **SQLite:** `.backup`-API. **Niemals die laufende Datenbankdatei kopieren.**
- **Verzeichnisse:** Snapshot der deklarierten Upload- und Medienpfade.

Zwei Sonderfälle: **SL-Journal** — SQLCipher-Schlüssel müssen mitgesichert werden, sonst ist das Backup wertlos. **abgen** — PostgreSQL 18 plus Yjs-Zustand.

Mitzusichern sind außerdem Plattformkonfiguration, Secretstore und notwendige Schlüssel. Backups verschlüsselt außerhalb des Servers ablegen; ein Snapshot auf demselben Server ist kein Backupkonzept. Dokumentiere Aufbewahrung, Rotation und Alarmierung. RPO 24 h und RTO 4 h sind Diskussionsgrundlage und vom Auftraggeber noch zu bestätigen.

**Abnahme:** Restore in eine **leere** Umgebung mit anschließender Prüfung von Schema-Version, Fremdschlüsseln, Eigentümerschaft, Rollen und verweigerten Zugriffen. Container-Rollback und Datenbank-Rollback getrennt dokumentieren.

## 9. Dashboard

Schlankes serverseitiges Dashboard mit eigener kleiner Datenbank. Inhalt: App-Kacheln entsprechend tatsächlicher Zugangsrechte, getrennte Administrationsansicht mit Aktivierung, Domain, installierter Version, Zustand, Update- und Sicherungsstatus, SMTP-Einstellungen mit Testversand sowie ein Betriebsprotokoll administrativer Änderungen ohne Passwörter und Tokens.

Ohne Keycloak hat das Dashboard seine **eigene** Administrationsanmeldung mit TOTP. Vermeide ein zweites konkurrierendes Benutzerverzeichnis: das Dashboard verwaltet Plattformzustand, nicht die Fachbenutzer der Apps.

Der Deployment-Dienst ist eng begrenzt und authentifiziert: feste erlaubte Aktionen, validierte Parameter, Audit-Protokoll, kein Docker-Socket am Dashboard, keine argv- oder Shell-Eingaben aus der Oberfläche. Migrationskommandos stammen ausschließlich aus geprüften Releases. Erkläre in der Dokumentation die verbleibenden Privilegien und Angriffsflächen.

**Lebenszyklus** nach `integration-contract.md`: **ausblenden** verbirgt nur die Kachel, **stoppen** drainiert und behält Daten, **deinstallieren** entfernt Container und Routen und archiviert Daten standardmäßig. Datenvernichtung ist ein eigener irreversibler Vorgang mit ausdrücklicher Freigabe. Eine wieder aktivierte App-ID verwendet bestehende Volumes und führt keinen Bootstrap erneut aus.

## 10. Sicherheitsarbeiten, unabhängig vom Umfang

Diese Punkte sind auch dann zu erledigen, wenn nur eine App migriert wird. Belege jeden mit einem Negativtest.

1. **gswb-Redaktion schließen.** `grundschul_woerterbuch/routes.py:102–139`: `/review`, `review_approve`, `review_toggle_regeneration`, `review_save` haben keine Authentifizierung, CORS steht auf `*`. Im Audit per anonymem POST bestätigt. Alle Schreibpfade und CSRF serverseitig abdecken; die Lese-API bleibt öffentlich.
2. **Dev-SECRET_KEY** in `gswb/grundschul_woerterbuch/__init__.py:26` durch eine Pflichtvariable ersetzen; fehlendes Secret blockiert den Produktionsstart.
3. **Gemeinsames `ADMIN_PASSWORD`** in losverkauf: an eine individuelle Identität binden, vorhandene `edit_tokens` nicht neu erzeugen.
4. **Zackboing-Session ohne Ablaufprüfung** in `userForToken`, Cookie 90 Tage: serverseitigen Ablauf ergänzen.
5. **Bootstrap-Token für grundschultafel.** `mustChangePassword` wird in `src/middleware.ts:37` bereits erzwungen; zu schließen ist das Zeitfenster zwischen erstem Start und erstem Login. Gleichzeitig das Schreiben von `data/users.json` atomar oder gesperrt ausführen.
6. **Eingehende vertrauensbezogene Header am Proxy entfernen**, Proxyadressen explizit zulassen, nur Proxyports veröffentlichen. Beachte, dass Dockers Portveröffentlichung Hostfirewallregeln umgehen kann.

## 11. SSO-Kür, zuletzt

Erst beginnen, wenn Pakete 5 bis 9 abgenommen sind.

**schulwissen:** Der vorhandene Flow in `kern/oidc.py` ist generisches OIDC mit Discovery, Issuer-Prüfung, PKCE S256, State und Nonce; `.env.example:73–83` beschreibt die Nextcloud-App „OIDC Identity Provider" als Anbieter. Konfiguriere ihn gegen die Schul-Nextcloud. Verknüpfung über **`issuer` + `subject`**, niemals über die E-Mail-Adresse. Gleiche unbestätigte E-Mail führt nie zu einer Zusammenführung. Nutzer-Primärschlüssel, Gruppen, Fachrechte und die vorhandene Identitätstabelle bleiben erhalten. Der lokale Login bleibt als Notfallzugang bestehen.

**gswb:** Redaktion hinter Proxy- oder BFF-Auth. Proxy-Auth ist hier zulässig, weil die App keine eigene Benutzeridentität braucht — nur unter der Bedingung, dass direkte Backend-Zugriffe ausgeschlossen sind und alle Schreibpfade erfasst werden.

**Abnahme:** Anmelden in schulwissen über den Identity Provider; Benutzer ohne Freigabe wird auch beim direkten API-Aufruf abgewiesen; öffentliche Routen bleiben erreichbar; ein bestehendes Testkonto wird mit unverändertem Datenbesitz und unveränderten Rollen zugeordnet; Logout und abgelaufene Tokens verhalten sich wie spezifiziert.

**Bekannte Lücke aus dem Audit:** Nach abgeschlossenem Logout beim Identity Provider blieb schulwissen lokal angemeldet. Zentrale Sperrung ist damit noch kein Plattformmerkmal. Entweder schließt du die Lücke über lokale Session-Revokation, oder du dokumentierst ausdrücklich, dass es keine zentrale Sperrung gibt. Behaupte keine Sperrfrist, die du nicht gemessen hast.

Für SL-Journal, schulanmeldung und schulkasse bleibt eigenes TOTP ohne zentrale Sperrung. Lege eine schriftliche Austritts-Checkliste pro App an.

## 12. Messung und Dimensionierung

Zielgröße aus dem Umfangsbeschluss, **geschätzt, nicht gemessen**: 16 GB RAM, 4 dedizierte vCPU, 250 GB SSD für alle 14 Apps ohne Keycloak; etwa 160–200 GB bei zehn Apps.

Zu messen, sobald der Stack läuft:

1. **Leerlauf aller vorgesehenen Apps** auf dem Zielserver. Das ist die wichtigste und billigste Messung — sie entscheidet 16 gegen 32 GB und braucht keinen Lastgenerator.
2. Hauptfall **zehn gleichzeitig aktive Personen** nach dem Szenario in `server-sizing.md`: 5 min Aufwärmen, 20 min konstante Last, 5 min Spitze, danach 60 min Dauerlauf für Speicherwachstum.
3. **Konkurrenz von Hintergrundarbeit**: ein PDF-Slot, ein Import, Mailqueue und ein konsistentes Backup parallel zum Normalbetrieb.
4. Größe des Playwright-Basisimages für abgen (`mcr.microsoft.com/playwright:v1.64.1-noble`) — größter einzelner Plattenposten, im Audit nicht gemessen.

Lastgenerator möglichst auf einem separaten Rechner. Erfasse je Dienst und insgesamt Idle- und Spitzen-RAM, CPU, OOM und Neustarts, I/O-Wartezeit, Datenbankverbindungen, Queue-Länge sowie p50/p95/p99. Addiere Cache und RSS nicht unbesehen.

Zielwerte, zu bestätigen: p95 unter 1 s für gewöhnliche serverseitige CRUD-Anfragen, technische Fehlerrate unter 1 %, keine OOM-Abbrüche, kein wachsender Rückstau. PDF separat, zunächst p95 unter 15 s für eine definierte kleine Vorlage. Fachlich erwartete 403 und 409 nicht als technische Fehler zählen. **Keine Lasttests gegen Produktivdomains.**

Das ausführbare Grundgerüst liegt in `docs/platform-audit/benchmarks/`; die fehlenden App-Fixtures sind dort benannt.

## 13. Lieferergebnisse

Ein neues Plattform-Repository mit:

- `install.sh` oder gleichwertiges Installationsprogramm nach Abschnitt 6.
- `platform.yml` als Override je App sowie die unveränderten eigenständigen Compose-Dateien in den App-Repositories.
- App-Manifeste nach `integration-contract.md`, gegen ein versioniertes JSON-Schema geprüft, mit fixierten Digests.
- Dashboard und begrenzter Deployment-Dienst.
- Backup- und Restore-Dienst nach Abschnitt 8.
- Caddy-Konfigurationserzeugung und Domain-Transaktion.
- `README.md` mit Installation, Betrieb, Grenzen und bekannten Lücken.
- `UPGRADE.md` mit Kompatibilitätsmatrix, Upgrade-Reihenfolge, Wartungsfenster, Sicherung vor Migration und Healthcheck danach; Container-Rollback und Datenbank-Rollback getrennt.
- `docs/messungen/` mit Aufbau, Rohdaten und Auswertung der tatsächlich ausgeführten Messungen.
- Pro migrierter App ein kurzer Abnahmebericht: ausgeführte Tests, Negativtests, Restore-Nachweis, Domainwechsel, Ressourcenbudget.

Je App gilt als fertig: fixierter Commit und Digest, amd64-Build, bestandene Fach- und Negativtests, unveränderte beabsichtigte Eltern-, Kinder- und Öffentlichkeitszugänge, konsistente Sicherung mit Restore in eine leere Umgebung, Domainwechsel mit Rückfall, **und ein nachgewiesener Standalone-Start ohne Plattform**.

## 14. Reihenfolge

| Paket | Inhalt | Abnahme |
| --- | --- | --- |
| A0 | Lizenzdeklaration in den 14 Repositories; Fremdmaterial nach `licenses.md` prüfen | jede ausgelieferte Komponente mit belegter Freigabe oder ausgeschlossen |
| A1 | Sicherheitsarbeiten nach Abschnitt 10 | Negativtest je Punkt |
| A2 | Release- und Manifestgrundlage, Digests, SBOM, Kompatibilitätsmatrix | reproduzierbarer Build einer App |
| A3 | Caddy, Mail-Relay, Secretstore, Compose-Grundstack | Stack startet auf leerem Ubuntu 24.04 |
| A4 | Containerisierung schulwissen und gswb als Vorlage für beide Muster | Standalone- und Plattformstart beide nachgewiesen |
| A5 | Installationsskript nach Abschnitt 6 | zweimaliger Lauf, Abbruch und Fortsetzung, Fremdbestand-Abbruch |
| A6 | Domain-Transaktion nach Abschnitt 7 | Wechsel plus erzwungener Rückfall |
| A7 | Backup- und Restore-Dienst nach Abschnitt 8 | Restore in leere Umgebung |
| A8 | Dashboard und Deployment-Dienst nach Abschnitt 9 | Kacheln und Admin getrennt, Audit-Protokoll, kein Socket |
| A9 | Containerisierung der übrigen acht Apps | je App Abnahme nach Abschnitt 13 |
| A10 | Zielservermessung nach Abschnitt 12 | Leerlauf, Hauptfall, Hintergrundkonkurrenz |
| A11 | SSO-Kür nach Abschnitt 11 | fünf Abnahmepunkte |

A4 ist der erste sichtbare Erfolg: ein nackter Server, ein Kommando, zwei laufende Apps mit Proxy und TLS. Priorisiere ihn.

## 15. Schlussbericht

Nenne ausgeführte und nicht ausgeführte Tests. Gib die gemessene Serverauslastung gegen die geschätzten 16 GB und 4 vCPU an und korrigiere die Empfehlung, falls die Messung abweicht. Benenne verbleibende Lücken ausdrücklich, insbesondere jede Stelle, an der zentrale Sperrung oder zentraler Logout nicht umgesetzt sind. Bezeichne keinen Prototyp als fertige Plattform. Führe keine Produktivumstellung ohne gesonderten Auftrag aus.
