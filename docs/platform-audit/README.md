# Entscheidungsvorlage: gemeinsame Schulplattform

> **Nachtrag vom 01.11.2026 — teilweise überholt.** Der verbindliche Umfang steht in
> [scope-decision.md](scope-decision.md). Überholt sind: SSO für alle Apps (jetzt nur
> schulwissen und gswb), Keycloak als Identity Provider (entfällt, stattdessen die
> vorhandene Schul-Nextcloud) und die Gewichtung des Lizenzpunkts als P0-Blocker
> (alle 14 Repositories haben genau einen Autor, der zugleich der Auftraggeber ist).
> Der Aufwand sinkt damit von 187,5–382,5 PT auf etwa 112–231 PT ohne bzw. 120–248 PT
> mit der SSO-Kür. Priorität ist jetzt Installationsskript und zentrale Wartung,
> nicht SSO. Die Befunde dieses Berichts bleiben unverändert gültig.

**Empfehlung:** Für **eine Schule mit 24 Lehrkräften und maximal zehn gleichzeitigen Nutzer:innen** ist eine gemeinsame, selbst gehostete Installation technisch praktikabel. Ein neues Plattform-Repository soll eigenständige App-Images mit Docker Compose, Caddy, Keycloak und internem SMTP-Relay orchestrieren. Daten und fachliche Rechte bleiben je App getrennt. **Schulwissen ist die geeignete Pilot-App**, weil dort bereits echtes OIDC samt kontrollierter Kontoverknüpfung vorhanden ist.

Stand: 1. November 2026. Alle **14 Repositories tatsächlich ausgecheckt und anhand von Code/Konfiguration untersucht**, einschließlich des privaten Schulanmeldung-Repositories über vorhandenen SSH-Zugang. Datum, Branch und vollständige SHAs: [Repositorymatrix](repository-matrix.csv), [Zugriffsnachweise](evidence/repositories.json). Im Arbeitsverzeichnis liegt keine funktionsfähige beschreibbare Gitstruktur vor; Ergebnisse sind als Dateien abgelegt, kein Commit angelegt. Keine Produktivumstellung, Veröffentlichung, echten Benutzerkonten, DNSänderung oder echten E-Mails.

## Die entscheidenden Befunde

- **Beobachtet:** Alle 14 Apps haben serverseitige Funktionen. Der Bestand umfasst Django/Flask/FastAPI/Next/Fastify/Express, PostgreSQL 16/18, SQLite, SQLCipher sowie JSON-/Dateispeicher. Ein pauschaler statischer Webhost reicht nicht. [Einzelberichte](apps/), [Quellinventar](evidence/source-inventory.json).
- **Beobachtet:** Schulwissen bietet den besten SSO-Ausgangspunkt; die anderen Authmodelle benötigen gezielte Adapter. Elternlinks, Kindercodes, TAN, Posten-PWA, Spiel-PIN und Offlinefunktionen dürfen nicht durch einen Login vor allen Routen ersetzt werden. SL-Journal ist ein verschlüsseltes Einbenutzersystem und braucht eine eigene Zugangsentscheidung.
- **Gemessen:** Echter Browserlogin Schulwissen → synthetischer zweiter OIDC-Client ohne zweites Passwort funktioniert. B verweigert fehlende Appfreigabe auch bei direktem APIzugriff. **Eine konkrete Lücke ist nachgewiesen:** Schulwissen bleibt nach abgeschlossenem IdP-Logout lokal angemeldet. Zentrale Sperrung und Logout sind deshalb noch kein fertiges Plattformmerkmal. [Integrationsnachweis](prototype/README.md).
- **Beobachtet/gemessen:** gswb erlaubt derzeit unautorisierte Redaktionsänderungen; mit künstlichem JSONeintrag bestätigt. Grundschultafel erzeugt einen bekannten Erstzugang; mehrere Apps haben lange oder nicht serverseitig ablaufende Sessions. Diese Befunde vor allgemeiner Freigabe bearbeiten, siehe Appmaßnahmen.
- **Offen/blockiert:** Nur SL-Journal enthält eine projektweite MIT-Lizenzdatei. Für die übrigen 13 ist gemeinsame Distribution nicht freigegeben; Grundschultafel erklärt im README sogar ausdrücklich „Nicht zur Weitergabe bestimmt“. Asset-/Abhängigkeitsrechte sind zusätzlich zu klären. [Lizenzbefund](licenses.md).
- **Beobachtet/offen:** Vollständiges gleichwertiges Self-Hosting optionaler KI-/Medienfunktionen ist nicht überall vorhanden: insbesondere Gemini-Handschriftanalyse, YouTube/Galerie und Kartendienste. Ein Mock ist kein funktionaler Ersatz.

## Server und Aufwand

**Vorläufige wirtschaftliche Startplanung:** **4 dedizierte oder 6 verlässlich verfügbare geteilte vCPU, 16 GB RAM und 250 GB SSD**, externe Builds und begrenzte PDF-/Officejobs, angenommen höchstens 50 GB Medien. **Dies ist eine Schätzung, keine nachgewiesene Mindestkonfiguration oder Kapazitätszusage.** 8 GB eignen sich zunächst für eine Appauswahl, 32 GB sind eine Ausbauoption bei nachgewiesenen Engpässen. Ein einzelner Server bleibt ein Ausfallpunkt. Rechnung, Komponentenbudgets und Upgradeauslöser: [server-sizing.md](server-sizing.md).

