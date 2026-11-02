# Upgrade-Vertrag – noch keine Releasefreigabe

Es existiert noch keine abgenommene Plattformversion. Der aktuelle Stand darf
keine produktive Bestandsinstallation automatisch übernehmen.

| Bestandteil | Implementierter/Teststand | Grenze |
| --- | --- | --- |
| Manifestschema | Version 1 | nur Validierung; keine signierte Releasekette |
| gswb | Python 3.12.12, SQLite user_version 1 | lokaler amd64-Standalone-Test |
| Zackboing | unverändertes SQLite-Schema | Sessionablauf ergänzt |
| Grundschultafel | users.json mit optionalem Bootstrapablauf | atomare Dateien, keine vollständige Schreibtransaktion |
| Losverkauf | unverändertes SQLite-Schema | persönlicher Adminname zusätzlich erforderlich |
| Übrige Apps | unveränderte Auditcommits | noch keine Container-/Plattformabnahme |

Vor jeder späteren Freigabe: Abhängigkeiten/Lizenzen/SBOM und Image-Digests prüfen,
Wartungsfenster ankündigen, Schreibzugriffe drainieren, zusammengehörige DB-, Datei-
und Schlüsselstände sichern, Wiederherstellbarkeit nachweisen, Migration exklusiv
ausführen, App/Proxy aktualisieren, Health-/Fach-/Negativtests ausführen. Das ist eine
verbindliche Betriebsfolge, derzeit kein bereits implementierter Updatecontroller.

Container-Rollback setzt nur das Image zurück. Nach inkompatibler Migration ist
separater Datenbank-Rollback erforderlich: Schreibstopp, konsistenter Restore von
Datenbank, Dateien und Schlüsseln, dazu das kompatible Image. Änderungen seit der
Sicherung können verloren gehen. Ein altes Image allein stellt kein altes Schema her.

Die gswb-App initialisiert Datenbanken nicht mehr beim Start. Bestehende Instanzen
müssen vor dem Start einmal das explizite Migrationskommando aus `PLATFORM.md`
ausführen. Vorher eine konsistente Sicherung erstellen.
