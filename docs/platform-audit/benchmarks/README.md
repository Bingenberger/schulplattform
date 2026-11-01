# Reproduzierbares Benchmarkpaket

Alle gespeicherten Werte stammen von lokaler synthetischer Last. Keine Anfrage gegen Produktivdomains. Die Skripte sind Teilnachweise und eine ausführbare Grundlage, keine bereits vollständige Lasttestsuite für 14 unterschiedliche Fachmodelle.

## Ausgeführt

`raw/gswb-smoke.jsonl` enthält HTTP-Einzelwerte, `raw/gswb-smoke.summary.json` die daraus berechneten Perzentile, `raw/host.json` Hostdaten. Produktions-Gunicorn (kein Flaskdevserver), ein Worker/zwei Threads, SQLite mit 1.000 künstlichen Wörtern aus `prototype/gswb_fixture.py`; eine kleine App, 5 s warmup/30 s Messung, zehn virtuelle Nutzer mit 0,5–1,5 s Denkzeit, gleiche Maschine. Keine Login-/Schreib-/Medien-/KIlast. Responsebytes ohne TLS-/Protokollheader. Redirects werden nicht verfolgt; eine Loginseite wird dadurch nicht als erfolgreicher Fachzugriff gezählt.

```bash
# Repositories anhand der aufgezeichneten SHAs erneut holen:
python3 docs/platform-audit/scripts/checkout.py /tmp/schulplattform-audit/repos
# Python3.12-Umgebung mit geprüften requirements bereitstellen (siehe tests.md).
PYTHONPATH=/tmp/schulplattform-audit/repos/gswb:$PWD/docs/platform-audit/prototype \
AUDIT_FIXTURE_DIR=/tmp/schulplattform-audit/gswb-smoke \
/tmp/schulplattform-audit/test-venv/bin/gunicorn \
  --bind 127.0.0.1:25434 --workers 1 --threads 2 gswb_fixture:app
# Im zweiten Terminal:
python3 docs/platform-audit/benchmarks/load.py \
  docs/platform-audit/benchmarks/gswb-smoke.json \
  --users 10 --warmup 5 --seconds 30 --output /tmp/gswb-rerun.jsonl
```

Die Bibliotheken in `evidence/test-environment.txt` beschreiben den finalen gemeinsamen Testenvstand. Der erste Schulhelfer-Testlauf verwendete den Stand vor zusätzlich installierten Schulanmeldungsanforderungen; Installlogs getrennt archiviert. Für langfristige Reproduktion getrennte Venvs pro App nutzen, nicht blind unterschiedliche Requirements zusammeninstallieren.

## Zielserver-Abnahme vorbereiten

```bash
python3 docs/platform-audit/benchmarks/generate.py /tmp/audit-fixtures
python3 docs/platform-audit/benchmarks/load.py /tmp/audit-fixtures/read-plan.json \
  --users 10 --warmup 300 --seconds 1200 --output /tmp/school-10.jsonl
# Zusätzliche Hypothesen erst nach Hauptfall: 30/120/250 Nutzer, Spitze und 60-min-Lauf.
python3 docs/platform-audit/benchmarks/collect.py \
  --containers schulplattform-audit-keycloak schulplattform-audit-pg \
  --seconds 1800 --output /tmp/resources.jsonl
```

Der generierte Plan enthält bewusst einen Health-Platzhalter für Leseflux: **kein Trainingsbenchmark**. APIroute, Cookie-/CSRFbinding, echte synthetische Klassen-/Text-/Schüler-/Buchungsfixtures und erfolgreiche Schreibpfade zuerst je App implementieren. Generator legt 24 synthetische Erwachsene/400 Kinder an, importiert sie aber nicht in echte Appdatenbanken. `example.invalid` verhindert keine Mailzustellung, wenn ein echter SMTP-Upstream eingeschaltet würde: Tests ausschließlich mit netzisoliertem Sink betreiben.

`load.py` akzeptiert nur Loopback-/privat auflösende .test-Ziele, keine offenen Redirects und keine tokenhaltigen Querystrings. Cookies/CSRFheader aus benannten Umgebungsvariablen beziehen; Werte nie im Ergebnis. Vorplan-Routenanteile, Denkzeiten, Payloadgrößen und erwartete Statuscodes in server-sizing.md. Für zustandsändernde Requests unterstützt der Runner JSON und Header, aber noch keine automatische Formular-/CSRF-/ID-Ermittlung. Dafür Appadapter schreiben, nicht die Authentifizierung zur Vereinfachung abschalten. Auf separatem Lastgenerator .test-Namen gezielt auf Testserver auflösen und dessen Test-CA vertrauen; Adress-/DNSwechsel während Lauf vermeiden.

`collect.py` protokolliert Dockerstats (MemoryUsage/Limit, CPU, NetIO, BlockIO) und Host-Memory/Diskstats/CPU/Pressure. Container-Metrik hängt von Docker/Linux-Cachebehandlung ab: als Working-Set-nahe Dockerstatsangabe kennzeichnen, nicht mit RSS/Pagecache addieren. Diskstats erlauben Deltaberechnung von I/O-Wartezeiten, aber keine vollständige Latenzverteilung. Zusätzlich benötigt: cgroup memory.events/oom_kill und cpu.stat/throttled, restartcount vor/nach, DBpool/-locks/-connections, Queuealter/-länge, WSverbindungen/Broadcastbytes, Host-iostat/Steal und Netzmetriken. Diese Messadapter sind noch nicht vollständig implementiert.

`raw/prototype-resources.jsonl` erfasst eine kurze Stichprobe der Testinfrastruktur während Browserprüfung, nicht alle Appprozesse oder Lastspitzen. Keycloak läuft hier bewusst im Entwicklungsmodus mit H2 und festen Limits, daher keine Übertragung auf den produktiven PostgreSQL-IdP. Kein 60-min-Speicherwachstumsnachweis.

Notwendige Fachtests vor Kapazitätsfreigabe: konkurrierende Schicht-/Platzbuchung (Schulhelfer/Losverkauf), Kassen-/Umbuchungsinvarianten, TANverbrauch/Antwortatomarität, 30/90 Socket.IO-/Yjsverbindungen mit Sperre/Reconnect, begrenzte Chromium-/LibreOfficequeue plus Backup, Loginburst und Tokenrefresh. Nicht ausgeführt, kein Erfolg behauptet. Stopp bei OOM, Fehlerquote >5 % über 30 s oder gefährlicher Hostpressure; Generator stoppen, ursprüngliche Dienste unverändert lassen.
