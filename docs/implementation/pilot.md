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

## Optionaler dritter Dienst: Zackboing

Nach Anwendung der Zackboing-Patches das Image mit
`scripts/build_zackboing.py` bauen und einen neuen Zustandsordner wählen:

```sh
./install.sh pilot-up --state-dir .work/pilot-v3 --apps gswb,schulwissen,zackboing
```

Die Auswahl wird dauerhaft gespeichert. Bestehende Konfigurationen ohne
Appauswahlschlüssel behalten exakt den Zweierplan. Neue Auswahl bei bestehenden
Installationen wird abgewiesen. Zackboing erhält ein eigenes internes Proxynetz,
Laufzeit-Origin `https://quiz.localhost:<TLS-Port>` und ein eigenes Datenvolume.
Der Controller führt nur beim Erstlauf die explizite Migration aus; es wird dabei
kein Account angelegt.

Stop, konsistente Sicherung und Domainwechsel verweigern den Eingriff bei aktiven
Spielen. Die erweiterte Abnahme und die sieben noch nicht integrierten Apps sind
in [Zackboing](zackboing.md) beziehungsweise im [Status](status.md) dokumentiert.


## Optionaler vierter Dienst: Schulhelfer

Nach dem Build mit `scripts/build_schulhelfer.py` eine neue Installation anlegen:

```sh
./install.sh pilot-up --state-dir .work/pilot-v7 --apps gswb,schulwissen,zackboing,schulhelfer
```

Schulhelfer erhält einen eigenen Session-Schlüssel, ein eigenes SQLite-Datenvolume
und ein internes Proxynetz. Mailpit ist dort ausschließlich als lokaler Sink ohne
Upstream erreichbar. Die explizite Migration läuft nur im Erstlauf. Erstadmin
und Fachrechte werden nicht aus dem Dashboard übernommen.

[Stand und Abnahme](schulhelfer.md) enthalten die ausgeführten Fach-, Negativ-,
Restore-, Domain- und Parallelbuchungsprüfungen sowie die Grenzen von Mailqueue,
Legacy-Adoption und Browserassets. Bestehende Zwei-/Dreierkonfigurationen werden
nicht umgeschrieben. Nach neuen Runtime-Builds ist ein neuer Pilotzustandsordner
erforderlich; der lokale Pilot ersetzt keinen produktiven Upgradecontroller.


## Optionaler fünfter Dienst: Losverkauf

Mit `scripts/build_losverkauf.py` bauen und einen neuen Pilotzustandsordner verwenden:

```sh
./install.sh pilot-up --state-dir .work/pilot-v10 --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf
```

Losverkauf besitzt eigene feste Session-/Elternschlüssel, ein eigenes SQLite-Volume,
Maps-/Mailverzeichnisse, ein internes Proxynetz und eine begrenzte lokale Mailqueue.
Der Erstlauf migriert das Schema, erzeugt aber keinen Standardadmin. Die persönliche
Identität wird lokal konfiguriert. Bereits installierte Auswahlen bleiben erhalten.

[Losverkauf-Abnahme](losverkauf.md) nennt Standalone, kombinierten Restore,
individuelle Elternlinks nach Domainwechsel und die Grenzen von SMTP-Duplikaten,
nativen Alt-Automationen und noch fehlender Browser-/Produktionsabnahme.

## Optionaler sechster Dienst: Grundschultafel

Nach scripts/build_grundschultafel.py in einem neuen Zustandsordner mit --apps
gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel installieren.
Die geprüfte Umgebung ist .work/pilot-v12. Grundschultafel erhält einen eigenen
Session-Schlüssel, ein privates JSON-/Asset-Volume und internes Proxynetz.
Der Erstlauf führt ausschließlich node scripts/migrate.mjs aus. Persönlicher
Erstzugang wird separat lokal am Terminal eingerichtet.

[Grundschultafel-Abnahme](grundschultafel.md) enthält Standalone, parallele
Nutzeränderungen, widerrufbare Sitzungen, mobile Uploadtickets, Login-/QR-
Domainwechsel, Rückfall und Restore in ein leeres Volume. Unterrichtsmedien
müssen nach Lizenzklärung ausdrücklich bereitgestellt werden.

## Optionaler siebter Dienst: Fahrradausbildung

Nach scripts/build_fahrradausbildung.py in einem neuen Zustandsordner mit --apps
gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung
installieren. Die geprüfte Umgebung ist .work/pilot-v14. Eigene PostgreSQL-Instanz,
beschränkte Approlle, Credentials, Vorlagenvolume und internes Proxynetz.
Der Erstlauf führt nur python -m app.migrate aus, keinen Konto- oder Seedjob.

[Fahrradausbildung-Abnahme](fahrradausbildung.md) enthält Standalone, gemeinsame
Workerlimits, QR-Domainwechsel und PG-/Vorlagenrestore. Vor Domainwechsel
Postengeräte vollständig synchronisieren: IndexedDB/PWA bleibt an die alte
Browser-Origin gebunden. Serverbackup enthält keine ungesendeten Geräteereignisse.
