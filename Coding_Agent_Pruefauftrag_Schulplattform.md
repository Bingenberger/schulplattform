# Prüfauftrag für einen Coding-Agenten: gemeinsame Schulplattform

Stand: 1. November 2026. Auftraggeber: Florian Emrich.

## 1. Auftrag und Arbeitsweise

Du bist als Softwarearchitekt, Full-Stack-Entwickler und Betriebsverantwortlicher mit einer technischen Machbarkeitsprüfung beauftragt. Untersuche die unten genannten 14 Repositories tatsächlich anhand ihres aktuellen Codes. Erarbeite eine belastbare Architektur, einen konkreten Integrations- und Migrationsplan und eine nachvollziehbare Serverdimensionierung für eine gemeinsam installierbare, selbst gehostete Schulplattform.

Das Ziel ist zunächst eine Prüfung mit reproduzierbaren Nachweisen, keine vollständige Neuentwicklung. Führe reversible lokale Analysen, Builds, Tests und isolierte Prototypen selbstständig aus. Ändere keine produktiven Systeme, DNS-Einträge oder echten Benutzerkonten und versende keine echten E-Mails. Nutze synthetische Testdaten. Veröffentlichung, produktive Migration und Deployment gehören nicht zu diesem Prüfauftrag. Erstelle keine bloßen Empfehlungen aus Repository-Namen oder README-Dateien.

Lies vorhandene AGENTS.md und projektspezifische Entwicklungsanweisungen. Verwende isolierte Checkouts oder Worktrees und erhalte bestehende Änderungen. Prüfe vorhandene GitHub-Zugänge; fordere keine Tokens im Chat an. Bei fehlendem Zugriff dokumentiere das betroffene Repository als blockiert, nenne die konkret fehlende Zugriffsmöglichkeit und arbeite an den übrigen Projekten weiter. Ein fehlender Zugriff ist kein Beleg dafür, dass eine Funktion fehlt.

Trenne in jedem Ergebnis:
- **Beobachtet:** durch Code, Konfiguration oder ausgeführten Test belegt.
- **Gemessen:** mit dokumentiertem Testaufbau und Rohdaten ermittelt.
- **Geschätzt:** nachvollziehbare Annahme, Bandbreite und Unsicherheit genannt.
- **Offen/blockiert:** mangels Zugang, Daten oder Testumgebung nicht geprüft.

## 2. Vollständiger Umfang

1. https://github.com/Bingenberger/schulwissen
2. https://github.com/Bingenberger/fahrradausbildung
3. https://github.com/Bingenberger/schulanmeldung — nach Angabe des Auftraggebers privat
4. https://github.com/Bingenberger/SL-Journal
5. https://github.com/Bingenberger/kompetenz-manager
6. https://github.com/Bingenberger/leseflux
7. https://github.com/Bingenberger/schuleva
8. https://github.com/Bingenberger/gswb
9. https://github.com/Bingenberger/grundschultafel
10. https://github.com/Bingenberger/schulkasse
11. https://github.com/Bingenberger/abgen
12. https://github.com/Bingenberger/losverkauf
13. https://github.com/Bingenberger/schulhelfer
14. https://github.com/Bingenberger/zackboing

Dokumentiere je Repository Prüfdatum, Branch, vollständige Commit-SHA und Zugriffsstatus. Belege zentrale Befunde mit commitgebundenen Dateilinks und Zeilennummern. Dokumentiere Lizenzen und die Zulässigkeit der vorgesehenen gemeinsamen Distribution, einschließlich relevanter Assets und Abhängigkeiten. Erfinde keine Lizenz, wenn keine vorhanden ist.

## 3. Zielbild und vorläufige Annahmen

Eine Linux-Installation soll alle ausgewählten Apps einschließlich gemeinsamer Infrastruktur starten können. Ein zentrales Dashboard stellt eine App-Übersicht und eine getrennte Administrationsansicht bereit. Dort werden Anwendungen aktiviert, Domains verwaltet, ein gemeinsamer SMTP-Versand eingerichtet sowie Benutzer und App-Zugangsrechte gepflegt. Ein zentraler Login ermöglicht SSO für geeignete geschützte Bereiche.

