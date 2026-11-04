# Nachauftrag für den Coding-Agenten: produktionsfähige Installation, Domains, Zertifikate und Datenübernahme

Stand: 4. November 2026. Auftraggeber: Florian Emrich.

Dieser Nachauftrag ergänzt den [Umsetzungsauftrag](Coding_Agent_Umsetzungsauftrag_Schulplattform.md). Alle dortigen harten Randbedingungen (Abschnitt 3), Arbeitsweise (Abschnitt 2) und Berichtsregeln (beobachtet / gemessen / geschätzt / offen) gelten unverändert weiter. Wo dieser Nachauftrag konkreter ist, gilt er.

## 1. Ausgangslage

Der Zehn-App-Pilot läuft lokal. Alle Änderungen sind in den App-Repositories und im Plattform-Repository auf `main` gepusht. Laut `docs/implementation/status.md` und dem Code fehlt jedoch, was den Pilot zu einer Installation auf einem echten Server macht:

- `./install.sh apply` bricht mit „host provisioning/bootstrap/verification not yet implemented“ ab.
- `schulplattform/pilot.py` verwendet fest verdrahtete `*.localhost`-Domains (`DEFAULT_DOMAINS`) und eine lokale CA (`local_certs`). Es gibt keine Möglichkeit, eigene Domains anzugeben, und keine ACME-Konfiguration.
- `schulplattform/domains.py` ist ein Transaktionskern. DNS-, Besitz-, ACME- und Callback-Prüfungen sind als Treiberaufgaben offen.
- Images werden lokal als `*:0.1.0-dev` gebaut. Es gibt kein veröffentlichtes, signiertes Releasebundle mit Digests.
- Das Dashboard kann nur Status, Start und Stopp. Domains, Zertifikate, Updates, Backups und SMTP fehlen in der Oberfläche.
- Die Übernahme echter Bestandsdaten ist nicht implementiert und nie getestet worden (`UPGRADE.md`).

## 2. Rahmen beim Auftraggeber

- **Der Zielserver existiert noch nicht.** Alles wird so vorbereitet, dass am Tag der Bereitstellung gilt: leeres Ubuntu Server 24.04 LTS (amd64), DNS-Einträge gesetzt, **ein Kommando** installiert die Plattform vollständig.
- **Jede App läuft unter einer eigenen Subdomain**, z. B. `wissen.example-schule.de` und `tafel.example-schule.de`. Der Auftraggeber legt **jeden Hostnamen einzeln per DNS-Eintrag** (A/AAAA) auf den Server. Es gibt keinen Wildcard-Eintrag und keinen DNS-API-Zugang. Die Hostnamen müssen nicht unter einer gemeinsamen Elterndomain liegen.
- Zusätzlich gibt es eine **eigene Verwaltungsdomain** für das Dashboard, getrennt von allen App-Domains.
- **Die Apps laufen heute produktiv auf einem Altserver** mit nicht automatisch aktualisierten Deployments. Ihre Daten sollen auf den neuen Server übernommen werden. Weitere Installationen gibt es nicht.

## 3. Arbeitspakete

### N1 – Release- und Imagepipeline

Ziel: Der Server baut nichts aus ungeprüften Quellen. Er bezieht versionierte Images, die über Version und Digest fixiert sind.

- Je App-Repository ein reproduzierbarer Build des amd64-Images aus einem getaggten Commit, veröffentlicht in einer Registry (Vorschlag: GitHub Container Registry unter `ghcr.io/bingenberger/<app>`). Begründe die Wahl der Registry und lege eine Alternative offen, falls GHCR ungeeignet ist (z. B. für private Repos).
- Die SBOM und den Digest je Image ins Releasebundle aufnehmen. Das Bundle mit dem vorhandenen Ed25519-Mechanismus (`schulplattform/bundle.py`) signieren. Der Vertrauensschlüssel wird unabhängig vom Bundle verteilt.
- Ein Releasebundle referenziert alle zehn Apps, die Infrastruktur-Images (Caddy, PostgreSQL, Mail-Relay, Dashboard) und die Kompatibilitätsmatrix aus `UPGRADE.md`.
- Für die Entwicklung bleibt der lokale Build aus den gepinnten Commits erhalten. Er darf jedoch nie die produktive Installation speisen.
- **Kein `latest`.** Ein unbekannter oder veränderter Digest blockiert die Installation.

