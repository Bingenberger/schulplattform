# Dashboard und Steuerdienst: verbleibende Privilegien und Angriffsflächen

Stand: 4. November 2026, Release-Kandidat 0.1.0-rc2.

## Aufbau

| Komponente | Läuft als | Darf | Darf nicht |
| --- | --- | --- | --- |
| Dashboard (Container `sp-infra-dashboard`) | UID/GID 10001, read-only Root-FS, keine Capabilities | eigene SQLite-DB im Volume `dashboard-state`; Unix-Socket des Steuerdienstes lesen/schreiben; App-Katalog lesen | Docker-Socket, Hostpfade, Shell, Netz außer `sp-management` |
| Steuerdienst (`schulplattform-deploy.service`) | root auf dem Host | feste Aktionen über Docker Compose ausführen | Befehle, Pfade oder Compose-Fragmente aus Anfragen übernehmen |
| Caddy (`sp-infra-proxy`) | Container, nur `NET_BIND_SERVICE` | Ports 80/443 veröffentlichen, Zertifikate in `/var/lib/schulplattform/caddy/data` | Admin-API nach außen (nur `localhost:2019` im Container) |
| Mail-Relay (`sp-infra-mailrelay`) | Container, read-only Root-FS, minimale Capabilities | Mails von den Proxy-Netzen der Mail-Apps annehmen und an den konfigurierten Anbieter weiterreichen | aus dem Internet erreichbar sein; fremde Absender übernehmen (From wird normalisiert) |

## Steuerkanal

- Unix-Socket `/var/lib/schulplattform/management/deploy.sock`, Verzeichnis `root:10001`, Modus `0750`. Der Socket gehört `root:10001`, Modus `0660`.
- Jede Anfrage trägt `action`, `app`, Zeitstempel, eine einmalige Nonce und optional `params`. Sie ist mit HMAC-SHA256 und einem Schlüssel signiert, den nur Steuerdienst und Dashboard kennen (`runtime/dashboard/deployment-key`).
- Der Dienst prüft die Peer-UID (nur 10001), die Signatur, ein Zeitfenster von 60 s und die Wiederholung der Nonce (persistente Tabelle).
- Für jede Aktion gibt es ein exaktes Parameterschema (`schulplattform/deployment.py`, `EXTENDED`). Unbekannte Felder, Zeilenumbrüche, Pfade oder Shell-Zeichen werden abgewiesen. Antworten sind ebenfalls signiert.

Erlaubte Aktionen: `status`, `start`, `stop`, `overview`, `dns-recheck`, `domain-change`, `maintenance`, `smtp-update`, `smtp-password`, `smtp-test`, `backup-now`, `update-check`, `uninstall`, `enable`, `purge`.

## Verbleibende Angriffsflächen

1. **Kompromittiertes Dashboard** (z. B. eine Lücke in Flask oder Werkzeug): Ein Angreifer kann jede der festen Aktionen auslösen. Am schwersten wiegen:
   - `purge`: Datenvernichtung einer zuvor deinstallierten App. Vorher muss eine Sicherung existieren, und der App-Name muss als Bestätigung übergeben werden.
   - `domain-change`: Umleitung einer App auf einen anderen Hostnamen. Der neue Name muss per DNS auf diesen Server zeigen.
   - `smtp-update`: Mailversand über einen anderen Anbieter.

   Er erhält **keinen** Zugriff auf Hostdateien, Docker oder Shell. Gegenmaßnahmen: Dashboard nur über die Verwaltungsdomain, Anmeldung mit Passwort und TOTP, Sitzung maximal 1 h, Betriebsprotokoll.
2. **Steuerdienst als root:** Er ist das einzige Element mit Docker-Zugriff. Eine Lücke in seinem Parser hätte Root-Folgen. Deshalb ist er klein gehalten (JSON-Zeile ≤ 4 KiB, feste Schemas) und mit Tests gegen Injektion abgedeckt (`tests/test_production_services.py`).
3. **Docker-Portveröffentlichung:** Docker umgeht `ufw` für veröffentlichte Ports. Veröffentlicht werden nur 80 und 443 (Caddy). Backends haben keine Host-Ports, das prüft `verify`.
4. **Secrets auf dem Host:** `/var/lib/schulplattform/secrets` (0700, root) und die 0444-Projektionen unter `runtime/` (Verzeichnis 0711, Dateinamen nicht auflistbar). Wer root auf dem Host hat, hat alles.
5. **Backup-Schlüssel:** Er liegt auf dem Server (`secrets/backup-key`). Ohne eine Kopie außerhalb des Servers sind Sicherungen nach einem Totalverlust wertlos. Mit Kopie gilt: Wer Archiv und Schlüssel hat, hat die Daten.
6. **Zentrale Sperrung:** Gibt es nicht. Plattform-Admins erhalten keine Fachrechte in den Apps, und das Sperren eines Plattform-Admins sperrt keine App-Konten.

## Nicht vorhanden (bewusst)

- Kein Docker-Socket im Dashboard.
- Keine freien Kommandos, kein Datei-Upload ins Dashboard.
- Kein Anlegen von Fachbenutzern über das Dashboard. Erstzugänge je App gibt es nur über `./install.sh app-setup APP` an der Konsole.
- Keine Änderung der Verwaltungsdomain über das Dashboard (nur Konsole), damit der Verwaltungszugang bei Fehlern erhalten bleibt.
