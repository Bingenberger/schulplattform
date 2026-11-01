# Serverdimensionierung

> **Nachtrag vom 01.11.2026 — zwei Korrekturen.** Siehe
> [scope-decision.md](scope-decision.md), C1 und C2.
>
> **C1, Worker-Zahl:** Keine der 14 Apps hat eine Job-Queue; WeasyPrint (schulwissen,
> schulkasse, schuleva, fahrradausbildung) und LibreOffice (kompetenz-manager, SL-Journal)
> laufen synchron im Request. Die Budgettabelle unten rechnet mit einem Worker pro App;
> ein Export blockiert dann die App für alle Nutzer. Realistisch sind mindestens zwei
> Worker für diese sechs Apps, geschätzt +0,8 GiB Idle und +1,5 GiB Last.
>
> **C2, CPU-Spalte:** Die Spalte `CPU vCPU Budget` summiert 5,65 vCPU, empfohlen werden
> 4 dedizierte. Beim RAM wurde additiv mit 30 % Reserve gerechnet, bei der CPU nicht.
> Die Spalte ist als Limit zu lesen, nicht als Bedarf.
>
> **Ergebnis nach Korrektur und ohne Keycloak: 16 GB RAM und 4 dedizierte vCPU tragen
> alle 14 Apps** (Last ~9,35 GiB, RAM ~13,5 GiB). 32 GB sind nicht erforderlich.

## Planungsbasis und Aussagegrenze

**Vom Auftraggeber bestätigt:** eine Schule, 24 Lehrkräfte, maximal zehn gleichzeitig aktive Personen (Nachricht während des Audits). 350–450 Kinder aus dem Prüfauftrag sind eine Daten-/Szenarioannahme, keine bestätigte Kontenzahl. Eltern-/Veranstaltungsspitzen über zehn hinaus werden nur als optionale Stresshypothese gerechnet. Unbekannt: Medienbestand, Zielserver, Verfügbarkeitsziel.

**Beobachtet:** 14 serverseitige Apps, unterschiedliche Python-/Node-Prozesse, vier PostgreSQL-Apps mit PG16/PG18-Vorgaben, zusätzliche SQLite-/Dateibestände; Chromium bei abgen, LibreOffice bei Journal/Kompetenz, WeasyPrint bei mehreren Apps. Daher ist „14 statische Frontends“ keine passende Größenannahme. Ein gemeinsam genutzter Dienst wird nachfolgend nur einmal gezählt; Budgets mit mehreren Instanzen sind bereits Gesamtsummen.

**Gemessen:** nur ein kurzer lokaler gswb-Lesetest mit Produktions-Gunicorn und synthetischen Daten, kein Kapazitätsnachweis. [Rohdaten](benchmarks/raw/gswb-smoke.jsonl), [Zusammenfassung](benchmarks/raw/gswb-smoke.summary.json), [Host](benchmarks/raw/host.json). Zehn virtuelle Nutzer, Denkzeit 0,5–1,5 s, 5 s Warmup/30 s Messung, 1.000 synthetische Wörter, ein Gunicorn-Worker/zwei Threads, SQLite; keine Medien, externe KI im Mockmodus, Lastgenerator auf demselben Host. 298 Anfragen in Messphase, 9,93 rps; p50 5,553 ms / p95 8,416 ms / p99 12,504 ms; technische Fehler 0/298. Dies sind Antwortzeiten zweier kleiner öffentlicher Leserouten, keine CRUD-/Login-/PDF-/Schulplattformleistung. Kalter Cache nicht separat gemessen; Cache warm nach fünf Sekunden, OS-Cache nicht geleert.