**Abnahme:** Release `0.1.0` für alle zehn Apps veröffentlicht. `./install.sh plan --bundle … --trusted-key …` verifiziert es. Ein manipuliertes Bundle und ein manipulierter Digest werden jeweils abgewiesen.

### N2 – Installationskonfiguration und Domainzuordnung

- Eine versionierte, schemageprüfte Konfigurationsdatei (z. B. `/etc/schulplattform/platform.toml`) enthält mindestens:
  - die Verwaltungsdomain,
  - je App: aktiviert ja/nein und Hostname,
  - eine ACME-Kontakt-E-Mail,
  - die ACME-Umgebung (`staging` | `production`),
  - die SMTP-Upstream-Einstellungen (optional, ohne Secrets in der Datei),
  - das Backup-Ziel.
- Zusätzlich ein interaktiver Assistent, der diese Datei erzeugt. Secrets werden nie als Shellargument übergeben.
- Die Hostnamen sind je App frei wählbar. Doppelte Hostnamen, IP-Literale und Kollisionen mit der Verwaltungsdomain werden abgewiesen (die Logik existiert in `proxy.hostname` und `Domains.validate`).
- Die Konfiguration ersetzt `DEFAULT_DOMAINS` vollständig. Alle abhängigen Werte werden aus dem Hostnamen abgeleitet: App-Basis-URL, `ALLOWED_HOSTS`, CORS/CSRF-Origins, WebSocket-Origin, Mail-, QR- und Elternlinks sowie OIDC-Callbacks. Je App ist das im Manifest deklariert. Wo eine öffentliche URL beim Build eingebrannt wird, gilt Abschnitt 7 des Hauptauftrags.

### N3 – DNS-Prüfung und Zertifikate

- **Caddy mit ACME** über HTTP-01 bzw. TLS-ALPN-01, mit einem Zertifikat je Hostname. Kein Wildcard, keine DNS-Challenge.
- **Vor** jeder Zertifikatsanforderung je Hostname prüfen:
  - Die öffentliche Auflösung (A/AAAA) zeigt auf diesen Server. Dafür die eigene öffentliche Adresse ermitteln, ohne Drittdienste blind zu vertrauen; den Weg dokumentieren.
  - Die Ports 80 und 443 sind von außen erreichbar. Wo das ohne externen Helfer nicht beweisbar ist, ehrlich als „nicht geprüft“ melden.
- **Teilbereitschaft ist der Normalfall:** Weil der Auftraggeber jeden Eintrag einzeln umstellt, darf ein noch nicht umgestellter Hostname die übrigen Apps nicht blockieren. Je App gibt es den Zustand `dns-ausstehend` → `zertifikat-ausstehend` → `aktiv`. Nicht bereite Apps bleiben ohne öffentliche Route. Die Installation ist trotzdem erfolgreich und meldet die ausstehenden Hostnamen. Ein späterer Lauf oder eine Dashboard-Aktion „DNS erneut prüfen“ aktiviert sie.
- Zuerst gegen die Let's-Encrypt-**Staging**-Umgebung, dann Umschaltung auf Produktion. Rate-Limits und Fehlschläge dürfen keine Wiederholungsschleife auslösen.
- Der Zertifikatszustand ist persistent und wird im Backup gesichert. Ablaufdaten, letzte Erneuerung und Fehler sind abrufbar.
- Die Caddy-Admin-API bleibt nur intern erreichbar. Weiterhin gilt: keine Docker-Discovery.

### N4 – Installer `apply` auf leerem Ubuntu 24.04

Die Zustandsmaschine aus Abschnitt 6 des Hauptauftrags wird vollständig umgesetzt (`preflight → plan → provision → bootstrap → verify → completed`). Neu bzw. konkretisiert:

- **Provision:**
  - Docker Engine und Compose-Plugin aus den offiziellen Paketquellen in fixierter Version installieren, nur wenn noch nicht vorhanden. Vorhandenes bricht weiterhin mit Übernahmeplan ab.
  - Firewall: nur 22, 80 und 443. Dabei die Docker-Portveröffentlichung beachten.
  - Systembenutzer, Verzeichnisse, Secretstore, Images per Digest ziehen, Netzwerke und Volumes anlegen.
  - Die SSH-Konfiguration nicht verändern.
- **Bootstrap:**
  - Dashboard-Admin über die lokale Konsole (der vorhandene Weg `dashboard setup`).
  - Erstzugänge je App über die vorhandenen App-CLIs, ebenfalls nur über die Konsole.
  - Kein Standardpasswort.
