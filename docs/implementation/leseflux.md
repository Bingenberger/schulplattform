# Leseflux: achte App im lokalen Pilot

Leseflux bleibt ein eigenständiges Repository. Das Änderungspaket ist unter
[patches/index.json](../../patches/index.json) mit Basis- und Ergebniscommit
nachvollziehbar. Der lokale amd64-Container kombiniert Fastify-API und gebaute
React-/Vite-Oberfläche; PostgreSQL ist separat und veröffentlicht keinen Port.
Die bisherigen npm-Workspaces und App-Dockerfile-Pfade bleiben nutzbar.
Node 22.23.4, Prisma 5.22.0, Fastify 5.8.5; die genaue Image-ID und Größe stehen
im [Imagebeleg](evidence/leseflux-image.json). Das Image enthält derzeit auch
Build-/Prisma-Abhängigkeiten und ist rund 480 MB groß.

## Betriebsvertrag

Die App läuft als UID 10001 mit schreibgeschütztem Rootdateisystem, begrenztem
tmpfs, Ressourcenlimits und ohne zusätzliche Capabilities. Die Approlle darf
weder Superuser sein noch Datenbanken oder Rollen anlegen. Neue DB-/JWT-Werte
werden pro Installation erzeugt und nur als einzelne Credentialdateien projiziert.
Bestehende DATABASE_URL/JWT_SECRET-Namen bleiben erhalten; _FILE-Alternativen
sind gegenseitig exklusiv. Ein geschütztes Elternverzeichnis ist zwingend.

Migrationen laufen ausschließlich über node scripts/platform-migrate.cjs,
Inhalte separat über node scripts/content.cjs. Der Inhaltsjob legt keine
Benutzer an und bewahrt bearbeitete Vorlagen. Der erste persönliche Admin wird
über node scripts/setup-admin.cjs am lokalen interaktiven Terminal angelegt.
Passwort zweimal verdeckt, kein Standardkonto, kein HTTP-Bootstrap. Weitere
Ausführungen erhalten vorhandene Konten. Der Secretgenerator und dieser echte
Terminalpfad sind [separat geprüft](evidence/leseflux-setup.json).

Liveness bleibt bei DB-Ausfall verfügbar. Readiness kontrolliert die komplette
Prisma-Migrationshistorie einschließlich SQL-Prüfsummen; Drift oder unvollständige
Migration sperrt Geschäfts-Endpunkte. Start/Stop führt keine Migration oder
Inhaltsanlage erneut aus.

## Lokale Zugänge

Persönliche Lehrkraft-Anmeldung und Kinderzugänge per QR/Kurzcode bleiben
erhalten. Anton-Inhalte werden ausschließlich lokal als undurchsichtiger
Zugang behandelt. Es gibt keine Verbindung zu Anton-Servern. Druckkarten
enthalten den Kurzcode und bleiben deshalb unabhängig von einer Domain.

JWTs liegen nur im HttpOnly-/SameSite-Strict-Cookie, im TLS-Pilot zusätzlich
Secure. Antwort und LocalStorage enthalten keinen JWT. Die Webmigration entfernt
den alten persistierten Token. PostgreSQL hält gehashte zufällige Sitzungskennungen
mit Credential-Fingerabdruck: acht Stunden für Lehrkräfte, 24 für Kinder, maximal
20 gleichzeitig. Logout, Passwort-/QR-/Codewechsel und Kontolöschung widerrufen
Zugänge serverseitig. Ein DB-Ausfall wird als Dienstfehler behandelt.

Alle schreibenden API-Aufrufe benötigen X-Leseflux-Request: 1 und, wenn vorhanden,
eine exakt passende Origin. Das Frontend setzt den Header. Der Proxy entfernt
eingehende Identitätsheader; nur seine konkrete IP wird vertraut. Klassen- und
Schülerzugriffe bleiben an die zuständige Lehrkraft gebunden. Auch Kinderanlage
und Import prüfen die Zielklasse. Einwilligungszeitpunkte sind Pflicht und werden
mit der Anlage transaktional protokolliert.

Neue QR-Werte werden nur gehasht gespeichert und einmalig zurückgegeben.
Historische qrTokenRaw- und Auditwerte werden bei der Migration bewusst erhalten;
bestehende Karten werden nicht still rotiert. Klassen-, Detail- und Vorlagen-API
blenden historische Rohwerte sowie Passwort-/QR-Hashes aus. Vor realer
Bestandsübernahme sind Schutz und Bereinigung historischer Werte gesondert zu
prüfen. Der bisherige Rohwert-Backfill ist deaktiviert.