Vorläufiger Planungsfall: eine eigenständige Installation pro Schule; zunächst eine Grundschule mit ungefähr 25–40 erwachsenen Konten und 350–450 Kindern als Größenordnung. Das sind keine bestätigten aktuellen Nutzungszahlen und keine Aussage, dass jedes Kind ein Konto benötigt. Alle 14 Apps können installiert und gestartet sein, ohne dass alle gleichzeitig stark benutzt werden. Berücksichtige zusätzliche Eltern-, Veranstaltungs- und Gastzugriffe. Leite den tatsächlichen Nutzerkreis je App aus dem Code ab.

Stelle früh höchstens fünf entscheidungsrelevante Fragen, falls die Antworten nicht vorliegen: eine oder mehrere Schulen, erwartete gleichzeitige Nutzung, größte Daten-/Mediendatenbestände, vorhandener Zielserver und Verfügbarkeitsbedarf. Warte mit unabhängiger Prüfung nicht auf Antworten. Rechne alternativ klar benannte Szenarien. Mehrere isolierte Schulinstallationen und echte Mandantenfähigkeit innerhalb einer App sind unterschiedliche Anforderungen.

## 4. Bestandsaufnahme je App

Erstelle eine vollständige Matrix und einen kurzen Einzelbericht pro Anwendung mit folgenden Punkten:

### Technologie und Betrieb
- Tatsächliche Frameworks, Laufzeiten und Versionen; unterstützte Betriebssysteme und CPU-Architekturen; Lockfiles und reproduzierbare Installation.
- Frontend, Backend, statische Auslieferung, serverseitiges Rendering, API, WebSockets, Service Worker und Offline-Funktionalität.
- Produktionsstart, Build-Kommandos, Dockerfiles, Compose-Dateien, bestehende Installskripte, Reverse-Proxy-Annahmen, Ports und Healthchecks.
- Datenbanken mit Versionen und Erweiterungen; Cache, Queue, Worker, Cronjobs, Scheduler, Suchindex und weitere Dienste.
- Persistente Dateien, Uploads, lokale Browserdaten, Volumes, temporäre Dateien und Datenbankmigrationen.
- Externe Dienste, insbesondere gehostete Datenbanken, Authentifizierung, Objektspeicher, KI-/Sprachdienste, Zahlungsdienste und proprietäre APIs. Prüfe, ob tatsächlich vollständiges Self-Hosting möglich ist und welche Alternativen nötig wären.
- Aufwendige Verarbeitung: PDF-Export, Chromium/Playwright, Bildverarbeitung, OCR, Audio, lokale Modelle, große Importe, Berichte oder Echtzeitverbindungen. Vorhandensein nicht aus App-Namen ableiten.

### Anmeldung, Rollen und Daten
- Anmeldeverfahren, Session-/Tokenverwaltung, Passwort-Hashes, Registrierung, Einladungen, Zurücksetzen und bestehende OIDC/SAML-Unterstützung.
- Benutzer-ID und Beziehungen zu fachlichen Daten; Rollen, Klassen-, Gruppen-, Schul- und Objektberechtigungen; Serverdurchsetzung dieser Rechte.
- Öffentliche Seiten, Freigabelinks, Codes/PINs, Eltern-/Kinderzugänge, Geräte-/Kioskzugänge und API-Zugänge.
- Bestehende Mailbibliothek, Versandstellen, SMTP-Konfiguration und Absenderanforderungen.
- Konfiguration über Umgebungsvariablen, Dateien, Datenbank oder Oberfläche; beim Build fest eingebrannte URLs; Cookies, CORS, CSRF und absolute Links.
- Datenarten und vorhandene Export-, Lösch- und Sicherungsmöglichkeiten. Keine echten personenbezogenen Datensätze in Berichte kopieren.

### Befund und Aufwand

Bewerte getrennt: Containerbetrieb, Domainwechsel, zentraler Mailversand, SSO, Benutzermigration und Backup/Restore. Nutze die Kategorien „bereits vorhanden“, „kleine Anpassung“, „größerer Umbau“, „blockiert“ und begründe jede Kategorie. Nenne betroffene Dateien und konkrete Änderungsschritte. Gib Aufwand als Bandbreite von Arbeitstagen mit Annahmen, Abhängigkeiten und Vertrauensgrad an; keine unbegründeten Fixtermine.

## 5. Architekturentscheidung