- **Verify:**
  - Readiness und Negativzugriff je aktiver App.
  - TLS-Kette je aktivem Hostname gültig, nicht die lokale CA.
  - Testmail in den Sink bzw. Testversand nur auf ausdrückliche Anforderung.
  - Backup und Restore-Probe.
- **Dienste dauerhaft einrichten:** Dashboard (gunicorn hinter Caddy auf der Verwaltungsdomain) und Deployment-Dienst als systemd-Units. Neustart des Hosts → alles läuft wieder.
- Der zweite Lauf ist ein No-op. Ein unterbrochener Lauf wird fortgesetzt. Fremdbestand (Docker oder nginx vorhanden) führt zum Abbruch mit klarer Meldung.

### N5 – Dashboard: Domains, Zertifikate, Betrieb

Erweiterungen der Administrationsansicht. Alle Änderungen laufen über **feste, neu hinzuzufügende Aktionen** des Deployment-Dienstes mit validierten Parametern, HMAC und Audit-Protokoll. Weiterhin gilt: kein Docker-Socket am Dashboard, keine Shell- oder argv-Eingaben.

- **Domains:** je App Hostname, DNS-Status, Routenstatus und die Aktion „DNS erneut prüfen“. **Domain ändern** als Transaktion nach Abschnitt 7 des Hauptauftrags: Vorschau/Diff ohne Secrets → Prüfung → Anwenden → Verifikation → automatischer Rückfall. Die Verwaltungsdomain lässt sich nur über die Konsole ändern, damit der Zugang erhalten bleibt.
- **Zertifikate:** je Hostname Aussteller, Ablaufdatum, letzte Erneuerung und letzter Fehler. Eine manuelle Erneuerung nur als begrenzte, rate-limitierte Aktion.
- **Updates:** installierte Version je App, verfügbares signiertes Release, Kompatibilitätsprüfung. Das Update selbst läuft mit Sicherung vor der Migration, exklusiver Migration und Healthcheck danach, gemäß `UPGRADE.md`.
- **Backups:** letzter erfolgreicher Lauf je App, Größe, Ziel, letzte Restore-Probe.
- **SMTP:** Upstream-Einstellungen, Secret nur schreibbar und nie angezeigt, Testversand an eine eingegebene Adresse. In automatisierten Tests ausschließlich gegen den Sink.
- **Lebenszyklus** (ausblenden / stoppen / deinstallieren mit Archivierung / Datenvernichtung mit ausdrücklicher Freigabe) gemäß Abschnitt 9 des Hauptauftrags.

### N6 – Datenübernahme vom Altserver

Auf dem Altserver wird **nichts verändert**. Alle Schritte dort sind lesend und werden vom Auftraggeber selbst ausgeführt.

1. **Inventurskript für den Altserver** (lesend, ohne Root, wo möglich). Es erfasst je App:
   - Commit/Version, Datenbank-Engine und Schemastand (Alembic-, Django-, Drizzle- und Prisma-Revision bzw. `user_version`),
   - Datenpfade und Größen, Namen der Secrets (ohne Werte), Betriebsart (systemd/Docker).
   
   Die Ausgabe ist eine JSON-Datei ohne personenbezogene Daten.
2. **Exportskript für den Altserver.** Es erzeugt einen konsistenten Export je App: SQLite über die `.backup`-API, PostgreSQL über `pg_dump -Fc`, Dateien als Snapshot. Dazu gehören die nötigen Schlüssel, z. B. Session- und Token-Secrets, damit Elternlinks und Tokens gültig bleiben. Der Export ist verschlüsselt und hat eine Prüfsumme. Kurzer Schreibstopp je App nur nach Ankündigung.
3. **Importbefehl auf dem neuen Server** (`./install.sh import --app <id> --archive …`):
   - Trockenlauf mit Bericht, danach die eigentliche Übernahme.
   - Er schließt die bekannten Lücken: Adoptionspfade für unversionierte Bestandsdatenbanken bei **schulhelfer, fahrradausbildung, abgen** und für ältere Schemata bei **kompetenz-manager**. Jeder dieser Pfade ist gegen den im Inventar gefundenen tatsächlichen Stand geprüft.
   - IDs, Rollen, Datenbesitz, Elternlinks und QR-Tokens bleiben erhalten. Wo das nicht möglich ist (z. B. losverkauf-Elterntoken unter 32 Zeichen), wird das vor der Übernahme gemeldet; nichts wird still neu erzeugt.
   - Nach dem Import werden geprüft: Datensatzanzahlen je Tabelle, Fremdschlüssel, Eigentümerschaft, ein Login mit einem bestehenden Konto und ein öffentlicher Link.
