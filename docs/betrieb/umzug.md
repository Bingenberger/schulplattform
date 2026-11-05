# Runbook: Umzug vom Altserver auf den neuen Server

Laufen die Apps auf **mehreren Altservern**, gilt alles hier je Server: Werkzeug und Transferschlüssel auf jeden Altserver kopieren, Inventar je Server erstellen. Apps, die auf einem Server nicht installiert sind, meldet das Inventar als nicht vorhanden.

Grundsatz: Auf dem Altserver wird **nichts verändert**. Das Werkzeug liest dort nur und schreibt seine Archive in ein Verzeichnis, das Sie angeben. Der Altserver bleibt bis zur Abnahme der Rückfallweg.

## 0. Vorbereitung (Tage vorher)

1. Den neuen Server nach [bereitstellung.md](bereitstellung.md) installieren. Alle Apps laufen dort zunächst leer.
2. Die TTL der DNS-Einträge aller App-Hostnamen beim Provider auf 300 s senken.
3. Auf dem **neuen** Server: `./install.sh import-key`. Die angezeigte Datei sicher auf den Altserver kopieren (z. B. `scp`).
4. Auf dem **Altserver** (nur lesend, ohne Root, wo möglich):

   ```sh
   python3 schulplattform_altserver.py inventory > inventory.json
   ```

   Die Datei enthält Version, Speicherart, Schemastand, Datenpfade, Größen und die **Namen** der Secrets, keine Werte und keine personenbezogenen Daten. Weichen Pfade ab, geben Sie sie beim Inventar mit `--app NAME=PFAD` an, Compose-Projekte mit `--compose-project NAME=PROJEKT`; beim **Export** heißen die Optionen `--path PFAD` und `--compose-project PROJEKT`.
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
| schulhelfer | nativ, SQLite (`create_all`, `/opt/schulfest/data/app.db`, Unit `schulfest-helfer.service`) | **auf dem echten Server übernommen** (2026-11-05, schulhelfer 0.1.1; zuvor lokal: `create_all`-Datenbank des Basis-Commits, auch ohne Spalte `token`) | Die Migration vergleicht die Struktur mit den bekannten Alembic-Ständen und stempelt nur bei exakter Übereinstimmung; sonst Abbruch mit den abweichenden Tabellen. Persönliche Links bleiben gültig (Token-Hash in der Datenbank); Admins melden sich neu an. |
| leseflux | Docker Compose (`lesefluss`), PostgreSQL 16 | **auf dem echten Server übernommen** (2026-11-05, 6.396 Zeilen, Prisma vorwärts um `AuthSession`) | Export mit `--compose-project`; vorher nur `api` und `web` stoppen. QR-Karten enthalten nur den Token und bleiben gültig. |
| schulwissen, abgen | Docker Compose, PostgreSQL | nicht getestet | Export- und Importweg identisch zu fahrradausbildung. abgen: Drizzle-Historie muss passen. |
| kompetenz-manager | nativ, SQLite **oder PostgreSQL** (`DATABASE_URL` im `EnvironmentFile` des Dienstes) | PostgreSQL → SQLite **auf dem echten Server übernommen** (2026-11-05; zuvor lokal mit PostgreSQL 16 und Stand `dd5f14c`), Schema 0001 bestätigt | Der Export wandelt mit der Python-Umgebung der App aus einem lesenden Snapshot um und bricht ab, wenn Tabellen oder Spalten vom Datenmodell abweichen. Dienst und Arbeitsverzeichnis werden selbst erkannt, abweichende Pfade mit `--path`/`--app`. |
| fundkiste | nativ, SQLite (`/opt/fundkiste`, Unit `fundkiste.service`) | **auf dem echten Server übernommen** (2026-11-05, 70 Zeilen, Team-Schlüssel und QR-Codes erhalten) | Der Team-Schlüssel aus `Environment=FUNDKISTE_TEAM_KEY` der Unit wird zu `data/team_key.txt`; ausgehängte QR-Codes bleiben gültig. Einträge älter als die Aufbewahrungsfrist löscht die App nach dem Import beim ersten Aufruf. |
| schuleva | nativ, SQLite (`/opt/schulbefragung`, Unit `schulbefragung.service`) | **auf dem echten Server übernommen** (2026-11-05; Hostname muss `SCHOOL_DOMAIN` entsprechen, er steht auf den TAN-Zetteln) | Eigene Fragebögen aus `surveys/` ziehen nach `data/surveys`; die täglichen Cron-Kopien in `data/backups/` bleiben auf dem Altserver. Alle müssen sich einmal neu anmelden. |
| schulkasse | nativ, SQLite (`/opt/schulkasse/instance`, Unit `schulkasse.service`) | **auf dem echten Server übernommen** (2026-11-05, 3.511 Zeilen, Schema 9, Anmeldung mit 2FA geprüft) | **Der alte `SCHULKASSE_SECRET_KEY` muss mit** (verschlüsselt die 2FA-Geheimnisse); das Werkzeug liest ihn aus `.env`. Belege und `brief.toml` ziehen mit, die app-eigenen Backups nicht. |
| schulanmeldung | nativ, SQLite (Pfad aus `SL_OFFICE_DATABASE_URL` der `.env`, Unit `sl-office.service`) | **auf dem echten Server übernommen** (2026-11-05, Alembic `b4c1e82f5a37`, 3.114 Zeilen) | Datenbank, Uploads und Unterschrift über die Pfade der `.env`; das konfigurierte und das Standard-Upload-Verzeichnis werden zusammengeführt (Altserver: `documents/` und `uploads/`). Export mit `--path` (z. B. `/opt/SL-Office`). Eltern-Zugangslinks bleiben bei gleichem Hostnamen gültig; Personal meldet sich neu an (2FA bleibt). Erinnerungs-Timer des Altservers stoppen, falls eingerichtet. |
| sl-journal | nativ, SQLCipher (`JOURNAL_INSTANCE`, Schlüssel `JOURNAL_KEY_FILE`, Unit `journal.service`) | nachgebauter Altbestand exportiert (lokal) | **Vorher `journal.service` und beide Timer stoppen** (die verschlüsselte Datei wird als Datei kopiert). Der Originalschlüssel kommt als Secret mit; ohne ihn sind die Daten verloren. Passwort und Authenticator bleiben; Sitzungen und Android-Geräte müssen sich neu anmelden. |
| zackboing | nativ, SQLite (`ZACKBOING_DATA` der Unit, Vorgabe `/var/lib/zackboing`, Unit `zackboing.service`) | **auf dem echten Server übernommen** (2026-11-05, 82 Zeilen; Hostname danach per `domain-change` gewechselt) | Die laufende App hält die Daten im WAL (Datei nur 4 KiB); der Export liest sie über die SQLite-Sicherungsschnittstelle mit. Uploads ziehen mit. Fehlende Spalten werden ergänzt; ohne Rollen-Spalte wird das älteste Konto Admin. |
| gswb | nativ (`/var/www/grundschul-woerterbuch`, Stand `7c2875b` = Basis) | **auf dem echten Server übernommen** (2026-11-05) | Export mit `--path`; Datenbank, Bilder, Audio und Uploads ziehen mit. |
| grundschultafel | nativ (`/var/www/tafelpopafel`, Unit `tafelpopafel.service`, Stand `496466c` = Basis) | **auf dem echten Server übernommen** (2026-11-05, 26 Konten) | `data/` (users.json, Notizbücher je Benutzer-UUID) und `public/assets` → `data/assets` (Hintergründe, Journal, RS, Galerie, Uploads). Export mit `--path`. Alle melden sich neu an. Das alte Standardkonto `admin` (Passwort 123456, Wechsel verlangt) vorher prüfen. grundschultafel: eigene Medien ausdrücklich importieren. |

## 3. Wer muss sich neu anmelden?

- grundschultafel, leseflux, kompetenz-manager: alte Sitzungen sind ungültig (neue Sitzungsverwaltung)
- alle Apps, deren Session-Schlüssel nicht mitgenommen wird (alle außer losverkauf): einmalige Neuanmeldung
- Elternlinks losverkauf: bleiben gültig, wenn der Token mindestens 32 Zeichen hat

## 4. Abschluss

Nach vollständiger Umstellung und einer Woche Parallelbetrieb ohne Rückfall:

1. Altserver abschalten. Seine Daten bleiben archiviert.
2. Den Transferschlüssel auf beiden Servern löschen.