Prüfe ein neues Plattform-Repository, das versionierte App-Images und Infrastruktur orchestriert, während die Apps eigenständig bleiben. Vergleiche dies kurz mit einem Monorepo; begründe die Empfehlung anhand der Befunde. Vermeide zwingende Änderungen an allen Apps bei jedem Plattformrelease.

Für einen einzelnen Server ist Docker Compose der Ausgangspunkt, nicht eine vorab beschlossene technische Pflicht. Bewerte Reverse Proxy (z. B. Caddy oder Traefik), Identity Provider (z. B. Keycloak oder authentik), Mail-Relay und ein schlankes Dashboard. Verwende aktuelle offizielle Dokumentation. Entscheide jeweils für eine Primärvariante und erkläre Betriebskosten und Integrationsaufwand; keine bloße Produktliste.

Entwirf ein App-Manifest mit mindestens: stabiler App-ID, Anzeigename, Image-Version/Digest, benötigten Diensten, internem Port, Healthcheck, Konfigurationsschema, persistenten Pfaden, Migrationskommando, Ressourcenbudget, öffentlichen Routen, Authentifizierungsmodus, OIDC-Client, SMTP-Bedarf und Backup-/Restore-Verfahren. Ein deaktiviertes Modul darf nicht versehentlich Daten verlieren; unterscheide „ausblenden“, „stoppen“ und „deinstallieren“.

Daten bleiben je App logisch getrennt. Gemeinsame Datenbankserver nur bei kompatibler Engine/Version, separaten Datenbanken und eingeschränkten Dienstkonten. Bestehendes SQLite nicht ohne Befund ersetzen; Dateisperren, Parallelität und konsistente Sicherung prüfen. Fachliche Tabellen nicht zu einer gemeinsamen Datenbank verschmelzen, nur um SSO zu erreichen.

Berücksichtige einen späteren eigenständigen Betrieb der Apps, soweit wirtschaftlich sinnvoll. Definiere einen stabilen Vertrag zwischen Plattform und Anwendung statt verstreuter Sonderfälle.

## 6. SSO und Berechtigungen

Plane echtes OpenID Connect pro Anwendung mit separatem Client. Wähle anhand der App-Architektur Authorization Code Flow mit PKCE und geeignete Sessionverwaltung; keine Client-Secrets in Browsercode. Prüfe Signatur, Issuer, Audience, Ablauf, State und Nonce mit etablierten Bibliotheken. Verwende exakt registrierte Redirect-URIs.

Verknüpfe lokale Konten über die Kombination aus Issuer und Subject. E-Mail-Adressen sind kein hinreichender dauerhafter Identitätsschlüssel. Entwirf für bestehende Konten ein kontrolliertes Zuordnungsverfahren einschließlich Duplikaten, geänderten Adressen, Konten ohne E-Mail und nicht migrierbaren Passwort-Hashes. Automatisches Zusammenführen allein aufgrund gleicher unbestätigter E-Mail-Adressen ist ausgeschlossen. Fachliche Eigentümer- und Klassenzuordnungen müssen erhalten bleiben.

Unterscheide Plattformadministrator, Appadministrator und fachliche Rolle. Der Zugang zu einer App verleiht keine pauschalen Rechte an deren Daten. Schütze Backend-Endpunkte; das Ausblenden einer Dashboard-Kachel genügt nicht.

Prüfe SSO über verschiedene Hauptdomains ohne gemeinsame Domain-Cookies. Definiere Einladungen, Deaktivierung, Berechtigungsänderungen, Sessionlaufzeiten, MFA für Administratoren und Notfallzugang. Zentraler Logout muss mit den tatsächlich unterstützten Verfahren jeder App getestet werden; lokale Sessions verschwinden nicht automatisch durch Logout beim Identity Provider. Definiere eine messbare Frist, innerhalb der gesperrte Konten den Zugriff verlieren.

Eine vorgeschaltete Proxy-Anmeldung ist nur dort ausreichend, wo keine eigene Benutzeridentität in der App gebraucht wird. Stelle dies nicht als fertige Integration lokaler Benutzerkonten dar. Vertrauenswürdige Header nur verwenden, wenn direkte Backend-Zugriffe ausgeschlossen und eingehende gleichnamige Header entfernt werden.

