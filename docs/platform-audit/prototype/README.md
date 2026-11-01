# Isolierter Integrationsnachweis

**Tatsächlich ausgeführt**, Stand 01.11.2026: Caddy 2.11.7, Keycloak 26.8.1, reale Schulwissen-App am dokumentierten Commit, synthetischer Flask/Authlib-Testclient B, PostgreSQL 16.15 und Mailpit 1.33.0. Alle Netzwerkports nur Loopback. Keine Produktionsdomains/Benutzer/Daten und kein externer SMTP-Upstream. Images mit tatsächlich verwendeten Digests in [prototype-images.json](../evidence/prototype-images.json). Kein fertiges Plattformprodukt.

Keycloak läuft nur für diesen Versuch als `start-dev` mit H2; dies ersetzt nicht den geplanten produktiven IdP mit PostgreSQL. App A/B laufen über Produktions-Gunicorn auf dem Host in isolierten Venvs. Das ist **kein vollständiger Containerbuild der Plattform**. Schulwissen verwendet den vorhandenen nativen Authlib-OIDC-Flow; App B ist ausdrücklich ein Testclient und keine zweite integrierte Schulapp.

## Ergebnisse gegen die neun Prüfpunkte

| Nr. | Prüfschritt | Ausführung und Grenze |
| --- | --- | --- |
| 1 | Login A → B ohne zweites Passwort | **Bestanden:** Browser meldet sich über Caddy/Keycloak in Schulwissen an; B führt Codeflow ohne erneute Passworteingabe aus. [Browserrohprotokoll](../evidence/prototype-browser.log) |
| 2 | Fehlende Appfreigabe auch direkt API | **Teilnachweis bestanden für B:** anonyme API 401, Benutzer `denied` ohne B-Rolle Callback 403, API danach weiter 401. **Offen für Schulwissen:** Mapping allein ist noch keine zentrale Appfreigabe-/Revokationsprüfung. |
| 3 | Öffentliche Routen erreichbar | **Bestanden für B /public und gswb-Lese-API**; Eltern-/Kinder-/Offlinewege der übrigen Apps nicht durch SSO-Prototyp getestet. |
| 4 | Bestehendes Testkonto mit Besitz/Rolle | **Bestanden als kontrollierte administrative Zuordnung:** vorher lokales Testkonto, Gruppe Lehrkraft, eigenes Dokument; issuer/sub zugeordnet, echter OIDC-Login. Wiederinitialisierung und Restore vergleichen User-/Dokument-/Identitäts-/Gruppenzahlen und owner=1. Kein interaktiver Migrationswizard und keine echten Konten. |
| 5 | Logout/Sperre/abgelaufene Tokens | **Gap nachgewiesen:** IdP-Logout beendet Schulwissen-Sitzung nicht; separater Test bestätigt erneute Passwortanforderung am IdP bei weiter gültiger lokaler A-Session. B weist nach 60-s-ID-Token-Lebensdauer ab. Falsche Signatur/Audience/Issuer/Nonce/State in vorhandenen Schulwissen-Tests geprüft. Zentrale Sperrung, Backchannel-Logout und 60-s-Revokationsvertrag **nicht implementiert/getestet**. |
| 6 | Domain-/Callbackänderung mit Rückfall | **Nicht ausgeführt.** Ablauf spezifiziert in operations.md; noch kein implementierter transaktionaler Domaincontroller. Nächster Test: zweite .localhost-Origin in Caddy/IdP/App gemeinsam eintragen, Login und Mail-Link prüfen, ungültige Änderung injizieren, alte Konfig wiederherstellen. |
| 7 | Mail ausschließlich Testpostfach | **Bestanden für App-SMTP → Mailpit:** Django-SMTP sendet eine synthetische Mail, Sink meldet eine Nachricht. **Kein Postfix-Relaynachweis**: Test ging direkt zum Sink; Absenderbindung/Auth/Retry des geplanten Relays bleiben offen. |
| 8 | Neustart/erneute Einrichtung | **Teilnachweis:** eigener PG-Container neu gestartet, User/Dokument bleiben je 1; `run_host.py init` wiederholt ohne neue Objekte/Migrationen. gswb-Schema zweimal initialisiert und alle 1.000 Wörter erhalten. Gesamter Container-/IdP-/Dateineustart nicht abgenommen. |
| 9 | Backup in leere Umgebung | **Teilnachweis bestanden:** pg_dump -Fc der synthetischen Schulwissen-DB in neue leere DB `audit_restore`, Besitz/Rollen/Anzahlen identisch; gswb-SQLite-Backup-API in leeres Verzeichnis, integrity_check ok. Kein kompletter Plattform-/IdP-/Datei-/Schlüsselrestore, keine RPO-/RTO-Zusage. |

Die positiven Logeinträge zur fortbestehenden A-Session bestätigen bewusst einen **Befund**, keine erfüllte Logoutanforderung. Alle Grenzen auch in [tests.md](../tests.md).

## Wiederholung in eigener lokaler Testumgebung

Vorbereitung: ausreichend freier RAM (für diesen Teilstack mindestens mehrere GB als Testreserve), freie Ports 25425/25426/25432/25440–25443, Docker, Chromium und zwei Python3.12-Venvs. Keine vorhandenen gleichnamigen Container überschreiben. Benötigte Pakete/Versionen aus Installlogs, UV-Lock und `evidence/test-environment.txt`; Appcheckouts über `scripts/checkout.py`. Tatsächlich verwendete Digests aus `prototype-images.json` statt später veränderter Tags verwenden.

