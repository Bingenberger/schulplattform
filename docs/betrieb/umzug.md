# Runbook: Umzug vom Altserver auf den neuen Server

Grundsatz: Auf dem Altserver wird **nichts verändert**. Das Werkzeug liest dort nur und schreibt seine Archive in ein Verzeichnis, das Sie angeben. Der Altserver bleibt bis zur Abnahme der Rückfallweg.

## 0. Vorbereitung (Tage vorher)

1. Den neuen Server nach [bereitstellung.md](bereitstellung.md) installieren. Alle Apps laufen dort zunächst leer.
2. Die TTL der DNS-Einträge aller App-Hostnamen beim Provider auf 300 s senken.
3. Auf dem **neuen** Server: `./install.sh import-key`. Die angezeigte Datei sicher auf den Altserver kopieren (z. B. `scp`).
4. Auf dem **Altserver** (nur lesend, ohne Root, wo möglich):

   ```sh
   python3 schulplattform_altserver.py inventory > inventory.json
   ```

   Die Datei enthält Version, Speicherart, Schemastand, Datenpfade, Größen und die **Namen** der Secrets, keine Werte und keine personenbezogenen Daten. Weichen Pfade ab, geben Sie sie mit `--app NAME=PFAD` an, Compose-Projekte mit `--compose-project NAME=PROJEKT`.
5. Inventar prüfen: Steht bei jeder App ein Commit? Passt der Schemastand? Siehe Tabelle unten.

## 1. Umzug je App (Wartungsfenster, App für App)

| Schritt | Altserver | Neuer Server |
| --- | --- | --- |
| a | Schreibstopp ankündigen; bei Bedarf die App kurz in den Wartungsmodus (eigener Weg der App) | – |
| b | `python3 schulplattform_altserver.py export APP --key-file transfer.key --out /sicher/` | – |
| c | Archiv per `scp` übertragen | – |
| d | – | `./install.sh import APP ARCHIV --dry-run` → Bericht prüfen (Quelle, Schema, Zeilenzahlen, übernommene Secrets) |
| e | – | `./install.sh import APP ARCHIV --confirm-replace` → automatische Sicherung des bisherigen Zustands, Übernahme, Migration, Start, Zeilenvergleich |
| f | – | Stichprobe: Anmeldung mit einem bestehenden Konto, ein öffentlicher Link |
| g | DNS-Eintrag der App beim Provider auf den neuen Server umstellen | `./install.sh reconcile` (läuft auch stündlich) |
| h | Altserver-App gestoppt lassen, aber **nicht löschen** | – |

**Rückfall:** Scheitert e, bleibt der neue Server bei der automatisch erstellten Sicherung. Mit `./install.sh restore APP <Sicherung> --confirm-replace` wird zurückgespielt. Der Import selbst verweigert, wenn die App vorher nicht gesund war. Der Altserver bleibt unverändert in Betrieb.

## 2. Stand der Übernahmepfade (getestet mit synthetischen Altbeständen der geprüften Basis-Commits)

| App | Altserver-Betriebsart | Ergebnis im Test | Hinweis |
| --- | --- | --- | --- |
| losverkauf | nativ, SQLite | **übernommen**, Zeilen vollständig, alter Elternlink funktioniert | Elterntoken und Session-Schlüssel werden mitgenommen. Die Karte wandert von `static/` nach `data/maps/`. Token unter 32 Zeichen müssen ersetzt und Links neu verteilt werden. |
| fahrradausbildung | Docker Compose, PostgreSQL 16 | **übernommen**, Alembic 0007 → 0008, Zeilen vollständig, Eigentümer `fahrrad` | – |
| schulhelfer | nativ, SQLite (`create_all`) | **verweigert** (unversionierte Datenbank) | Ein Adoptionspfad im App-Code fehlt. Die App blieb auf dem gesicherten Stand. |
| schulwissen, leseflux, abgen | Docker Compose, PostgreSQL | nicht getestet | Export- und Importweg identisch zu fahrradausbildung. abgen: Drizzle-Historie muss passen. |
| gswb, zackboing, kompetenz-manager, grundschultafel | nativ | nicht getestet | Zuordnung der Pfade im Werkzeug hinterlegt. kompetenz-manager übernimmt nur einen passenden Ausgangsstand. grundschultafel: eigene Medien ausdrücklich importieren. |

## 3. Wer muss sich neu anmelden?

- grundschultafel, leseflux, kompetenz-manager: alte Sitzungen sind ungültig (neue Sitzungsverwaltung)
- alle Apps, deren Session-Schlüssel nicht mitgenommen wird (alle außer losverkauf): einmalige Neuanmeldung
- Elternlinks losverkauf: bleiben gültig, wenn der Token mindestens 32 Zeichen hat

## 4. Abschluss

Nach vollständiger Umstellung und einer Woche Parallelbetrieb ohne Rückfall:

1. Altserver abschalten. Seine Daten bleiben archiviert.
2. Den Transferschlüssel auf beiden Servern löschen.