Öffentliche Formulare, Elternlinks, Kinder-Codes, Kioskbetrieb und Offline-Funktionen müssen gezielt erhalten oder mit begründetem Migrationsweg angepasst werden. SSO nicht ungeprüft vor sämtliche Routen setzen. Dokumentiere auch das Verhalten bei Ausfall des Identity Providers und bei weiterlaufenden lokalen Sessions.

## 7. Dashboard, Domains und SMTP

Definiere Benutzeroberfläche und Backend-Verantwortlichkeiten für:
- App-Kacheln entsprechend den tatsächlichen Zugangsrechten.
- Aktivierung, Domain, installierte Version, Zustand, Update- und Sicherungsstatus.
- Benutzer, Einladungen, Gruppen und App-Freigaben; vermeide widersprüchliche doppelte Benutzerverzeichnisse.
- SMTP-Host, Port, TLS, Zugangsdaten, Standardabsender, erlaubte Absender und Testversand.
- Betriebsprotokoll administrativer Änderungen, ohne Passwörter oder Tokens zu protokollieren.

Ein Domainwechsel muss Proxy, Zertifikat, App-Basis-URL, Auth-Redirects, Mail-Links und ggf. CORS/CSRF gleichzeitig berücksichtigen. Führe Validierung, Vorschau, Anwendung, Funktionsprüfung und Rückfall auf die alte Konfiguration als Ablauf auf. DNS wird ohne gesonderte Providerintegration nicht automatisch geändert. Behalte bei fehlerhaften Änderungen einen administrativen Zugangsweg.

SMTP: Prüfe internes Relay als bevorzugte Lösung, mit externen Zugangsdaten nur dort. Kein öffentliches offenes Relay; je App eingeschränkte Authentifizierung oder gleichwertige Isolation, zulässige Absender, Queue, Wiederholungen, Rate Limits und Diagnose. Beachte, dass auch der Identity Provider Mail versenden muss. Prüfe SPF/DKIM/DMARC und Absenderbedingungen als Einrichtungsanforderung, ohne pauschal die Zustellung zu garantieren. In Tests ausschließlich Mail-Sink verwenden.

Das Dashboard erhält keinen unbeschränkten Docker-Socket und keine frei formulierbaren Root-Shell-Kommandos. Entwirf einen eng begrenzten, authentifizierten Deployment-Dienst oder vergleichbaren Mechanismus mit festen erlaubten Aktionen, validierten Parametern und Audit-Protokoll. Erkläre verbleibende Privilegien und Angriffsflächen. Secrets gehören nicht ins Git, ins Frontend oder in Logs; behandle Schutz, Rotation und Sicherung der Schlüssel explizit.

## 8. Installation, Updates und Wiederherstellung

Lege nach Kompatibilitätsprüfung eine konkrete unterstützte Linux-LTS-Version und zunächst eine CPU-Architektur fest. Prüfe zusätzlich ARM64-Kompatibilität, behaupte sie aber erst nach erfolgreichen Builds für native Abhängigkeiten.

Spezifiziere ein idempotentes Installationsskript mit Vorprüfung für Rechte, RAM, Speicher, Ports, DNS, ausgehende Verbindungen und bestehende Dienste. Keine existierende Firewall, SSH-Konfiguration, Docker-Installation oder Datenbestände blind überschreiben. Erste Einrichtung mit einmaligem Bootstrap-Verfahren und ohne Standardpasswort. Wiederholung und Unterbrechung dürfen keine Datenverluste verursachen.

Verwende reproduzierbare, versionierte Images; keine unkontrollierten latest-Updates. Plane Release-Kompatibilitätsmatrix, Upgrade-Reihenfolge, Wartungsfenster, Sicherung vor Migration und Healthchecks danach. Unterscheide Containerrollback von Datenbankrollback. Für irreversible Migrationen Wiederherstellung und möglichen Verlust zwischenzeitlicher Änderungen ausdrücklich beschreiben.

Sicherungen umfassen Datenbanken, Uploads, Identity Provider, Plattformkonfiguration und notwendige Schlüssel. Nutze konsistente DB-Verfahren; nicht einfach laufende Datenbankdateien kopieren. Speichere verschlüsselte Backups außerhalb des Servers. Als Diskussionsbasis: RPO 24 Stunden und RTO 4 Stunden; bei Transaktionen/Veranstaltungen kürzeres RPO gesondert prüfen. Dokumentiere Aufbewahrung, Rotation, Alarmierung und einen durchgeführten Restore auf leerer Testumgebung. Ein Snapshot auf demselben Server ist kein vollständiges Backupkonzept.