```bash
python3 docs/platform-audit/scripts/checkout.py /tmp/schulplattform-audit/repos
UV_CACHE_DIR=/tmp/schulplattform-audit/uv-cache \
UV_PYTHON_INSTALL_DIR=/tmp/schulplattform-audit/python \
uv sync --frozen --project /tmp/schulplattform-audit/repos/schulwissen
# Separate Venv anlegen, requirements und Authlib/requests/playwright installieren;
# die finale getestete Paketliste steht in evidence/test-environment.txt.
python3 docs/platform-audit/prototype/prepare.py
```

`prepare.py` verweigert das Überschreiben bestehenden Realm-/Secretzustands. Realm importiert nur `audit` und `denied`, beide mit dem ausdrücklich synthetischen Passwort `synthetic-local-only`; zwei getrennte Clientsecrets werden zufällig erzeugt und nie ausgegeben. Dieses Testpasswort darf nur in der isolierten Loopbackumgebung verwendet werden. Secretzustand liegt unter /tmp, nicht im Git/Auditbericht.

```bash
docker run -d --name schulplattform-audit-pg --label schulplattform.audit=true \
  --memory=192m --cpus=1 -p 127.0.0.1:25432:5432 \
  -e POSTGRES_PASSWORD=audit-local-only -e POSTGRES_DB=audit postgres:16-alpine
docker create --name schulplattform-audit-caddy --label schulplattform.audit=true \
  --network host --memory=96m --cpus=.5 caddy:2.11.7-alpine
docker cp docs/platform-audit/prototype/Caddyfile schulplattform-audit-caddy:/etc/caddy/Caddyfile
docker start schulplattform-audit-caddy
docker run -d --name schulplattform-audit-mailpit --label schulplattform.audit=true \
  --memory=96m --cpus=.5 -p 127.0.0.1:25425:1025 \
  -p 127.0.0.1:25426:8025 axllent/mailpit:v1.33.0
docker create --name schulplattform-audit-keycloak --label schulplattform.audit=true \
  --memory=1536m --cpus=1 -p 127.0.0.1:25440:8080 \
  -e KC_HOSTNAME=https://login.audit.localhost:25443 -e KC_PROXY_HEADERS=xforwarded \
  quay.io/keycloak/keycloak:26.8.1 start-dev --import-realm
# Importverzeichnis im synthetischen State erzeugen, Dateirechte UID1000 erhalten:
mkdir -p /tmp/schulplattform-audit/integration/kc-import
cp /tmp/schulplattform-audit/integration/realm.json /tmp/schulplattform-audit/integration/kc-import/school-audit-realm.json
docker cp -a /tmp/schulplattform-audit/integration/kc-import schulplattform-audit-keycloak:/opt/keycloak/data/import
docker start schulplattform-audit-keycloak
# Nach Caddy-Start und CA-Erzeugung:
docker cp schulplattform-audit-caddy:/data/caddy/pki/authorities/local/root.crt \
  /tmp/schulplattform-audit/integration/caddy-root.crt
```

Bei anderem Host-UID Importdateien im **Testcontainer** lesbar für Keycloak-UID1000 machen. Vor Start der Apps DBreadiness und Discovery abwarten, ohne feste Startupzeit anzunehmen. Im durchgeführten Versuch wurde das fehlende Importverzeichnis nachträglich im eigenen Container erstellt und Keycloak neu gestartet; der finale Zustand entspricht dem Verzeichnisimport oben. Caddy nutzt Hostnetz, bindet aber explizit nur 127.0.0.1 und ::1. Keine globale CA-Vertrauensinstallation: `run_host.py` setzt REQUESTS_CA_BUNDLE nur für seine Prozesse. Playwright ignoriert Zertifikatsfehler nur im isolierten Testbrowser; das ersetzt keinen produktiven Zertifikatstest.

```bash
python3 docs/platform-audit/prototype/run_host.py init
# Je eigenes Terminal:
python3 docs/platform-audit/prototype/run_host.py a
python3 docs/platform-audit/prototype/run_host.py b
# Browser-/SMTP-/Restoreprüfungen:
/tmp/schulplattform-audit/test-venv/bin/python docs/platform-audit/prototype/browser_check.py
/tmp/schulplattform-audit/test-venv/bin/python docs/platform-audit/prototype/logout_check.py
python3 docs/platform-audit/prototype/run_host.py mail
python3 docs/platform-audit/prototype/pg_restore_check.py
```

`pg_restore_check.py` verlangt eine noch nicht vorhandene Ziel-DB und überschreibt keine bestehende DB. Für einen zweiten Versuch eigene neue Zielumgebung anlegen; keine pauschale Löschroutine. `run_host.py init` verwendet ausschließlich die eigens benannte lokale Auditdatenbank; Bootstrap/Fixtures nicht gegen produktive Verbindungsdaten verwenden. Gswb-Teilsnapshot mit `check_gswb.py` wiederholen. Browsertests benötigen Chromium unter /usr/bin/chromium; Testclient ist bewusst minimal, ohne produktive MFA-/Revokations-/Backchannelintegration.

Auditprozesse werden nach Abschluss gestoppt; Testcontainer/Daten bleiben identifizierbar erhalten, es werden keine fremden Container gestoppt/gelöscht. Eigene Container später gezielt nach Label prüfen; kein globales `docker system prune` und kein `compose down -v`. Verbleibender synthetischer State unter /tmp kann durch Neustart verschwinden; reproduzierbare Skripte und bereinigte Resultate liegen hier.
