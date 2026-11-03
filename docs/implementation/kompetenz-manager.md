# Kompetenz-Manager: neunte App im lokalen Pilot

Das eigenständige Repository erhält einen amd64-Standalone-Stack mit zwei
Gunicorn-Webworkern und einem separaten Benachrichtigungsworker. Standardmäßig
bleibt SQLite erhalten. Python 3.12.12, Flask 3.1.3, SQLAlchemy 2.1.6 und
LibreOffice 7.4.7.2 sind im [Imagebeleg](evidence/kompetenz-manager-image.json)
beobachtet; das lokale Entwicklungsimage umfasst rund 645 MB.
Keine Registry-Veröffentlichung, ARM64- oder Produktionsfreigabe.

## Implementiert und beobachtet

- Bestehende Env-Namen bleiben erhalten, insbesondere SECRET_KEY, DATABASE_URL,
  APP_BASE_URL und MAIL_*. Der Plattformadapter fixiert die eigene SQLite-URL
  für Webapp und Worker ausdrücklich; eine fremde native DATABASE_URL aus
  der Hostumgebung wird nicht übernommen. Secretdateien sind alternativ möglich. Private
  Projektionen liegen unter 0700-Elternverzeichnissen. Kein Secretwert im
  Container-Env, Git, HTML oder Betriebsprotokoll.
- UID 10001 besitzt instance und das Vorlagenvolume. Rootdateisystem
  schreibgeschützt, begrenzte tmpfs-/CPU-/RAM-/PID-Ressourcen. Geschützte Uploads
  und Schullogo bleiben im privaten Instanzvolume. Das Image enthält keine
  schuleigenen ODT-Vorlagen; diese werden ausdrücklich bereitgestellt.
- Revision 0001 ist ein expliziter exklusiver Job. Tabellen-/Spalteninventar
  und Release-Prüfsumme gehören zur Readiness. Ein Intent-Journal ermöglicht
  Fortsetzung nach einem echten Prozessabbruch während der Tabellenerzeugung.
  Normale Starts verändern kein Schema und legen keine Konten an.
- Vollständiges Schema des auditierten Ausgangsstands wird ohne Umschreiben
  von IDs, Klassen, Rollen oder Zuordnungen übernommen. Unbekannte ältere
  Schemata werden vor Änderungen abgewiesen. Historische Backfills laufen
  nicht automatisch. Keine echte Altinstallation wurde übernommen.
- Persönlicher Erstadmin ausschließlich am lokalen Terminal, Passwort zweimal
  verdeckt. Wiederholung bei bestehenden Nutzern und kopflose Ausführung
  verweigert. /setup und alte Reparatur-Passwortausgabe sind geschlossen.
- Lokale Flask-Anmeldung bleibt bestehen. Zufällige serverseitig gehashte
  Sitzungskennungen mit acht Stunden Laufzeit ermöglichen Widerruf bei Logout,
  Passwort-/Rollenwechsel und Löschung. Neustarts erhalten gültige Sitzungen;
  alte Cookies benötigen erneute Anmeldung. Der Credential-Fingerabdruck wird
  nach Passwortprüfung unter DB-Schreib-/Zeilenlock erneut verglichen, damit
  ein paralleler Passwortwechsel keine neue Sitzung mit alten Daten zulässt.
  Keine zentrale Sperrung.
- Vorhandene Rollen und Klassenzuordnungen bleiben maßgeblich. Beobachtungen
  sind entsprechend dem ursprünglichen Fachmodell intern schulweit sichtbar;
  Diagnostik und weitere klassengebundene Bereiche behalten ihre feineren
  Regeln. Verwaltung lehnt unberechtigte Lehrkräfte per bisheriger Umleitung
  ab, Diagnostikzugriffe auf fremde Klassen mit 403. Keine pauschale neue
  Klassengrenze über fachlich bewusst gemeinsame Daten.
- CSRF bleibt bestehen; vorhandene Origin muss zusätzlich APP_BASE_URL
  entsprechen. Nur die explizite Caddy-IP wird als Proxy vertraut.
  Eingehende Identitäts-/Weiterleitungsheader werden am Proxy entfernt.
- Ein Dateilock begrenzt LibreOffice über beide Worker und lokale Jobs.
  Sammel-PDF-Anfragen halten den Slot über die gesamte Anfrage. Belegt: 429,
  während Liveness über den zweiten Worker erreichbar bleibt.
  Konvertierungen maximal 20 Sekunden, Prozessgruppenabbruch, 16-MiB-ODT-
  und 64-MiB-Einzelausgabelimit; pdfunite ebenfalls zeitbegrenzt.
- Vorhandene dauerhafte Notification-/mailed_at-Logik bleibt erhalten.
  Separater exklusiver Worker statt Zeitgebern in jedem Webprozess.
  SMTP-Ausfälle lassen Zustellungen offen. Anonymisierte Fehlermeldung auf
  Fehlerstufe, ohne Exception-Stacktrace oder Benutzerkennung.
  Workerfehler erscheinen als degraded; Stop hält zuerst den Hintergrundschreiber,
  dann die Webapp an. Das Dashboard erhält keinen Docker-Socket.

## Ausgeführt