Die geringe Gleichzeitigkeit reduziert die Nutzlast. Sie beseitigt nicht die Arbeit an 14 verschiedenen Auth-/Daten-/Betriebsmodellen. Vollständige SSO-, Migrations-, Restore- und Betriebshärtung ist ein mehrmonatiges Vorhaben; die Appschätzungen summieren sich separat auf 187,5–382,5 Personentage mit deutlicher Unsicherheit und Überlappung. Einen kleinen technischen Pilot zuerst abnehmen, dann nur tatsächlich benötigte Apps in Wellen integrieren. [Roadmap](implementation-roadmap.md).

## Was praktisch nachgewiesen wurde

24 Schulwissen-Tests und 52 Schulhelfer-Tests bestanden. Schulanmeldung: 445 Tests, ein Fehler in einem zeitabhängigen TOTP-Test; derselbe Einzeltest und ein deterministischer gleicher-Zeitschritt-Test anschließend bestanden. Der Gesamtlauffehler bleibt dokumentiert. 644 Pythondateien ohne Syntaxfehler; daraus folgt keine vollständige Sicherheits-/Laufzeitprüfung.

Produktions-Gunicorn-Wörterbuch mit 1.000 synthetischen Wörtern: zehn virtuelle Nutzer, 30 s Messung nach 5 s Warmup, 298 Leseanfragen ohne technischen Fehler, p95 rund 8,4 ms. **Nur ein kurzer lokaler Lesetest**, kein Leistungsnachweis aller Apps. Kurze Infrastrukturressourcenstichprobe zusätzlich erfasst. Komplette Lastfälle, 60-min-Dauertest und Zielservermessung sind offen.

Echte lokale OIDC-Browserprüfung mit Caddy/Keycloak, öffentlicher Testclientroute und API-Negativfällen; Mail ausschließlich in lokalem Mailpit; synthetischer Schulwissen-DBrestore in leere Datenbank mit gleichem Besitz/Rollen sowie gswb-SQLite-Teilstrestore. Kein vollständiger IdP-/Datei-/Schlüssel-/Offsite-Plattformrestore. Tests/Digests/Rohdaten und verbleibende Grenzen: [tests.md](tests.md), [benchmarks](benchmarks/README.md). Auditprozesse und eigene Testcontainer wurden zum Abschluss gestoppt; synthetische Daten wurden nicht durch globale Aufräumkommandos gelöscht.

## Ergebnisse lesen

| Datei | Inhalt |
| --- | --- |
| [repository-matrix.csv](repository-matrix.csv) | alle 14 Apps, SHA/Stack/Dienste/Auth/Mail/Persistenz, sechs Integrationskategorien, Aufwand |
| [apps/](apps/) | Einzelberichte, konkrete Änderungsschritte und commitgebundene Codeanker |
| [architecture.md](architecture.md) | Komponentenentscheidungen, Datenflüsse, Netze und Vertrauensgrenzen |
| [integration-contract.md](integration-contract.md) | Manifestbeispiel, Konfiguration, Auth/SMTP/Health/Backup und Modulzustände |
| [identity-migration.md](identity-migration.md) | lokale IDs, issuer/sub, Fachrollen, Sonderzugänge, Sperr-/Logoutvertrag |
| [server-sizing.md](server-sizing.md) | Zehn-Personen-Hauptfall, Stresshypothesen, Budgets und Kapazitätsgrenzen |
| [operations.md](operations.md) | Installerspezifikation, Domains, Secrets, Updates, Monitoring und Restore |
| [implementation-roadmap.md](implementation-roadmap.md) | priorisierte Plattform-/Apparbeit, Abhängigkeiten und Abnahmekriterien |
| [open-questions.md](open-questions.md) | ausschließlich verbleibende Entscheidungen und Blocker |
| [licenses.md](licenses.md) / [tests.md](tests.md) | Lizenzgrenzen und ausgeführte/nicht ausgeführte Prüfungen |
| [prototype/](prototype/README.md) / [benchmarks/](benchmarks/README.md) | reproduzierbare Teilnachweise und ausführbare Prüfgrundlage |

**Beobachtet** bedeutet durch Code/Konfiguration/Test belegt; **gemessen** erfordert beschriebenen Aufbau und Rohdaten; **geschätzt** bezeichnet ausdrücklich Annahme/Bandbreite; **offen/blockiert** markiert fehlenden Nachweis/Entscheidung. Entwürfe sind keine vorhandenen Funktionen. Aktuelle offizielle Komponentendokumentation ist in den jeweiligen Berichten direkt verlinkt.

## Die nächsten drei Umsetzungsschritte

1. Benötigte Apps, Lizenz-/Assetfreigaben, Medienmengen, Zielserver und Verfügbarkeitsbedarf festlegen; derzeitige Redaktions-/Bootstraplücken gezielt schließen.
2. Schulwissen-Pilot vervollständigen: native Appfreigabe, 60-Sekunden-Sperrung und globaler Logout, echter Relaypfad, Domainrollback sowie vollständiger IdP-/Datei-/Schlüsselrestore; den zweiten Client danach durch die nächste benötigte reale App ersetzen.
3. Auf einem leeren Zielserver das bestätigte Zehn-Personen-Szenario und Job-/Backupkonkurrenz messen; erst dann Serverprofil freigeben und weitere Apps entsprechend Fachbedarf integrieren. Wirtschaftliche Planungsgröße bleibt bis dahin 16 GB RAM, keine zugesicherte Maximalnutzerzahl.
