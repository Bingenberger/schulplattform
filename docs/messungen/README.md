# Tatsächlich erfasste Messdaten

Es liegt jetzt eine kurze **lokale Leerlaufstichprobe des Zehn-App-Pilots** vor.
Sie ersetzt keine Zielserver-, Last- oder Kapazitätsabnahme. Frühere Auditwerte
werden nicht auf die neue Umgebung übertragen.

[Aufbau, Diensttabelle und Auswertung](local-idle-2026-11-03T202543Z-ebc545/README.md),
[rohe Cgroup-/Host-/DB-/Queue-Proben](local-idle-2026-11-03T202543Z-ebc545/samples.jsonl),
[Metadaten](local-idle-2026-11-03T202543Z-ebc545/metadata.json),
[Zusammenfassung](local-idle-2026-11-03T202543Z-ebc545/summary.json),
[CSV](local-idle-2026-11-03T202543Z-ebc545/services.csv).

Auf TUXEDO OS 24.04, Ryzen 7 7840HS und 16 logischen CPUs wurden nach 30 Sekunden
Aufwärmen 25 Stichproben über 120 Sekunden erfasst. Die 18 Dienste umfassen die
zehn Apps, vier Datenbanken, separaten PDF-/Benachrichtigungsdienst, Caddy und
Mailpit. Dashboard, Dauer-Steuerdienst, Produktiv-Relay sowie Host-/Desktopkosten
sind nicht in den Dienstsummen enthalten.

Beobachtet: gemeinsames Maximum memory.current **1,525 GiB**, anonymer
Cgroup-Speicher maximal **1,020 GiB**, CPU-Intervallmittel **0,378 Kerne**,
Maximum **0,573 Kerne**. Speicheransichten werden nicht addiert.
Kein beobachteter OOM-Abbruch oder Neustart. Der PDF-Renderer blieb kalt;
keine aktive Person, kein Import oder Backup lief im Messfenster.

Die Datenbasis ist klein und synthetisch. Docker-exec-Proben und Healthchecks
sind Teil der beobachteten Last. Ein fremder PostgreSQL-Dienst wurde nicht
einbezogen oder verändert, seine Last kann aber Hostwerte beeinflussen.

## Imagegrößen

[Aktuelles Docker-Inventar](local-idle-2026-11-03T202543Z-ebc545/images.json) enthält die einzelnen
Runtime-Imagegrößen, einschließlich abgen-PDF, und die zusätzliche Inventur des
Playwright-Basisimages: **2.542.930.822 Byte**. Das Dashboard wurde nur inventarisiert,
nicht in dieser Laufzeitstichprobe gemessen. Imagegrößen sind weder RAM-Verbrauch
noch addierbarer physischer Plattenverbrauch; gemeinsame Layer werden geteilt.

## Weiter offen

Die geschätzten 16 GB RAM, 4 dedizierte vCPU und 160–200 GB SSD für zehn Apps bleiben
Planungswerte. Kein Leerlaufnachweis auf dem vorgesehenen Ubuntu-Zielserver, kein
separater Lastgenerator, keine CRUD-Latenz-/Fehlerratenmessung, kein 60-Minuten-
Dauerlauf und keine Konkurrenz von PDF, Import, Mailqueue und konsistentem Backup.
Queuealter und Plattenlatenz fehlen ebenfalls. Ein belastbares Mindestprofil
oder eine geänderte Kaufempfehlung lässt sich aus dieser Stichprobe nicht ableiten.

Änderungspaket: `13498abd4c7684d4200afa7cd09ccc2037f95c2e`. [Geprüfter Commitbeleg](../implementation/evidence/restore-metrics-work-package-commit.log).
