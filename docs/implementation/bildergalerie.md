# Bildergalerie – Plattform-App (Auftrag „Bildergalerie und Wörterbuch“, B2)

Stand: 7. November 2026. Quelle: `/home/emrichschule/Bildergalerie` (bisher kein Git-Repository),
produktiv unter https://pix.foerster.rocks (87.106.86.217). Neues Repository `Bingenberger/bildergalerie`
(nur Code; Datenbanken, Bilder, `.env`, `key3.json`, `cookies.txt` per `.gitignore` ausgeschlossen,
Historie vor dem ersten Commit auf Secrets geprüft: keine Treffer im Code).

| Commit | Inhalt |
| --- | --- |
| `f13c912` | Ausgangsstand wie vorgefunden (Basis) |
| `4b1fe55` | Plattform-Version (getesteter Stand, `patches/bildergalerie/changes.patch`) |
| `3acd4a0` | verwalteter Release-Workflow (einziger Unterschied zum getesteten Stand) |

## Umsetzung

- **Container-Vertrag:** UID/GID 10001, schreibgeschütztes Root-Dateisystem, Volumes `db` (`/data/db`)
  und `media` (`/data/media`) getrennt, `/health/live` und `/health/ready` (Schema aktuell, Medien
  beschreibbar; keine externen Dienste), Gunicorn mit 1 Worker und 4 Threads, Port nur auf Loopback.
- **Migration als Job** (`python migrate.py`): neue Datenbank oder Übernahme der Altdatenbank. Die alte
  Version legte Tabellen mit `create_all` an und ergänzte Spalten per `ALTER TABLE`; übernommen wird nur,
  wenn ausschließlich die bekannten Tabellen und Spalten vorhanden sind (fehlende ältere Spalten werden
  ergänzt, unbekannte führen zum Abbruch ohne Änderung). IDs, Dateinamen und Konten bleiben.
  Schema 2 ergänzt Erstzugang, Sitzungsversion, Anmeldesperre, Bildmaße und Indizes.
- **Kein Standardkonto:** `BOOTSTRAP_ADMIN`, `DEFAULT_ADMIN_PASSWORD` und `update_existing_instance.py`
  entfallen. `python bootstrap.py <name>` (Plattform: `./install.sh app-setup bildergalerie`) legt nur
  ohne bestehende Konten einen Zugang mit Einmal-Passwort an (nur auf `/dev/tty`, 15 min gültig, Pflicht
  zum eigenen Passwort mit mindestens 12 Zeichen).
- **Anmeldung:** Sperre nach 5 Fehlversuchen je Name für 15 min (unbekannte Namen teilen einen Zähler),
  Passwortwechsel beendet andere Sitzungen, Abmelden per POST. CSRF für alle schreibenden Anfragen
  (vorher schon vorhanden, jetzt auch für Logout).
- **Uploads:** Signatur (PNG/JPEG/GIF/WebP) muss zum erkannten Format passen, Pixel- (40 MP) und
  Größenlimit (20 MB), Dateiname = bereinigter Wortstamm + 12 zufällige Hex-Zeichen, Endung nach Format.
- **Sichtbarkeit:** `GALLERY_PUBLIC` (Plattform: `public` in `[apps.bildergalerie]`, Standard `true`).
  Neu: nicht freigegebene Bilder sehen nur Angemeldete (vorher waren sie auf der Startseite, im
  Download und in der ZIP-Sammlung für alle sichtbar). `/license` bleibt immer öffentlich.
- **JSON-API v1** nach Vertrag (API.md im Repository): `/api/v1/images`, `/api/v1/images/{id}`,
  `/api/v1/tags`, `/media/{thumbnails,display}/<datei>`. Suche über Beschreibung, Schlagworte und Stil,
  ohne Groß-/Kleinschreibung auch für Umlaute, Sortierung neueste zuerst; Platzhalter `%`/`_` wörtlich.
  `/static/{thumbnails,display}/…` bleiben als Alias für bestehende Links.
- **KI-Metadaten:** nur mit `GALLERY_AI_KEY_FILE` (Plattform: `./install.sh gallery-ai-key DATEI`).
- **Keine fremden Abrufe:** Bootstrap 5.3.0, Tagify 4.36.0 (vorher ohne Versionsangabe vom CDN),
  Dropzone 5.9.3 und die Schriften Fraunces/Manrope (OFL) liegen unter `static/vendor`.

## Zugriff der Tafel: Entscheidung

Die Galerie ist öffentlich lesbar wie bisher, also ist auch die API öffentlich (Variante „öffentlich“).
Zusätzlich erzeugt die Plattform immer `gallery-api-token` und gibt es Galerie und Tafel als Datei; die
Tafel sendet es nur an die **eigene** Galerie. Damit funktioniert die Tafel unverändert weiter, wenn die
Schule die Galerie auf „nur für Angemeldete“ stellt (dann ist die API nur mit Token erreichbar, geprüft
im Verbundtest). Ein Token an eine fremde Galerie wird nie gesendet.

## Plattform

`catalogue.py` (Index 16, Secrets `gallery-key`, `gallery-api-token`, `gallery-ai-key`, Migration,
Prüf-URLs, Setup), Schemas, `config.py` (`public`, Vorschlag `bilder.<domain>`, `gallery_origin`
mit „leer = eigene Galerie, `""` = aus“), Dashboard-Kachel (öffentlich, wenn die Galerie öffentlich ist),
Release-Fakten, Import-Hinweis, Altserver-Export mit SHA-256 je Bilddatei und Prüfung beim Import,
Adapter `adapters/bildergalerie/platform.yml`.

