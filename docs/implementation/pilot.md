# Lokaler Zweierpilot

Der Pilot verbindet die echten Standalone-Compose-Dateien von schulwissen und
gswb über ergänzende Overrides mit Caddy, einer eigenen PostgreSQL-Instanz für
schulwissen und Mailpit. Er verändert weder DNS noch produktive Deployments.

Voraussetzungen sind die geprüften Checkouts samt Patches, Python-venv mit
`requirements-dev.txt`, Docker, die checksumgeprüfte Compose-Binärdatei unter
`.work/docker-compose` und die lokal gebauten Images. Die vollständige
Ubuntu-Hostinstallation wird dadurch noch nicht ersetzt.

Vorbereitung in einer neuen Entwicklungsumgebung:

1. Auditcommits mit `scripts/checkout_apps.py` holen und die zugehörigen Patches
   aus `patches/` mit `git am` anwenden.
2. Compose 2.40.3 aus dem offiziellen GitHub-Release laden. Die Datei
   `.work/docker-compose.sha256` enthält die veröffentlichte Prüfsumme;
   der Pilot prüft sie vor jedem Lauf.
3. `.venv/bin/python scripts/pull_pilot_infrastructure.py`
4. `.venv/bin/python scripts/record_container_build.py`
5. `.venv/bin/python scripts/build_schulwissen.py`

Die Infrastrukturimages sind anhand der Audit-Digests fixiert. Die beiden
Appimages sind lokale Entwicklungsimages; der Installationsplan bindet ihre
konkreten lokalen Image-IDs. Ein geänderter Build erfordert einen neuen Pilot-
Zustandsordner oder einen späteren expliziten Upgradepfad. Ein stiller Versionswechsel
wird abgewiesen.

```sh
./install.sh pilot-up --state-dir .work/pilot-v2
./install.sh pilot-status --state-dir .work/pilot-v2
./install.sh pilot-stop --state-dir .work/pilot-v2
./install.sh pilot-start --state-dir .work/pilot-v2
```

`pilot-up` setzt einen unterbrochenen Erstlauf fort. Nach erfolgreicher Installation
verändert ein zweiter Lauf keine Container, Schlüssel oder Installationscheckpoints.
Eine gestoppte Installation wird dabei als gestoppt erkannt; sie wird mit
`pilot-start` gestartet. Start und Stop erzeugen keine neuen Nutzer, Schlüssel
oder Datenvolumes und führen keine Migrationen nochmals aus.

Caddy lauscht auf einem freien Host-Loopback-TLS-Port. Die Namen `wissen.localhost`
und `woerter.localhost` verwenden die lokale Caddy-CA. Die Prüfskripte verbinden
gezielt zu 127.0.0.1 und validieren Zertifikat und Hostname gegen diese CA.
Es werden keine Hosts-Dateien und keine globalen CA-Stores des Hosts verändert.
Caddys Admin-API bleibt im Proxycontainer.

Die Mastersecrets liegen mit Modus 0600 in einem privaten Verzeichnis. Für
Compose werden je App nur die benötigten Dateien in einem Verzeichnis mit Modus
0700 projiziert. Die projizierten Dateien sind für die Nicht-Root-Container
lesbar; andere Hostnutzer erreichen sie wegen des privaten Elternverzeichnisses
nicht. Das ist noch kein verschlüsselter Secretstore mit Offsite-Recovery.

Die Prüfscripte verwenden synthetische Konten und Mailadressen unter
`example.invalid`. Kein externer SMTP-Upstream ist konfiguriert. Die Fixturekonten
sind keine produktive Admininitialisierung. gswbs Redaktion bleibt ohne gesonderte
Redaktionskonfiguration geschlossen.

Ergebnisse und Grenzen: [Umsetzungsbericht](status.md).
