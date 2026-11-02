# Zackboing: lokaler dritter Pilotdienst

Beobachtet am 2. November 2026. Eigenständiger Appcommit und exportierbarer Patch
stehen in [patches/index.json](../../patches/index.json). Noch keine Produktionsfreigabe.

## Laufzeit und Start

Der amd64-Build verwendet Node 22.23.4 mit fixiertem Basisdigest und `npm ci`.
better-sqlite3 11.10.0 läuft unter ABI 127 mit SQLite 3.49.2.
Die im Audit gescheiterte native Installation ist damit im Container gelöst.
[Build](evidence/zackboing-build-runtime.log), [Metadaten](evidence/zackboing-image.json).

```sh
.venv/bin/python scripts/build_zackboing.py
./install.sh pilot-up --state-dir .work/pilot-v3 --apps gswb,schulwissen,zackboing
./install.sh pilot-stop --state-dir .work/pilot-v3
./install.sh pilot-start --state-dir .work/pilot-v3
```

Eine bestehende Zweierinstallation wird nicht still erweitert. Sie behält ihre
Appauswahl und ihren Plandigest. Neue Auswahl erfordert einen neuen Zustandsordner;
ein produktiver Upgradepfad ist noch offen. Die Compose-Standalone-Datei bleibt
im Apprepository und funktioniert ohne Plattform-Override.

Explizite Migration unter exklusiver SQLite-Transaktion, Schemaversion 1.
Readiness und API/WebSockets bleiben vor Migration gesperrt. Lokaler Bootstrap
nur über kontrollierendes Terminal, maximal 15 Minuten, Hashspeicherung und
transaktionaler einmaliger Verbrauch. Keine offene Erstregistrierung.

Runtime: UID:GID 10001:10001, Initprozess, Read-only-Root, tmpfs 64 MiB, gesetzte
Limits 384 MiB/1 CPU/128 Prozesse. Persistenz `/data` mit DB und Uploads.
Diese Limits sind keine Kapazitätsmessung. Das Image ist ein lokales
Entwicklungsimage; veröffentlichter Registrydigest, SBOM und Lizenzfreigabe fehlen.

## Ausgeführte Abnahmeprüfungen

| Prüfung | Beobachtetes Ergebnis |
| --- | --- |
| Standalone-Compose ohne Plattform | 117 Fach-/Negativprüfungen bestanden, lokale Galeriefixture, Neustart erhält Daten |
| Bootstrap | Import migriert nicht, Ablauf, private Hashspeicherung, zwei konkurrierende Erstzugriffe ergeben genau einen Admin |
| TLS/WebSocket | Zertifikatsprüfung mit lokaler CA; öffentliche PINs funktionieren, fremde Origin abgewiesen |
| Sessionablauf | HTTP und neues host:create auch auf offener Verbindung abgewiesen |
| Stop | Aktives Spiel blockiert Stop; Dashboard zeigt 409 mit Betriebsprotokoll; nach Spielende Stop/Start ohne Migration |
| Domaintransaktion | Neue Laufzeit-URL, Login, QR und WebSocket-Origin geprüft; erzwungener Fehler rollt zurück |
| Kombinierter Restore | DB-.backup und Medien in neues leeres Volume; App startet ohne Bootstrap/Migration, IDs/Rollen/Dateien erhalten |
| Wiederholung | Zwei Installationsläufe ohne Änderung an Containern, Schlüsseln oder Checkpoints |

Rohbelege: [Standalone](evidence/zackboing-standalone.json),
[Fachtestlog](evidence/zackboing-e2e.log),
[Bootstrap](evidence/zackboing-bootstrap.log),
[Node-LTS-Sicherheitstests](evidence/zackboing-runtime-security.log),
[TLS-Spiel](evidence/zackboing-platform.json),
[Clientlog](evidence/zackboing-platform-client.log),
[Domains](evidence/zackboing-domains.json),
[Restore](evidence/zackboing-restore.json),
[Restorekommandos](evidence/zackboing-restore-operations.json),
[Lifecycle](evidence/zackboing-lifecycle.json),
[Pilotkommandos](evidence/pilot-v3-operations.jsonl).

Bei der Entwicklung scheiterten zunächst der Clientzugriff auf die private
Fixtureverzeichnis-Mount und eine falsche Podium-Eventbezeichnung im Test.
Danach wurden einzelne Fixturedateien schreibgeschützt projiziert und das
tatsächliche Ereignis `player:podium` verwendet. Wiederholte TLS-Prüfungen nutzten
das bereits erzeugte synthetische Konto; Bootstrap ist separat und im
Standalone-Erstlauf geprüft. Die Rohbelege zeigen die anschließend erfolgreichen Läufe.
Der Initprozess wurde ergänzt, nachdem Stop zuvor bis zum Timeout wartete.

## Grenzen

Spielzustände bleiben im Speicher. Der lokale Controller drainiert neue Spiele
und verweigert Stop während aktiver Runden. Manuelles Compose-Stop umgeht diese
Prüfung. Bestehende Host-/Rejoin-Capabilities laufen bis Spielende weiter:
keine zentrale Sessionrevokation oder zentrale Sperrung behauptet.

Domainprüfungen verwenden ausschließlich .localhost und eine lokale CA.
Keine öffentliche DNS-/Besitz-/ACME-Abnahme, kein Mail- oder OIDC-Flow in dieser App.

`schulplattform.snapshot` ist ein generischer lokaler Baustein für SQLite und/oder
deklarierte Verzeichnisse. Aufruf nur bei pausierten Writern und exklusivem Zugriff
auf das Restoreziel. Das Inventar prüft SHA256, Schema, Fremdschlüssel und UID/GID;
Links, Spezialdateien, Pfadausbruch und nichtleere Ziele werden abgewiesen.
Dateien werden 0600, Verzeichnisse 0700 wiederhergestellt. Aktuell unkomprimierte
Tararchive, höchstens 512 MiB Nutzdaten und 20.000 Einträge. Der Testhelper hat
zusätzlich begrenztes tmpfs. Keine Verschlüsselung, kein Offsiteziel, keine
Rotation/Alarmierung und noch keine gemeinsame Plattform-/Secretstore-Sicherung.
Keine Ausfallsicherheitszusage bei Hostabbruch während der Restoreübernahme.

Alle Accounts, Spiele und Medien sind synthetisch. Testdienste werden gestoppt,
Volumes und lokale Archive bleiben zur Prüfung erhalten. Leerlauf-/Lastmessung
auf Ubuntu und Abnahme der sieben weiteren Apps stehen aus.