**zackboing:** Die Galerie-Fixture in `tests/test_altserver.py` gehört zur Tafel
(`public/assets/gallery`), nicht zu zackboing; zackboing hat keinen Galerie-Abruf. Nicht angebunden.

## Nachweise (lokal, 7. November 2026)

| Prüfung | Ergebnis |
| --- | --- |
| App-Tests im `tests`-Image (read-only, ohne Netz) | 30/30 |
| Standalone, leere Volumes: Migration als Job, Erstzugang über ein echtes Terminal, zweiter Erstzugang abgelehnt, Passwortwechsel, Upload, Freigabe, danach API | `bildergalerie-standalone.json`: vor Freigabe 0 Treffer, danach 1 mit Schlagworten, Stil und Maßen; WebP mit `nosniff`; Traversal 404 |
| Altbestand (lokale Kopie, 88 Bilder) | `bildergalerie-standalone-legacy.json`: übernommen, Maße für 88 Bilder nachgetragen, API 88, Medien 200, Erstzugang bei vorhandenen Konten abgelehnt |
| Oberfläche im Browser (Chromium/Playwright) | Startseite, Lizenz, Login, Sammeln: keine Konsolenfehler, keine Anfragen an fremde Server, Detailansicht öffnet |
| Plattform-Override mit Docker Compose v2.40.3 | Migrationsjob zweimal, `up --wait` gesund, kein veröffentlichter Port, nur Proxy-Netz, Token/KI-Datei eingebunden |
| Verbund Tafel + private Galerie (Token) + gswb | `tafel-gallery-woerterbuch.json`, siehe grundschultafel.md |
| Plattform-Tests | 215 bestanden |

**Offen:** Release-Image aus GitHub Actions (Repository muss angelegt werden), Abnahme mit signiertem
Bundle in der VM (Restore auf leerem Ziel mit Prüfsummen, manipuliertes Bundle), Datenübernahme vom
echten pix.foerster.rocks (Pfad, Unit und Codestand dort unbekannt; das Inventar zeigt sie).

## Entscheidungen des Auftraggebers

1. **Öffentlichkeit der Galerie:** Standard bleibt öffentlich durchsuchbar. Umstellen mit `public = false`.
2. **Token-Variante:** umgesetzt, wirkt aber nur bei nicht öffentlicher Galerie; keine Entscheidung nötig,
   solange die Galerie öffentlich bleibt.
3. **Lizenztexte:** `/license` beschreibt CC0 1.0 und KI-Herkunft; die API gibt den Kurzhinweis
   „KI-generiert, CC0 1.0 (gemeinfrei), Namensnennung nicht erforderlich“ aus (änderbar über
   `GALLERY_LICENSE_NOTE`). Bitte bestätigen, dass alle Bilder (auch künftige Uploads) unter CC0 stehen
   dürfen; Impressum und Datenschutz verweisen weiterhin auf emrich.in.
4. **Repository:** `Bingenberger/bildergalerie` anlegen (öffentlich wie die übrigen Apps oder privat mit
   öffentlichem GHCR-Paket wie schulanmeldung).
5. **Domain:** Soll die Plattform-Galerie unter `pix.foerster.rocks` laufen (DNS umstellen, alte Links
   bleiben gültig) oder unter einer neuen Adresse wie `bilder.gsndk.de`?

## B4 – Ausblick (nur bewertet)

**Galeriebilder für eigene Wortlisten.** Blitzlesen könnte für Wörter ohne Wörterbuchbild in der Galerie
suchen (`/api/v1/images?tags=<wort>` exakt, sonst `q=<wort>`). Treffergüte: Die Schlagworte stammen
meist aus dem Dateinamen (ein Substantiv je Bild, kleingeschrieben) und sind für konkrete Nomen gut
(„apfel“, „drucker“); bei Verben, Adjektiven, Funktionswörtern und Mehrdeutigkeiten („Bank“, „Schloss“)
schlecht, eine Freitextsuche liefert dann thematisch verwandte, aber falsche Bilder. Empfehlung: nur
exakte Schlagwort-Treffer automatisch vorschlagen, sonst Auswahl durch die Lehrkraft. Aufwand gering
(eine Tafel-Route, die vorhandene API, Anzeige im Wortlisten-Editor; etwa ein Tag), die Bilder müssten wie
heute beim Einfügen als Data-URL gespeichert werden.

**Eine Bildquelle für zwei Apps.** gswb hat rund 3.550 Wortbilder (`static/images/<WORT>.webp`, ein Bild je
Lemma, Name = Schlüssel), die Galerie freie Illustrationen mit Schlagworten. Gemeinsam ist der Stil (KI,
Aquarell) und teilweise das Motiv. Eine gemeinsame Quelle ohne gemeinsame Datenbank ginge so: Die Galerie
wird Medienquelle, gswb speichert nur eine Galerie-ID je Wort und holt das Bild über `/media/display/…`.
Dagegen sprechen: gswb müsste dann für jede Wortseite von der Galerie abhängen (heute eigenständig und
öffentlich), Freigabe und Lizenz unterscheiden sich (Wörterbuchbilder sind redaktionell an das Lemma
gebunden), und Umbenennen/Löschen in der Galerie würde Wörterbuchseiten brechen. Empfehlung: getrennt
lassen; stattdessen die Wörterbuchbilder **einmalig** als freigegebene Galerie-Bilder mit Schlagwort =
Lemma importieren (Duplikate per Prüfsumme erkennbar). Damit findet die Tafel-Galerie auch diese Motive,
ohne dass eine App von der anderen abhängt. Aufwand: ein Importskript (etwa ein halber Tag) plus
Lizenzklärung für die Wörterbuchbilder.
