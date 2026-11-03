# Lokale Leerlaufstichprobe des Zehn-App-Pilots

**Keine Zielserver-, Last- oder Kapazitätsabnahme.** Gemessen wurden zehn Apps und
ihre Testinfrastruktur: 18 Container, ohne Dashboard/Dauer-Steuerdienst und ohne
Produktiv-Relay. Ein fremder PostgreSQL-Container lief weiter und wurde weder
vermessen noch verändert; Hostmetriken können seine und andere Desktoplast enthalten.

## Aufbau

- Datum/Startkennung: 2026-11-03T202543Z.
- TUXEDO OS 24.04, Kernel 7.0.0-113038-tuxedo, x86_64.
- AMD Ryzen 7 7840HS w/ Radeon 780M Graphics, 16 logische CPUs; kein Profil mit vier dedizierten vCPU.
- Kernel meldet 27.13 GiB RAM und 0.50 GiB Swap.
- Docker 29.1.3, Cgroup v2/systemd.
- 30 Sekunden Aufwärmen, 25 Proben alle fünf Sekunden über 120.006 Sekunden.
- Überwiegend leere/kleine synthetische Pilotdaten; keine echten Schuldaten.
- PDF-Renderer blieb kalt; bewusst kein PDF-Auftrag, Import oder Backup während dieses Leerlaufs.
- Keine Cacheleerung. Frühere Abnahmeversuche beeinflussen den OS-/Dateicache.

## Beobachtet

| Kennzahl | Wert |
| --- | ---: |
| Gemeinsames Maximum memory.current | 1.525 GiB |
| Gemeinsames Maximum anonymer Cgroup-Speicher | 1.020 GiB |
| Gemeinsames Maximum current minus inactive_file | 1.396 GiB |
| CPU-Mittel der Intervallwerte | 0.378 Kerne |
| Höchster beobachteter Intervallwert | 0.573 Kerne |
| OOM-Kills / Neustarts im Fenster | 0 / 0 |
| Niedrigstes Host-MemAvailable | 23.268 GiB |
| Höchstes Host-I/O-Wait / Steal | 0.050 % / 0.000 % |

Die drei Speicherzeilen sind **verschiedene Sichten derselben Belegung** und
werden nicht addiert. memory.current umfasst Cgroup-Ladungen einschließlich
Dateicache und Kernelanteilen; anon ist kein vollständiges Prozess-RSS/PSS.
current minus inactive_file ist eine Arbeitsmengen-Näherung. Dienstmaxima können
zu verschiedenen Zeitpunkten auftreten und sind ebenfalls nicht zu einem
gleichzeitigen Gesamtmaximum zu addieren. CPU=1,0 entspricht einem ausgelasteten
logischen Kern, nicht einem Prozent der gesamten Maschine.

## Je Dienst

| Dienst | Maximum memory.current MiB | CPU-Mittel Kerne |
| --- | ---: | ---: |
| gswb/app | 164.75 | 0.0067 |
| schulwissen/app | 138.29 | 0.0343 |
| zackboing/app | 89.56 | 0.0124 |
| schulhelfer/app | 104.05 | 0.0354 |
| losverkauf/app | 63.04 | 0.0527 |
| grundschultafel/app | 60.93 | 0.0130 |
| fahrradausbildung/app | 288.16 | 0.0387 |
| leseflux/app | 57.77 | 0.0203 |
| kompetenz-manager/app | 158.40 | 0.0356 |
| abgen/app | 70.16 | 0.0127 |
| kompetenz-manager/worker | 93.66 | 0.0450 |
| abgen/pdf | 157.44 | 0.0297 |
| schulwissen/db | 25.28 | 0.0104 |
| fahrradausbildung/db | 30.45 | 0.0098 |
| leseflux/postgres | 28.96 | 0.0097 |
| abgen/postgres | 58.02 | 0.0097 |
| infra/proxy | 13.63 | 0.0001 |
| infra/mailpit | 6.71 | 0.0014 |

Alle Dienste waren gesund oder hatten keinen eigenen Docker-Healthcheck
(Caddy); die zehn Apps und ihre geprüften Zusatzdienste waren bereit.
Keine Probe ist ausgefallen. Haupt-PID, Startzeit, Image und RestartCount
blieben stabil; dadurch werden auch manuelle Neustarts ohne erhöhten
Docker-RestartCount erkannt.

Beobachtete sonstige DB-Verbindungen (ohne den jeweiligen Mess-Backend):
schulwissen maximal 2, Fahrradausbildung 2, Leseflux 1 und abgen 1.
Losverkauf hatte keine wartende Outboxzeile, Kompetenz-Manager keine unerledigte
Benachrichtigung; der abgen-PDF-Slot war frei und kalt. Diese beiden nativen
Queueproben sind kein vollständiges Plattform-Queue-Monitoring. Queuealter und
SQL-Abfragelatenz wurden nicht erfasst.

## Rohdaten und Methode

- [Metadaten, Auswahl, Image-IDs und Limits](metadata.json)
- [Unveränderte Stichproben](samples.jsonl)
- [Auswertung](summary.json)
- [Dienstwerte als CSV](services.csv)
- [Tatsächliche Imagegrößen](images.json)

Der Collector liest die Cgroup-v2-Dateien der ausdrücklich ausgewählten
Compose-Dienste. PID-/Image-/Startzeit- und Projekt-/Service-Labels werden
geprüft; fremde Container werden nicht einbezogen. CPUwerte entstehen aus
usage_usec-Differenzen und monotoner Zeit. Block-I/O-Bytes, Host-iowait/steal
und PSI werden gespeichert, daraus folgt keine Messung der Plattenlatenz.
Proben für PostgreSQL und die nativen Queues/PDF-Status erzeugen selbst etwas
Last. Diese Docker-exec-Last ist in Dienst-/Hostwerten enthalten; der äußere
Collector und Docker-Daemon gehören nur zur Hostlast.

Reproduktion aus dem Repositorywurzelverzeichnis:

```sh
.venv/bin/python scripts/measure_pilot_idle.py --state-dir .work/pilot-v21 --seconds 120 --warmup 30 --interval 5
```

Das Werkzeug verlangt den akzeptierten Zehn-App-Pilot, startet seine
bestehenden Dienste ohne Bootstrap, misst und stoppt sie wieder. Volumes und
Schlüssel bleiben erhalten. Fehler/Unterbrechung erzeugen einen ausdrücklichen
Unvollständigkeitsmarker; fehlende Queueproben sind unbekannt statt null.

## Aussagegrenze

Die geschätzten 16 GB/4 vCPU werden weder bestätigt noch widerlegt.
Nicht ausgeführt: Zielserver-Leerlauf, Zehn-Personen-CRUD mit p50/p95/p99 und
Fehlerrate, 5/20/5-Minuten-Lastprofil, 60-Minuten-Speicherlauf sowie PDF-/Import-/
Mail-/Backup-Konkurrenz. Die kleine Datenbasis und der kalte Renderer bilden
keine vollen Schulbestände oder einen bereits benutzten Chromiumprozess ab.
Die Stichprobe ist kein Beleg gegen langfristiges Speicherwachstum.
Keine RPO-/RTO- oder Verfügbarkeitszusage. Alle Testdienste wurden danach
gestoppt; Daten, private Schlüssel und der fremde Container blieben erhalten.