Host: Intel i5-10500, sechs physische Kerne/zwölf Threads; 7.707 MiB RAM und 7.706 MiB Swap, zu Beginn nur rund 1,2–1,5 GiB verfügbar und rund 7,2–7,5 GiB Swap belegt. CachyOS Rolling/amd64, Kernel siehe Rohdaten; Docker 29.9.2/Compose 5.6.1. /tmp ist tmpfs, daher kein repräsentativer SSD-/NVMe-I/Otest. Andere Anwendungen liefen bereits, deren Last wurde nicht verändert. Dedizierter Anteil/Hostbelegung unkontrolliert; gswb ohne eigenes Containerlimit, isolierte Test-PG16 mit 192 MiB/1 CPU. CPU/RAM/OOM/I/O/Queue-/DBpool-Metriken für die 14 Apps wurden nicht vollständig erfasst. Später wurden rund 4,3 GiB verfügbar, wodurch der begrenzte SSO-Teilstack ausgeführt werden konnte. Es existiert keine repräsentative gemeinsame Leerlauf-/Lastmessung und kein belegtes Mindestprofil.

## Lastszenarien für Abnahme

| Szenario | Gleichzeitige Personen und Verteilung | Aktionen und erwartete rps vor Reaktionszeit |
| --- | --- | --- |
| Leerlauf | alle 14 Apps, keine aktive Person | Healthchecks getrennt zählen, z. B. 14/30 s ≈ 0,47 rps plus Infrastruktur |
| Schulalltag (Hauptfall) | 10: 4 Wissen, 2 Kompetenz, 2 Leseflux, 1 Tafel, 1 Helfer | je Person 1 fachliche Aktion/6 s, im Mittel 1,5 HTTP-Requests/Aktion ≈ 2,5 rps; Burstfaktor 3 ≈ 7,5 rps |
| Kollegium (Stress) | 30: 12 Wissen, 6 Kompetenz, 6 Lesen, 3 Tafel, 3 Helfer | gleiche Denkzeit ≈ 7,5 rps |
| Unterricht (Stress) | 30 Erwachsene + 90 Kinder, Kinder je 30 Lesen/Wörterbuch/Quiz | Erwachsene 7,5 rps; 60 Lesekinder je Aktion/10 s × 1,5 = 9 rps; Quiz 30 offene WS, Antworten/Broadcast separat |
| Spitze (Stress) | 250: 10 Mitarbeiter, 120 Helfer-Eltern, 60 Losverkauf-Eltern, 60 Kinder | Eltern 1 Aktion/15 s × 2 Requests ≈ 24 rps; Kinder 1/10 s × 1,5 ≈ 9 rps; Mitarbeiter 2,5 rps, gesamt ≈ 35,5 plus WS; nur bei tatsächlicher Relevanz bestätigen |
| Hintergrund | Hauptfall plus ein PDFslot, ein Import, Mailqueue und konsistentes Backup | HTTP wie Hauptfall, Jobs/Mail/DBwrites separat; keine 14-fache Vollnutzung ansetzen |

Routen-/Payloadklassen: Lesen 1–10 KiB JSON bzw. 10–100 KiB HTML, Schreiben 1–20 KiB JSON/Form, Upload 0,5–5 MiB, Export 1–20 MiB; Annahmen durch tatsächliche Exemplare ersetzen. 70 % Lesen / 20 % Speichern / 10 % Listen/Exportanstoß als Hauptfallhypothese, an Fachaufgaben anpassen. Dynamische IDs/CSRF müssen aus synthetischen Appfixtures kommen. Lange PDFs nicht dem CRUD-p95 zuschlagen. Die Werte sind keine konstanten rps je virtuellem Nutzer: tatsächliche rps sinken mit Latenz und bestehen aus mehreren Requests pro Aktion.

SSO: zehn Neuanmeldungen binnen zehn Sekunden und getrennt 24 binnen einer Minute, danach sessiongestützte Appwechsel; Refresh-Jitter z. B. 20 % gegen synchronen Refresh. Erwartungswerte etwa 1 Passwortlogin/s bzw. 24/60 = 0,4/s, nicht 14 × Nutzerzahl. 10 erneuernde Sessions bei fünfminütigem Token ergeben im Mittel 0,033 Refresh/s je jeweils aktiver Clientsession; ungleichmäßig verteilte Clients explizit testen. Login-/MFA-/Sperr-/Logout-Tests im Browser, nicht per unzulässigem Password-Grant ersetzen.

