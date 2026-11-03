# Upgrade-Vertrag – noch keine Produktionsfreigabe

Es existiert noch keine abgenommene Plattformversion. Die CLI übernimmt keine
bestehende Hostinstallation automatisch.

| Bestandteil | Implementierter Stand | Nachweisgrenze |
| --- | --- | --- |
| Manifeste | Schema 1 | keine vollständige Releasekombination |
| Releasebundle | Schema 1, Ed25519, unabhängiger Trust-Key | noch kein freigegebenes oder veröffentlichtes Bundle |
| Dashboard | Python 3.12.12, SQLite Schema 1, TOTP-Wrapping-Key | lokaler TLS-/Unix-Dienst-Test; keine produktive Serviceinstallation |
| gswb | Python 3.12.12, SQLite user_version 1 | lokaler Standalone- und Plattformtest |
| schulwissen | Python 3.12.12, eigener PG16, Django-Migrationen | lokaler Standalone-, TLS-, Domain- und DB-Teilstrestore |
| Zackboing | Node 22.23.4, better-sqlite3 11.10.0, SQLite user_version 1 | Standalone, TLS-Spiel, Domainrückfall und leerer Apprestore lokal geprüft |
| Schulhelfer | Python 3.12.12, SQLite user_version 1 / Alembic b7c2e9a41d38 | Standalone, Parallelbuchung, SMTP-Ausfall, lokaler Domainrückfall und leerer Restore |
| Grundschultafel | Node 22.23.4 / Next 16.1.6, Dateischema 1 | JSON-Transaktionen, Sitzungs-/Uploaddenials, Domainrückfall und Dateirestore |
| Losverkauf | Python 3.12.12, SQLite user_version 1, dauerhafte Eingangs-Mailqueue | Standalone, Token-/ID-Erhalt, lokaler Domainrückfall und kombinierter Restore |
| Fahrradausbildung | Python 3.12.12, PostgreSQL 16 / Alembic 0008 | zwei Worker, gemeinsame Limits, öffentlicher Postentoken, PDF-QR-Domainwechsel und PG-/Vorlagenrestore |
| Übrige Apps | unveränderte Auditcommits | noch keine Container-/Plattformabnahme |

Ein Pilot-Installationsplan bindet die lokalen App-Image-IDs. Neue Builds werden
bei einer vorhandenen Installation als Versionswechsel erkannt und verweigert.
Daten und Schlüssel werden dabei nicht ersetzt. Eine neue Pilotumgebung erhält
einen eigenen Zustandsordner und eigene Volumes; sie übernimmt keine Bestandsdaten.

Vor einem späteren produktiven Upgrade: signiertes Bundle und Kompatibilität
prüfen, Wartungsfenster ankündigen, Schreibzugriffe drainieren, zusammengehörige
DB-, Datei- und Schlüsselstände sichern, Wiederherstellbarkeit nachweisen,
Migration exklusiv ausführen, App und Proxy aktualisieren und fachliche sowie
negative Zugriffstests ausführen. Der vollständige Updatecontroller ist noch offen.

**Container-Rollback:** vorheriges kompatibles Image mit alter Konfiguration starten.
Das setzt keine Datenbank zurück.

**Datenbank-Rollback:** nach inkompatibler Migration Schreibstopp, konsistenter Restore
von Datenbank, Dateien und Schlüsseln sowie das passende Image. Änderungen seit
der Sicherung können verloren gehen. Ein Gitcheckout ersetzt keinen DB-Restore.

gswb initialisiert Datenbanken nicht mehr beim Webprozessstart. Vor dem Start
`python -m grundschul_woerterbuch.migrate` ausführen. schulwissen benötigt
`python manage.py platform_migrate`; der Job sperrt konkurrierende Migrationen
über PostgreSQL und richtet danach die vorhandenen Fachrollen ein.

Zackboing benötigt `node server/migrate.js` als expliziten Job. Bestehende Tabellen
und Nutzer-IDs bleiben erhalten; die geprüfte Legacy-Migration setzt user_version 1.
Neue Erstregistrierungen erfordern den lokalen einmaligen Bootstrapcode; eine
bereits explizit geöffnete Registrierung bleibt bestehen. Vor Stop müssen Spiele
abgeschlossen sein. Ein neuer Pilotzustandsordner ist kein Datenupgrade.

Schulhelfer benötigt `python -m app.migrate`, einen Pflicht-Session-Schlüssel und
lokale persönliche Erstadministration. Unversionierte create_all-Bestandsdaten
werden ohne geprüften Adoptionspfad abgewiesen. Keine Änderung bestehender IDs
oder Neugenerierung von Elternlinks durch einen Installationslauf. Mail-Outbox
und verlustfreier Drain von Massenversand sind noch offen.

Losverkauf benötigt `python -m los_migrate`, feste Session-/Elternschlüssel und
eine persönliche Adminidentität. Die bekannte Legacy-Umwandlung erhält IDs und
edit_tokens; zusätzliche unbekannte Felder blockieren die Umwandlung. Bestehende
Elterntoken unter 32 Zeichen müssen vor Übernahme bewusst ersetzt und die Links
neu verteilt werden. Eingangsbestätigungen werden dauerhaft vorgemerkt; SMTP-
Absturzrennen können doppelte Zustellung verursachen. Keine native Altinstallation
wurde automatisch übernommen.

Vor Änderungen bestehender Deployments konsistent sichern und ein Wartungsfenster
nutzen. Der vorliegende Auftrag umfasst weiterhin keine Produktivumstellung.

Grundschultafel benötigt den expliziten Job node scripts/migrate.mjs vor dem ersten
Webstart. Benutzer-UUIDs und Notizbücher bleiben erhalten. Eigene Legacy-Medien
werden ausdrücklich importiert, ohne Konflikte zu überschreiben. Alte JWT-Sitzungen
benötigen erneute Anmeldung. Nicht zugeordnete flache Alt-Uploads werden nicht
automatisch freigegeben. Datei-/Assetbestand und Session-Schlüssel gemeinsam
sichern; bei produktivem Restore Sitzungs-/Bootstrap-Widerruf planen.
Details in [Grundschultafel](docs/implementation/grundschultafel.md).

Fahrradausbildung benötigt python -m app.migrate als expliziten exklusiven Job.
Revision 0008 erhält bestehende Fach-IDs und Postentokens. Neue Compose-DBs
verwenden getrennte Admin-/Appcredentials; vorhandene Cluster werden nicht
automatisch umgestellt. Vor Upgrade pg_dump, Vorlagen und Credentials gemeinsam
sichern und Geräte synchronisieren. Nicht gesendete Browserereignisse gehören
nicht zum Serverbackup. Details: [Fahrradausbildung](docs/implementation/fahrradausbildung.md).

Leseflux benötigt den expliziten Job node scripts/platform-migrate.cjs. Die neue
AuthSession-Tabelle erhält alle Fach- und Nutzer-IDs. Alte JWTs erfordern erneute
Anmeldung; aktuelle Zugänge werden serverseitig widerrufbar. Neue QR-Werte werden
nur gehasht gespeichert. Historische QR-Rohwerte und Auditdaten bleiben erhalten
und werden in API-Projektionen ausgeblendet; ihre Bereinigung muss vor realer
Übernahme separat geprüft werden. Inhaltsjob legt keine Benutzer an. DB-Dump und
private Credentials sichern. [Leseflux-Betriebsvertrag](docs/implementation/leseflux.md).