4. Ein **Umzugs-Runbook** mit der Reihenfolge je App, Schreibstopp, DNS-Umstellung (TTL vorher senken), Rückfall auf den Altserver und der Liste, wer sich neu anmelden muss.

**Abnahme ohne echte Daten:** Ein synthetischer „Altbestand“ je App, erzeugt aus dem **Basis-Commit vor den Plattformänderungen** (`baseCommit` in `patches/index.json`) mit dessen eigenem Startweg, wird exportiert, importiert und verifiziert. Echte Schülerdaten werden in diesem Auftrag nicht verarbeitet.

## 4. Abnahme ohne Zielserver

Weil es den Server noch nicht gibt, erfolgt die Abnahme in einer **lokalen Ubuntu-24.04-VM** (z. B. QEMU/KVM, LXD oder Multipass; beschreibe den Aufbau reproduzierbar):

- Eine lokale ACME-Testinstanz (z. B. Pebble) und ein lokaler DNS-Resolver simulieren öffentliche Hostnamen unter `.example.invalid` oder einer reservierten Testdomain. Kein Einsatz echter Produktivdomains.
- Nachzuweisen sind:
  - zweimaliger Lauf (der zweite ist ein No-op), Abbruch und Fortsetzung, Fremdbestand-Abbruch;
  - Teilbereitschaft: drei Hostnamen ohne DNS-Eintrag → später nachgezogen → aktiviert;
  - Domainwechsel mit Login, Mail-Link und QR-Code sowie erzwungener Rückfall;
  - Neustart des Hosts → alles läuft wieder;
  - Restore in eine leere VM;
  - Import des synthetischen Altbestands aller zehn Apps.
- Ein **Checkliste „Tag der Bereitstellung“** für den echten Server: Hostinganforderungen (16 GB / 4 vCPU / 250 GB als Ausgangsschätzung), DNS-Einträge je Hostname, Ports, Reihenfolge der Kommandos, Umschaltung Staging → Produktion, erwartete Ausgaben.

Was nur auf dem echten Server prüfbar ist (öffentliche Erreichbarkeit, echtes Let's Encrypt, Messungen aus Abschnitt 12 des Hauptauftrags), wird als **offen** gemeldet und nicht als bestanden.

## 5. Reihenfolge

| Paket | Inhalt | Abnahme |
| --- | --- | --- |
| N1 | Release- und Imagepipeline | signiertes Release 0.1.0, Manipulation abgewiesen |
| N2 | Konfiguration und Domainzuordnung | alle abgeleiteten URLs aus der Konfiguration, keine `localhost`-Konstanten im Produktionspfad |
| N3 | DNS-Prüfung und Zertifikate | Teilbereitschaft und ACME gegen Pebble in der VM |
| N4 | `install.sh apply` | Abnahmen aus Abschnitt 4 |
| N5 | Dashboard-Erweiterungen | jede neue Aktion mit Negativtest und Audit-Eintrag |
| N6 | Datenübernahme | synthetischer Altbestand aller zehn Apps übernommen und verifiziert |

N1 bis N4 haben Vorrang. Die SSO-Kür (A11) bleibt zurückgestellt.

## 6. Lieferergebnisse

- Code und Tests im Plattform-Repository, Build-Workflows in den App-Repositories. Commits je Arbeitspaket.
- Aktualisierte `README.md` und `UPGRADE.md`.
- `docs/betrieb/bereitstellung.md` (Checkliste Tag der Bereitstellung), `docs/betrieb/umzug.md` (Runbook Altserver) und `docs/betrieb/dashboard.md` (verbleibende Privilegien und Angriffsflächen).
- Je Paket ein Abnahmebericht mit ausgeführten Kommandos, Rohausgaben und den Kategorien beobachtet / gemessen / geschätzt / offen.

## 7. Fragen

Stelle höchstens fünf entscheidungsrelevante Fragen, etwa zur Registry, zum Backup-Ziel außerhalb des Servers oder zum SMTP-Anbieter. Arbeite unabhängig davon weiter. Bezeichne keinen VM-Nachweis als Abnahme auf dem Zielserver.