Auf separatem Lastgenerator: 5 min warmup, 20 min konstant, 5 min Spitze, danach 60 min Dauerlauf. Vorgeschlagene Abnahme: gewöhnliche CRUD-p95 <1 s, technische Fehler <1 %, keine OOM/Neustarts, kein wachsender Rückstau; erwartete 403/409 separat zählen. PDF separat zunächst p95 <15 s für definierte kleine Vorlage, Timeout/Überlauf/Queue hart begrenzen; Ziel nach Vorlage bestätigen. Bei Kasse/Los/Helfer/Schuleva Schreibkonkurrenz und Integrität prüfen (keine verlorene Buchung, keine Überbuchung, Einmal-TAN/Antwort atomar). WS: 30/90 Verbindungen, Broadcastbytes/Antwortzeit, Wiederverbindung und Sperre testen. Kein Lasttest gegen Produktivdomains.

## Komponentenbudgets

**Alles in der folgenden Tabelle ist geschätzt**, nicht aus gemessenen RSS-Werten abgeleitet. Kleine Prozesse: ein Worker pro App, statische Auslieferung separat, externe Builds, jeweils nur begrenzte schwere Jobs. Idle-/Lastspalten sind Prozess-/Dienstbudgets inklusive angenommener Caches, keine Summe aus RSS und Pagecache. CPU ist ein Arbeitsbudget im definierten Zehn-Personen-Szenario, kein gemessener Bedarf; nicht jede Zeile erreicht gleichzeitig den Wert. Daten-/Wachstumswerte sind synthetische Planungsgrößen, nicht vorhandene Schulbestände. Ungewissheit grob Faktor 0,5–2, bei Medien/Exports darüber. Herkunft: Implementationsbefunde in [Matrix](repository-matrix.csv), Budgetannahmen hier; [CSV](evidence/component-budgets.csv).

| Komponente | Instanzen | Idle GiB gesamt | Last GiB gesamt | CPU vCPU Budget | Startdaten GiB | Wachstum GiB/Jahr | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| schulwissen | 1 | 0.18 | 0.45 | 0.25 | 1 | 1 | geschätzt |
| fahrradausbildung | 1 | 0.13 | 0.35 | 0.2 | 0.5 | 0.25 | geschätzt |
| schulanmeldung | 1 | 0.2 | 0.45 | 0.25 | 1 | 1 | geschätzt |
| SL-Journal | 1 | 0.18 | 0.4 | 0.2 | 2 | 2 | geschätzt |
| kompetenz-manager | 1 | 0.2 | 0.5 | 0.3 | 2 | 2 | geschätzt |
| leseflux-api | 1 | 0.18 | 0.4 | 0.25 | 0.5 | 0.5 | geschätzt |
| schuleva | 1 | 0.15 | 0.4 | 0.25 | 0.2 | 0.2 | geschätzt |
| gswb | 1 | 0.1 | 0.25 | 0.2 | 1 | 1 | geschätzt |
| grundschultafel | 1 | 0.25 | 0.6 | 0.4 | 2 | 3 | geschätzt |
| schulkasse | 1 | 0.12 | 0.35 | 0.25 | 0.5 | 0.5 | geschätzt |
| abgen-api | 1 | 0.15 | 0.35 | 0.25 | 0.5 | 0.5 | geschätzt |
| abgen-web + leseflux-web | 2 | 0.04 | 0.08 | 0.05 | 0.1 | 0 | geschätzt |
| abgen-pdf | 1 | 0.05 | 0.9 | 0.7 | 0.1 | 0 | geschätzt |
| losverkauf | 1 | 0.08 | 0.18 | 0.15 | 0.1 | 0.1 | geschätzt |
| schulhelfer | 1 | 0.12 | 0.28 | 0.2 | 0.1 | 0.1 | geschätzt |
| zackboing | 1 | 0.08 | 0.2 | 0.3 | 0.5 | 0.5 | geschätzt |
| postgres16 shared | 1 | 0.25 | 0.6 | 0.35 | 2 | 1 | geschätzt |
| postgres18 abgen | 1 | 0.15 | 0.4 | 0.25 | 1 | 1 | geschätzt |
| keycloak | 1 | 0.8 | 1.25 | 0.4 | 0.5 | 0.3 | geschätzt |
| caddy | 1 | 0.03 | 0.08 | 0.1 | 0.1 | 0.05 | geschätzt |
| dashboard/deployer | 2 | 0.11 | 0.28 | 0.15 | 0.2 | 0.1 | geschätzt |
| postfix-relay | 1 | 0.04 | 0.1 | 0.05 | 0.2 | 0.1 | geschätzt |
| monitoring bounded | 1 | 0.1 | 0.25 | 0.15 | 1 | 0.2 | geschätzt |