## Ausgeführte Prüfungen

- [26 vorhandene Fachtests](evidence/leseflux-functional.log) für Fading, LIX,
  Adaptivität und Cloze im gepinnten Container ohne Netzwerk; TypeScript und
  Webbuild im [Buildlog](evidence/leseflux-build-runtime.log).
- [Reale parallele Sitzungstests](evidence/leseflux-session-contract.log):
  24 Anmeldungen ergeben 20 Slots, ausschließlich Hashkennungen, Ablauf,
  Rückgewinnung, Widerruf und Ablehnung einer fehlenden Kennung.
- [Standalone-HTTP-Abnahme](evidence/leseflux-standalone.json): explizite Migration,
  kein Defaultkonto, CSRF/Origin, Lehrkraft-/Klassengrenzen auch bei Kinderanlage,
  QR-Rotation, Passwortreset, Logout, Kontolöschung mit Trainingshistorie,
  Neustarterhalt, vollständige Leseübung mit Quiz und Fortschritt,
  historische Karten, private Pfade, Bodylimit, DB-Ausfall und Migrationsdrift.
- [Chromium auf Tabletansicht](evidence/leseflux-browser.json):
  Lehrkraft- und Kinder-Code-Anmeldung, Legacy-LocalStorage-Bereinigung,
  HttpOnly-Cookie und keine beobachteten Drittanfragen.
- [PostgreSQL-Restore](evidence/leseflux-restore.json) in einen neuen Cluster mit
  eigenem Volume: Fachzeilen identisch, Fortschritt und IDs erhalten, Lehrkraft
  und beide Kinderzugänge gültig, Fremdschlüssel und Rollenrechte geprüft,
  nichtleeres Ziel abgewiesen. Kein Seed oder Migrationsjob beim Restore.
- [Achterpilot](evidence/leseflux-platform.json): lokale verifizierte CA,
  Domainwechsel und erzwungener Rückfall, Secure-Cookies und vorhandene Karten,
  zwei No-op-Läufe mit unveränderten Containern/Schlüsseln/Checkpoints sowie
  Stop-Wartungsantwort und Start ohne Migration/Inhaltsjob.
- [Dashboard](evidence/dashboard-container.json): authentifizierte tatsächliche
  Start-/Stop-Steuerung über den Unix-Dienst; kein Docker-Socket im Dashboard.

## Grenzen und nächste Schritte

Die Abnahme verwendet nur synthetische Konten, lokale Domains und Entwicklungsimages.
Keine Kamerascans, dekodierten Druckkarten oder vollständige visuelle
Unterrichtsabnahme. Google-Font-Abfragen wurden entfernt; Systemschriften dienen
als Fallback. Optionale fehlende OpenDyslexic-Dateien werden nicht nachgeladen.
Die Rechte vorhandener Grundschrift-/Unterrichtsdateien sind weiterhin zu klären.

Sicherung erfordert gestoppte Schreiber, PostgreSQL-Custom-Dump und separat
geschützte Credentials. Keine Laufzeit-Uploads; statische Assets liegen im Image.
Offsite/Verschlüsselung, reale Altbestandsübernahme, zentrale Sperrung, öffentliche
DNS-/ACME-Abnahme, Ubuntu-Zielinstallation und Kapazitätsmessung bleiben offen.
Einige große Fach-Exporte sind noch nicht paginiert oder als eigener Exportjob
begrenzt. Das Bodylimit ist kein vollständiger Lastschutz.

Nach dem Build mit scripts/build_leseflux.py ist ein neuer Pilotzustandsordner mit
--apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung,leseflux
zu verwenden. Bestehende Auswahlen werden nicht erweitert oder umgeschrieben.
Die geprüfte finale Umgebung ist .work/pilot-v18; Dienste werden danach gestoppt,
Volumes und Schlüssel bleiben erhalten.

Bei der Terminalprüfung wurden ein offener ReadStream-Handle und ein Rennen
zwischen Prompt und deaktiviertem Echo korrigiert. Der finale Test führt den
unveränderten Image-Einstieg zweimal über ein echtes PTY aus und prüft, dass
das Passwort nicht in der Ausgabe erscheint. Auch restriktive umask 077 ist
für Credential-Projektionen mit einem Regressionstest abgedeckt. Masterdateien
bleiben 0600, Projektionen 0444 innerhalb privater 0700-Verzeichnisse.

Plattform-Quellpaket: c61256d; [Commit-Rohbeleg](evidence/leseflux-work-package-commit.log).