## 9. Serverleistung: Messung statt pauschaler Schätzung

Leite die Dimensionierung aus der tatsächlich ermittelten Architektur ab. Vierzehn statische Frontends haben einen völlig anderen Bedarf als vierzehn ständig laufende Backends mit Workern, Datenbanken und Browserprozessen. Zähle gemeinsam genutzte Dienste nur einmal. Trenne Betriebsbedarf, Build-/Updatebedarf und Backup-/Restore-Spitzen.

### Messaufbau

Dokumentiere CPU-Modell, vCPU-Zahl, dedizierte/geteilte Kerne, RAM, Swap, Speichermedium, I/O, Betriebssystem, Containerlimits, App-Versionen und Datenvolumen. Nutze Produktionsbuilds und realistische synthetische Daten, nicht Entwicklungsserver. Lastgenerator möglichst auf separatem Rechner. Laufzeitmessungen auf einem fremd ausgelasteten Agentenhost sind nur eingeschränkt aussagekräftig.

Erfasse je Dienst und insgesamt: Leerlauf- und Spitzen-RAM, CPU, OOM/Neustarts, I/O-Wartezeit, Disk-Latenz, Datenbankverbindungen, Queue-Länge, Netzverkehr, HTTP-Fehlerrate sowie p50/p95/p99 relevanter Antwortzeiten. Dokumentiere Cachezustand, Aufwärmphase und Container-Memory-Metrik; Cache und RSS nicht unbesehen addieren. Miss auch SSO-Loginspitzen und Tokens erneuernde Sessions.

### Lastszenarien

Teste, soweit Funktionen vorhanden, mindestens folgende Hypothesen und passe sie nach der Bestandsaufnahme begründet an:

| Szenario | Gleichzeitig aktive Nutzung | Zweck |
| --- | --- | --- |
| Leerlauf | alle 14 Apps gestartet, keine Nutzlast | feste Grundlast |
| Kollegium | 30 aktive erwachsene Nutzer | normaler Schulbetrieb |
| Unterricht | 30 Erwachsene plus 90 Kinder auf geeigneten Apps | mehrere Lerngruppen parallel |
| Spitzenlast | 250 aktive Nutzer über einen begründeten App-Mix | Eltern-/Veranstaltungsspitze |
| Hintergrundarbeit | Normalbetrieb plus Export, Import, Mailqueue und Backup | Konkurrenz um CPU, RAM und I/O |

Die Nutzerzahlen sind Testhypothesen, keine zugesicherten Kapazitäten. Definiere Nutzeraktionen, Denkzeiten, Routenanteile, Payloadgrößen und daraus resultierende Requests/s. Ein virtueller Nutzer ist keine feste Anzahl von Requests/s. Simuliere nicht einfach je App die volle Gesamtnutzerzahl. Falls eine App Transaktionen hat, teste konkurrierende Schreibvorgänge und Datenintegrität; falls sie Echtzeitverbindungen hat, teste Verbindungsanzahl und Broadcast-Last. Ressourcenintensive Jobs begrenzen und Warteschlangenverhalten prüfen.

Vorgeschlagener Ablauf: 5 Minuten Aufwärmen, 20 Minuten konstante Last, 5 Minuten kurze Spitze, mindestens 60 Minuten Dauertest für Speicherwachstum im aussichtsreichsten Setup. Dauer und Last an sichere Testressourcen anpassen; Einschränkungen offenlegen. Vorgeschlagene, zu bestätigende Ziele: p95 unter 1 Sekunde für gewöhnliche serverseitige CRUD-Anfragen, technische Fehlerrate unter 1 %, keine OOM-Abbrüche und kein stetig wachsender Rückstau. PDFs, Medien und andere lange Jobs separat mit passenden Zielen bewerten; fachlich erwartete Fehler nicht als technische Fehler zählen. Keine Lasttests gegen Produktivdomains ohne gesonderten Auftrag.

### Kapazitätsrechnung

Erstelle eine Tabelle je Komponente: Instanzen, Idle-RAM, Last-RAM, CPU bei definiertem Szenario, persistenter Speicher, Wachstum, Messstatus und Quelle. Begründe anschließend:

- RAM: realistische gemeinsame Last plus Betriebssystem und 25–35 % Reserve; Swap ist kein Ersatz für ausreichend RAM. Containerlimits gegen Worst-Case prüfen.
- CPU: beobachtete Last und Reaktionszeiten; CPU-Anteile/Quota und mögliche überbuchte vCPUs berücksichtigen. Ziel im Normalbetrieb: ausreichend Reserve für Lastspitzen, nicht dauerhaft nahe Vollauslastung.
- Speicher: Betriebssystem + aktuelle und vorherige Images + Datenbanken + Uploads + begrenzte Logs + temporäre Exporte + lokale Backup-Stagingfläche + Wachstumsreserve. Externe Backupkapazität separat ausweisen.
- Netzwerk: statische Assets, Medien und Exporte anhand Payload × Zugriffszahl berechnen; nötigen Uplink und erwartetes Monatsvolumen nennen. Externe API-Nutzung und Kosten getrennt vom Serverbedarf betrachten.
- GPU: nur bei nachgewiesenem lokalem Modell-/GPU-Workload erforderlich; externe KI-API oder Browsergrafik begründen keine Server-GPU.

Wenn keine repräsentative Ausführung möglich ist, liefere ausdrücklich eine Schätzung mit offenen Punkten und ein ausführbares Benchmarkpaket. Nenne keine erfundenen Messwerte und keine belastbare Maximalkapazität aus bloßer Codelektüre.

## 10. Vorläufige Größen zur Überprüfung

Diese Werte stammen aus einer Planung vor Codeeinsicht. Sie sind weder Mindestanforderungen der Apps noch Benchmark-Ergebnisse. Verifiziere oder korrigiere sie ausdrücklich:

| Profil | CPU | RAM | lokale SSD/NVMe | Einordnung |
| --- | --- | --- | --- | --- |
| technische Erprobung | 4 vCPU | 8 GB | 100–160 GB | eventuell ausreichend für geringe Last; kein garantierter Betrieb aller Apps |
| Startplanung für eine Schule | 8 vCPU | 16 GB | 200–300 GB | Prüfgröße bei überwiegend leichten Web-Apps und externen Builds |
| größere Reserve | 8–12 vCPU | 32 GB | 300–500 GB | Prüfgröße für mehrere Backends, Worker, parallele Exporte oder stärkere Spitzen |

Auch das größte Profil ist ohne Prüfung keine Zusicherung. Lokale Medienbestände und Modelle können die Werte stark verändern. Gib eine Mindestkonfiguration nur an, wenn ein konkretes Lastszenario damit nachgewiesen wurde. Empfiehl getrennt einen wirtschaftlichen Einstieg und eine Ausbaugrenze. Benenne messbare Upgrade-Auslöser, z. B. wiederholt verletztes p95-Ziel, hohe Speicherauslastung, I/O-Engpass oder anhaltender Queue-Rückstau.

Prüfe VPS gegenüber dedizierten vCPUs. Ein einzelner leistungsfähiger Server ist weiterhin ein Ausfallpunkt; mehr RAM ersetzt keine Hochverfügbarkeit. Für mehrere Schulen Kapazität und Isolation neu bewerten, nicht schlicht Kontenzahlen linear hochrechnen. Keine Anbieterpreise ohne aktuelle Recherche nennen.

## 11. Isolierter Integrationsnachweis

Wähle nach der Bestandsaufnahme eine möglichst repräsentative, gut prüfbare Pilot-App. Begründe die Wahl. Erstelle bei ausreichender Umgebung einen lokalen, nicht produktiven Prototyp mit Reverse Proxy, Identity Provider, Pilot-App und Mail-Sink. Ziehe für den Nachweis von appübergreifendem SSO eine zweite reale App oder einen klar als solchen bezeichneten Testclient hinzu. Eine einzige App beweist noch kein appübergreifendes SSO.