Idlebudgets zusammen **3.69 GiB**, konservativ addierte Lastbudgets **9.10 GiB**. Dazu etwa 1 GiB Betriebssystem/Daemonbedarf; mit 30 % Reserve ergibt `(Last + 1) × 1,30 ≈ 13.1 GiB`. Das vorsichtige Addieren aller Lastspalten bildet mehrere gleichzeitige Peaks ab und ist bei zehn Personen bereits konservativ, ersetzt aber keine Messung. Zusätzlicher LibreOffice-Export kann 0,5–1 GiB brauchen: über Slots verhindern, dass PDF/Office/Backup gleichzeitig alle Limits ausreizen. Containerlimits nicht gleich Reservationswerte setzen: z. B. leichte Apps 384–768 MiB, Next 1 GiB, PDF 1,5 GiB, IdP 2 GiB als Startlimits, danach messen. Summe theoretischer Limits kann 16 GiB überschreiten; Admission/Jobbegrenzung nötig, Reserve sonst nicht echt. Swap ist keine RAMkapazität.

Keycloak-Budget ist eine eigene kleine Schätzung. Die [Herstellerreferenz](https://www.keycloak.org/high-availability/single-cluster/concepts-memory-and-cpu-sizing) beschreibt eine andere Cache-/Loginlast; deren Werte werden nicht als Mindestbedarf einer Schule ausgegeben.

## Profile: Korrektur der Vorplanung

| Profil | Vorläufige Bewertung nach Codeeinsicht |
| --- | --- |
| 4 vCPU / 8 GB / 100–160 GB | Technische Erprobung einer Auswahl, alle 14 mit IdP/Chromium/Office nicht freigegeben; kein nachgewiesenes Mindestprofil |
| **4 dedizierte oder 6 verlässlich verfügbare geteilte vCPU / 16 GB / 250 GB SSD** | **Wirtschaftlicher Einstieg als zu prüfende Planung für eure 10 gleichzeitigen Personen**, externe Builds, begrenzte Exporte, Medienannahme ≤50 GB; keine Kapazitätszusage |
| 8 vCPU / 16 GB / 200–300 GB aus Auftrag | Weiterhin brauchbare konservative Prüfgröße; acht CPUs sind für zehn Personen aus Codelektüre nicht als notwendig belegt |
| 8–12 vCPU / 32 GB / 300–500 GB | Ausbauoption bei parallelen Office/PDFjobs, viel Medien oder bestätigten Veranstaltungsspitzen, keine Garantie für 250 Personen |

CPUentscheidung nach gemessenen Reaktionszeiten und CPUsteal/throttling treffen. Vier dedizierte Kerne sind kalkulierbarer als vier überbuchte VPS-vCPU; Anbieterpreise hier nicht untersucht. Shared VPS bei guter Messung wirtschaftlich, aber Reservierungs-/Noisy-Neighbour-Risiko; kein generelles Urteil aus der Zahl der vCPUs. Normallast sollte dauerhaft deutlich unter ~60–70 % CPU liegen; Build-/Restorezeiten separat.

**Speicherrechnung, geschätzt:** OS/Tools 15 GB + aktuelle/vorherige Images 25 + DBs 10 + Uploads/Medien 50 + begrenzte Logs/Monitoring 5 + temporäre Exporte 10 + lokales Backup-Staging 60 = 175 GB; 30 % Reserve ≈ 228 GB, deshalb 250 GB. Vorhandene große Audios/Bilder/Journalanhänge können das sofort überholen. Bei 100 GB Mediendaten neu rechnen. Externe Backupfläche separat zunächst 300–600 GB Planungsrahmen bei Deduplizierung/Retention, ohne Deduplizierung kann tägliche Vollkopie von 60 GB × 34 gehaltenen Ständen >2 TB beanspruchen. Retentions-/Zuwachsmodell vor Bestellung klären. Immutable Backups und getrennte Schlüsselkosten nicht unter lokaler SSD verstecken.

**Netzwerkrechnung, geschätzt:** 24 Lehrkräfte × 22 Tage × 30 Sitzungen/Tag × 0,5 MB/Sitzung ≈ 7,9 GB/Monat; zusätzlich 400 angenommene Kinder × 8 Sitzungen/Monat × 2 MB ≈ 6,4 GB; 300 Exporte × 5 MB = 1,5 GB; angenommene 5 GB Medien ergibt ~21 GB Nutzlast, mit Faktor 2 für Reload/Overhead ~42 GB/Monat. Hier meint Sitzung eine kurze Nutzungseinheit, kein IdP-Konto. Medien/Video abweichend neu rechnen. Täglich 1 GB inkrementelles Offsitebackup zusätzlich ~30 GB/Monat, initialer Upload ~60 GB separat. Spitze 10 Nutzer laden je 5 MB binnen 5 s → 80 Mbit/s, daher 100 Mbit/s Uplink für diesen Burst knapp ausreichend; 1 Gbit/s wünschenswert bei Medien/Restore. KI-/YouTube-/Kartendienste verursachen eigene Kosten/Datenübertragung und sind nicht im Serverbedarf enthalten.

Keine Server-GPU erforderlich anhand der nachgewiesenen Workloads; Gemini extern und Fabric/Quizgrafik im Browser begründen keine GPU. Lokale OCR/Modelle wären neue Architektur mit neuem Benchmark.

## Upgrade- und Ausfallgrenzen

Vorläufige messbare Auslöser: CRUD-p95 >1 s oder technische Fehler ≥1 % in drei vergleichbaren 20-min-Fenstern; RAM available <20 % über 15 min/Memorypressure oder jeder OOM; CPU >70 % über 15 min mit Latenzanstieg/Steal >5 %; Schreib-/Disklatenz >20 ms anhaltend mit Lockrückstau; Jobqueuealter wächst >10 min; Platte >70 % belegt mit prognostiziert <30 Tagen Reserve. Erst langsame Routen, Poolgrößen/Jobs und SQL prüfen, dann passende CPU/RAM/SSD vergrößern. Mehr RAM löst weder langsame externe API noch verlorene Mails.

Ein Server bleibt ein Ausfallpunkt, auch mit 32 GB. Vorläufig kein HAauftrag; Offsitebackup/Restore und Ausfallalarm zuerst. Mehrere Schulen erfordern neue Isolation, Secret-/Netz-/Daten-/Backupgrenzen und Kapazitätsmessung; keine lineare Hochrechnung aus Kontenzahlen. Vor Bestellung Hauptszenario auf leerem Zielserver mit vollständigem Pilotstack messen; erst daraus belastbare Mindestgröße ableiten.

## Gemessene kurze Infrastrukturstichprobe

Während der Browserprüfung wurden je 12 Dockerstatsproben über etwa 80 Sekunden erfasst: Keycloak 519,2–545,2 MiB (CPUmaximum 101,83 % ≈ ein Kern), Caddy 8,1–14,8 MiB, Mailpit 11,6–14,1 MiB, PG16 14,4–24,7 MiB. [Rohdaten](benchmarks/raw/prototype-resources.jsonl), [Zusammenfassung](benchmarks/raw/prototype-resources.summary.json). Testlimits: IdP 1.536 MiB/1 CPU, Caddy/Mailpit je 96 MiB/0,5 CPU, PG16 192 MiB/1 CPU. Keine OOMKilled-/RestartCount-Ereignisse laut abschließender Containerzustandsabfrage; ein manueller PG-Neustart wurde getrennt durchgeführt (Docker RestartCount zählt nicht einfach jeden manuellen Neustart). Kein produktiver PostgreSQL-IdP: Keycloak verwendete H2/start-dev. App-A/B-Pythonprozesse sind nicht in dieser Containerstatistik enthalten. Diese Stichprobe korrigiert keine 14-App-Lastbudgets und beweist keine Langzeitstabilität.
