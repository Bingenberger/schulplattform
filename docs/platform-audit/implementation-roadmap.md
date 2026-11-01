# Priorisierter Integrationsplan

**Geschätzt:** Personentage bei einer erfahrenen entwickelnden Person, eine Schule/24 Lehrkräfte/zehn gleichzeitig aktive Personen. Keine neuen fachlichen Funktionen. Bandbreiten keine Termine; Plattform/Apparbeiten teilweise gemeinsam durchführbar. Fachliche Rückfragen, Lizenzfreigaben und native Abhängigkeiten erhöhen Unsicherheit. Vertrauensgrad mittel aus Codeprüfung, niedrig für vollständige Migration/Produktionsbetrieb.

## Reihenfolge und Abnahme

| Priorität / Paket | Aufwand | Abhängigkeit | Abnahmekriterium |
| --- | ---: | --- | --- |
| P0 Lizenz-/Assetinventar und Umfang entscheiden | 3–7 PT Technik, juristische Wartezeit separat | Rechteinhaber/Schule | Jede ausgelieferte App/Asset mit belegter Freigabe oder aus Release ausgeschlossen |
| P0 sicherheitsrelevante Startwerte/öffentliche Redaktionsschreibwege | 4–8 PT, Teil der Appbudgets | Appauswahl | Keine Standardpasswörter, fehlende Secrets blockieren Produktion, gswb-Redaktion gesperrt, direkte Negativ-APItests |
| P1 Plattformrelease-/Manifest-/CI-Grundlage | 5–9 PT | Lizenzumfang und Vertrag | Digests/Locks/SBOM, getrennte Volumes, reproduzierbare Appbuilds und Kompatibilitätsmatrix |
| P1 Caddy/Keycloak/Relay/Secretstore + lokaler Pilot | 6–11 PT | Releasegrundlage | Zwei RPs, Appfreigaben serverseitig, eigene Claims/Rollen, Mail-Sink, getrennte Domains, kein externer Versand |
| P1 Schulwissen vollständig an Vertrag anpassen | 8,5–18 PT | Keycloak/Proxy/Testdaten | PKCE-/Mappingbestand nutzen, 60-s-Sperre, Logout, Resetmail, Besitz und Restore nachweisen |
| P2 Dashboard/BFF und begrenzter Deployment-Dienst | 10–18 PT | Manifest/IdP | Kacheln und Admin getrennt, kein Socket am Dashboard, allowlisted Aktionen, Domain-Rückfall/Audit |
| P2 Install-/Update-/Backup-/Monitoringautomatisierung | 8–15 PT | Images/Secrets/Vertrag | Wiederholbarer/unterbrechbarer Install, leere Restores, Alarm, kein blindes Überschreiben |
| P2 Zielserverbenchmark, Fehler-/Wiederherstellungstest | 4–8 PT | Pilot/Server/Datenprofil | Hauptfall 10 Personen; 20-min und 60-min-Lauf, Ressourcen/Rohdaten, RPO/RTO gemessen |
| P3 Appwellen aus folgender Tabelle | siehe Appbudgets | gemeinsamer Vertrag stabil | Pro App fachliche Rechte, Sonderzugänge, Mail und konsistenter Restore abgenommen |

Die Infrastrukturpakete ohne einzelne Apparbeit liegen grob bei 36–68 PT plus 3–7 PT Lizenzinventar. Ein kleiner technischer Pilot ohne fertiges Dashboard/Installer kann in etwa 10–20 PT zusätzlich zu gezielten Appanpassungen validiert werden; das ist ausdrücklich nicht die fertige 14-App-Plattform. Vollständige Einführung mit allen hier geforderten Betriebs-/Migrationsmerkmalen ist ein mehrmonatiges Vorhaben.

## Je Repository

Exakte sechs Teilkategorien, Dateien und Änderungsschritte stehen in [repository-matrix.csv](repository-matrix.csv) und [apps/](apps/). Summe der unabhängigen Appschätzungen ca. **187,5–382,5 PT**, inklusive Migration/Backup/SSO-Härtung aller Apps, ohne komplette Plattform. Das darf wegen überlappender Grundlagen nicht ungeprüft zum Liefertermin addiert werden. Für eure geringe Gleichzeitigkeit lässt sich Betriebsleistung sparen; die Zahl der unterschiedlichen Auth-/Datenmodelle bleibt gleich.

| Welle | App | Appaufwand PT | Zentrale konkrete Arbeit / Abnahme |
| --- | --- | ---: | --- |
| 1 | schulwissen | 8.5–18 | vorhandenes OIDC ergänzen, Freigabe/Revokation, Mapping, pg_dump+Medien |
| 2 | fahrradausbildung | 10–20.5 | native Mitarbeiter-OIDC, Schule/Posten/PWA erhalten, QR und Offline-Sync |
| 2 | schulhelfer | 14–27 | Admin-OIDC, Teilnehmerlinks/Schichtintegrität, Outbox und exklusiver Scheduler |
| 2 | losverkauf | 11–25 | gemeinsame Adminidentität auflösen, Elternzugang, Platzlimits und Outbox |
| 2 | schuleva | 12–24.5 | Admin-OIDC, TAN/Antwort-Atomarität und Ergebnisfreigaben |
| 3 | kompetenz-manager | 17–32 | User-/Klassenmapping, geschützte Uploads, LibreOffice und Versionsmigration |
| 3 | schulanmeldung | 15–30 | Mitarbeiter-OIDC/MFA, Elternportal/Termine, sensible Vorlagen und konsistentes Backup |
| 3 | schulkasse | 14–27.5 | Finanzrollen/MFA, Besitz, konkurrierende Buchungen, Salden-Restore |
| 3 | leseflux | 13–28.5 | OIDC Erwachsene/JWTwiderruf, QR/Code-Kinderzugang und UUID-Historie |
| 4 | grundschultafel | 17–34.5 | Bootstrap und Sessions korrigieren, JSON-Dateibestand/MobileUpload, externe Assets |
| 4 | abgen | 17–34.5 | OIDC und WSrevokation, PG18, Chromiumslots, Offline-/Share-/Printpfade |
| 4 | zackboing | 14–27.5 | native Node-Builds, Bootstrap/Sessions/WS-Hosts, flüchtige Spiele drainen |
| nach Schutzmaßnahme bedarfsabhängig | gswb | 8–17.5 | Redaktion schützen, Schreibprobenpflege, KI-/Medienentscheidung; kein Kontoimport |
| separat | SL-Journal | 17–35.5 | Einzelkontoziel entscheiden, SQLCipher/Keys/Mobil-API, Restore und native Tools |

Wellen 2/3 nach tatsächlichem Schulbedarf austauschen; es besteht keine technische Pflicht, alle Apps gleichzeitig auf SSO umzustellen. Zentralen Login erst freigeben, wenn die lokale Fachautorisierung derselben App abgenommen wurde.

## Gemeinsames Definition-of-Done

Je App: exakt festgehaltener Commit/digest, Linux-amd64-Build, alle erforderlichen Fach-/Negativtests, Kontrollmapping mit gleichem Besitz/FKs, unveränderte beabsichtigte Eltern-/Kinder-/Öffentlichkeitszugänge, konsistente Sicherung und Restore in leere Umgebung, Domainrollback, Secretrotation, echte Logout-/Sperrfristmessung und Ressourcenbudget mit Lasttest. Nicht benötigter Mailversand wird als nicht zutreffend dokumentiert. ARM64 eigene Freigabestufe. Keine Produktionsumstellung aus diesem Audit ableiten.
