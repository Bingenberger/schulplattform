# Upgrade-Vertrag – noch keine Produktionsfreigabe

Es existiert noch keine abgenommene Plattformversion. Die CLI übernimmt keine
bestehende Hostinstallation automatisch.

| Bestandteil | Implementierter Stand | Nachweisgrenze |
| --- | --- | --- |
| Manifeste | Schema 1 | keine vollständige Releasekombination |
| Releasebundle | Schema 1, Ed25519, unabhängiger Trust-Key | noch kein freigegebenes oder veröffentlichtes Bundle |
| gswb | Python 3.12.12, SQLite user_version 1 | lokaler Standalone- und Plattformtest |
| schulwissen | Python 3.12.12, eigener PG16, Django-Migrationen | lokaler Standalone-, TLS-, Domain- und DB-Teilstrestore |
| Zackboing | unverändertes SQLite-Schema | Sessionablauf ergänzt |
| Grundschultafel | users.json mit optionalem Bootstrapablauf | atomare Dateien, keine vollständige Schreibtransaktion |
| Losverkauf | unverändertes SQLite-Schema | persönlicher Adminname zusätzlich erforderlich |
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

Vor Änderungen bestehender Deployments konsistent sichern und ein Wartungsfenster
nutzen. Der vorliegende Auftrag umfasst weiterhin keine Produktivumstellung.