| Prüfung | Ergebnis / Beleg |
| --- | --- |
| Hash-Lock und amd64-Build | [Runtime](evidence/kompetenz-manager-build-runtime.log), [Tests](evidence/kompetenz-manager-build-tests.log) |
| Vorhandene Fachsuite plus fünf neue Laufzeitverträge | 566 bestanden, offline im gepinnten Container; [Rohlog](evidence/kompetenz-functional.log) |
| Echter Exit 17 während Schemaerzeugung, Wiederaufnahme, Bestands-IDs und unbekanntes Schema | Teil der fünf Laufzeitverträge; keine stillen Backfills |
| Plattform-Suite einschließlich Hintergrundschreiber/Status und umask | 96 bestanden; [Rohlog](evidence/python-tests.log) |
| Standalone, echte Terminaleinrichtung, Rollen/CSRF, kopierte Cookies, Passwortwiderruf, zwei Worker, PDF-Slot und SMTP-Ausfall | [Abnahme](evidence/kompetenz-standalone.json) |
| Frische SQLite-/Datei-/Vorlagenvolumes, keine Migration oder Seeds beim Restore | identische Fachzeilen, Rollen/IDs/Zuordnungen, private Dateien/Logo, synthetische Vorlagendatei, FK-/Integritäts- und HTTP/PDF-Prüfung; [Ergebnis](evidence/kompetenz-restore.json) |
| Chromium auf Tabletansicht | persönlicher Login, Kontoseite/Schülerakte, Verwaltungsablehnung, Logout und keine beobachteten Drittanfragen; [Ergebnis](evidence/kompetenz-browser.json) |
| Neunerpilot mit lokaler CA | Domainwechsel samt Mail-Link im Sink, erzwungener Rückfall, No-op und Web-/Worker-Lebenszyklus; [Ergebnis](evidence/kompetenz-platform.json) |
| Dashboard mit TOTP und authentifiziertem Unix-Dienst | tatsächlicher App-/Worker-Start und Stop; [Ergebnis](evidence/dashboard-container.json) |
| Fremde native DATABASE_URL bei Compose-Auflösung | beide Dienste bleiben auf der eigenen SQLite-DB; [Ergebnis](evidence/kompetenz-native-env-isolation.json) |
| Exportiertes Änderungspaket vom geprüften Basiscommit angewendet | identischer Dateibaum, sauberer Checkout; [Ergebnis](evidence/kompetenz-manager-patch-replay.json) |

Der vollständige Lauf enthält drei Warnungen zum Regexliteral eines
Testprogramms. Das Literal wurde anschließend korrigiert; die fünf
Laufzeitverträge und beide Codehygieneprüfungen bestehen danach erneut ohne
Warnungen ([7 Prüfungen](evidence/kompetenz-contracts.log)). Das Laufzeitimage
blieb dabei unverändert.

Die Wiederherstellung verwendet die generischen SQLite-Backup- und
Dateisnapshot-Bausteine. Beide Schreiber werden vor DB-/Dateisicherung gestoppt.
Keine laufende SQLite-Dateikopie. Alle Dateien gehören nach Restore UID 10001
und werden privat/nicht ausführbar wiederhergestellt. Nichtleere Ziele werden
abgewiesen. Schlüssel werden separat unverändert bereitgestellt.

## Grenzen

Keine Messung von Serverleerlauf, Last, Dauerlauf oder RPO/RTO.
566 Tests ersetzen keine vollständige visuelle/Tablet-/Importabnahme.
PostgreSQL-Codepfad bleibt vorhanden, wurde hier jedoch nicht mit echten
Containern abgenommen; geprüft ist SQLite. Ubuntu-Neuinstallation, öffentliche
DNS-/Besitz-/ACME-Prüfung, Offsite/Verschlüsselung, SBOM und signiertes Release
bleiben offen. Debian-Paketquellen sind noch kein eingefrorener Distributionssnapshot.

Mailversand ist mindestens einmal: ein Absturz zwischen SMTP-Annahme und
mailed_at-Commit kann Duplikate erzeugen. Native Cronjobs dürfen nicht parallel
zum Containerworker laufen; vor manuellen Versandjobs Worker anhalten.
Die Versandmengen sind begrenzt, große Rückstaus können mehrere Zyklen/Tage
benötigen. Alarmierung, vollständige Queueoberfläche und Zustell-SLA fehlen. Readiness
prüft DB/Schema; eine persistente SMTP-degraded-Projektion ist noch offen.

Sammel-PDFs, ODT-Erzeugung und große Importe benötigen noch umfassende Mengen-
und Lastgrenzen. Eigenes ODT-Vorlagenmaterial ist vor Bereitstellung zu prüfen.
Projektlizenz/Fremdmaterial bleibt offen; es wird keine Lizenz erfunden.
Ein Restore kann alte Sitzungen reaktivieren: produktiv Widerruf einplanen.

Nach scripts/build_kompetenz.py in einem neuen Zustandsordner mit --apps
gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung,leseflux,kompetenz-manager
installieren. Die geprüfte Umgebung ist .work/pilot-v20. Bestehende Auswahlen
werden nicht erweitert; eigene alte Testcontainer/-netze wurden gezielt entfernt,
um Docker-Subnetze freizugeben. Schlüssel und Volumes bleiben erhalten.

Die Testdienste sind nach den Abnahmen gestoppt. Keine Produktivumstellung,
öffentlichen DNSänderungen, echten Schülerkonten oder externen E-Mails.

Plattform-Quellpaket: 99905ed; [Commit-Rohbeleg](evidence/kompetenz-work-package-commit.log).