Prüfe und protokolliere:
1. Anmelden in App A, anschließend Zugriff auf App B ohne erneute Passworteingabe.
2. Benutzer ohne Appfreigabe wird auch bei direktem API-Aufruf abgewiesen.
3. Öffentliche Routen bleiben entsprechend der Anforderung erreichbar.
4. Bestehendes Testkonto wird korrekt zugeordnet, einschließlich Datenbesitz und Rollen.
5. Logout, Sperrung und abgelaufene Tokens verhalten sich wie spezifiziert.
6. Domain-/Basis-URL-Änderung einschließlich Callback und Rückfall funktioniert.
7. E-Mail landet über den vorgesehenen Weg ausschließlich im Testpostfach.
8. Neustart erhält persistente Daten, erneute Einrichtung überschreibt sie nicht.
9. Backup lässt sich in einer sauberen Umgebung wiederherstellen.

Falls einzelne Punkte nicht ausgeführt werden können: genau benennen, warum, und reproduzierbare nächste Schritte liefern. Prototypen nicht als fertige Plattform bezeichnen.

## 12. Verbindliche Ergebnisse

Lege die Ergebnisse gesammelt im Arbeitsrepository unter docs/platform-audit/ ab. Berichte auf Deutsch, Kommandos und Code nach üblicher Konvention. Liefere mindestens:

- **README.md:** verständliche Entscheidungsvorlage, Machbarkeit, größte Hindernisse, Empfehlung und unmittelbar nächster Schritt.
- **repository-matrix.csv:** alle 14 Repositories mit Commit, Stack, Diensten, Auth, Mail, Persistenz, Integrationsgrad, Blockern und Aufwand.
- **apps/<app-id>.md:** Einzelbefunde mit Dateibelegen und konkreter Änderungsliste.
- **architecture.md:** Zielarchitektur, Datenflüsse, Vertrauensgrenzen und begründete Komponentenentscheidungen.
- **integration-contract.md:** App-Manifest, Konfiguration, Auth-, SMTP-, Healthcheck- und Backup-Vertrag mit einem Beispiel.
- **identity-migration.md:** Rollenmodell und Migration bestehender Konten/Daten einschließlich Sonderfällen.
- **server-sizing.md:** Szenarien, Annahmen, Messwerte, Komponentenbudgets, empfohlene Serverprofile, Unsicherheiten und Skalierungsgrenzen.
- **operations.md:** Installation, Domains, Secrets, Updates, Überwachung, Sicherung und Wiederherstellung.
- **implementation-roadmap.md:** priorisierte Arbeitspakete je Repository und für die Plattform, Abhängigkeiten, Aufwandsspannen und Abnahmekriterien.
- **open-questions.md:** ausschließlich verbleibende Entscheidungen und Blocker, mit Wirkung auf Architektur oder Aufwand.
- **benchmarks/**: ausführbare Lasttests, synthetische Datengeneratoren, Anleitung und bereinigte Rohdaten, soweit tatsächlich erstellt/ausgeführt.
- **prototype/** oder ein nachvollziehbarer Branch: isolierter Integrationsnachweis, sofern möglich; Änderungen klar von Audit-Ergebnissen trennen.

Prüfe abschließend die Vollständigkeit gegen alle 14 Repositories. Nenne ausgeführte und nicht ausgeführte Tests. Schließe mit einer klaren Empfehlung: praktikable Architektur, geeignete Pilot-App, Reihenfolge der Integration, belastbare bzw. vorläufige Servergröße und die nächsten drei Umsetzungsschritte. Führe keine Produktivumstellung im Rahmen dieses Prüfauftrags aus.

## 13. Quellen für den Einstieg

Diese Quellen beschreiben einzelne Komponenten, nicht den Leistungsbedarf dieser 14 Apps. Prüfe beim Audit die dann gültigen Versionen und Anforderungen.

- Docker Compose im Produktivbetrieb: https://docs.docker.com/compose/how-tos/production/
- Docker Engine auf Linux: https://docs.docker.com/engine/install/
- Keycloak, Anwendungsintegration: https://www.keycloak.org/securing-apps/overview
- Keycloak, CPU- und Speicherdimensionierung: https://www.keycloak.org/high-availability/single-cluster/concepts-memory-and-cpu-sizing
- authentik, Compose-Installation: https://docs.goauthentik.io/install-config/install/docker-compose/
- Caddy, automatisches HTTPS: https://caddyserver.com/docs/automatic-https

Keycloaks Zahlen stammen aus einem beschriebenen Referenzaufbau; sie dürfen nicht ungeprüft als Mindestbedarf einer kleinen Schulinstallation übernommen werden. Ebenso sind Mindestwerte eines Identity Providers keine Dimensionierung der gesamten Plattform.
