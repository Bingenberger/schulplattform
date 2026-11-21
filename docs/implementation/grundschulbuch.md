# Grundschulbuch – Plattform-App

Stand: 21. November 2026. Quelle: `/home/emrichschule/grundschulbuch` (Repository
`Bingenberger/grundschulbuch`, öffentlich, Lizenz CC BY-NC-SA 4.0), Symlink `.work/apps/grundschulbuch`.

| Commit | Inhalt |
| --- | --- |
| `e5e6311` | getesteter Stand (Spitze von `verwaltung-originalvorlagen`, per Fast-Forward nach `main`) |
| `0156ba1` | verwalteter Release-Workflow aktualisiert (Token-Checkout wie bei den übrigen Apps; einziger Unterschied) |

Entscheidungen des Auftraggebers (21. November 2026): Stand = Branch-Spitze nach Merge in `main`,
keine Altdaten (Neueinrichtung), Vorschlag für den Hostnamen `buch.<domain>`.

## Kein Patch nötig

Die App wurde von Anfang an nach dem Plattformvertrag gebaut (`PLATFORM.md` im Repository): UID/GID 10001,
schreibgeschütztes Root-Dateisystem, `/tmp` als tmpfs, Migration als expliziter Job
(`node scripts/migrate.mjs`), kein Konto beim Start, Erstzugang nur am Terminal
(`node scripts/bootstrap.mjs NAME --admin`), `/health/live` und `/health/ready` ohne externe Dienste,
Herkunftsprüfung gegen `BASE_URL`. `patches/grundschulbuch/changes.patch` ist deshalb leer
(`baseCommit` = `implementationCommit` = `e5e6311`).

## Plattform

- `catalogue.py`: Index 17, Port 3000, Image `grundschulbuch` (Target `runtime`), Secret `buch-key`
  (über `GRUNDSCHULBUCH_SECRET_FILE` aus der Compose-Datei der App), gemeinsames `gallery-api-token`,
  Betreiberverzeichnis `runtime/grundschulbuch/inhalte` (über `GRUNDSCHULBUCH_ASSET_DIR`, schreibgeschützt
  nach `/assets`), Migration, Erstzugang per `exec` mit Anzeigename, Prüf-URLs:
  `GET /api/bilder?quelle=galerie&q=apfel` → 401, `GET /api/medien/beispiel.webp` → 401,
  `POST /api/verwaltung` ohne eigene Origin → 403.
- `config.py`: in `GALLERY_APPS` und `WOERTERBUCH_APPS` (gleiche Regeln wie die Tafel: fehlt = eigene
  Galerie bzw. eigenes gswb, `""` = aus, sonst https-Origin). Das Token geht nur an die eigene Galerie.
- Schemas, Dashboard-Kachel („Grundschulbuch – Digitale Hefte für Tafel, iPad und Druck“, nicht öffentlich),
  Import-Hinweis, Release-Fakten (`files`, Volume `data` → `/data`, 512 MiB, 1 CPU), Adapter-Referenz.
- Nicht angebunden: YouTube-Schlüssel (setzt ein Admin in der App, liegt im Datenvolume), KI-Dienst (aus),
  Altserver-Export (keine Altdaten).

## Nachweise (lokal, 21. November 2026)

| Prüfung | Ergebnis |
| --- | --- |
| `docker build --target tests` aus sauberem `git archive e5e6311` | Typecheck, Lint, 384 Tests bestanden, 1 übersprungen |
| Plattform-Abnahme `scripts/verify_grundschulbuch_platform.py` (echtes Override aus dem Katalog, Compose v2.40.3) | `grundschulbuch-platform.json`: Migrationsjob zweimal, `up --wait` gesund, kein Host-Port, nur Proxy- und eigenes Netz, Prüf-URLs wie erwartet, Erstzugang ohne Terminal abgelehnt, mit pty angelegt, fremde Origin 403, Einmalcode nur einmal, Cookie HttpOnly/Secure/SameSite=Strict, Verwaltung erreichbar, Token lesbar, Root-Dateisystem nicht beschreibbar, nach Neuanlage des Containers Sitzung und PIN-Anmeldung gültig |
| Plattform-Tests (`pytest tests`) | 236 bestanden |

| VM, Update 0.3.5 → 0.3.6 mit signiertem Bundle (`grundschulbuch-vm-0.3.6.log`) | neue App per `apply --reconfigure` aktiv, bestehende Apps unberührt; Erstzugang per `app-setup`, HTTPS-Anmeldung, Verwaltung, Galerie-Token und Wörterbuch (mit Test-CA), Sicherung mit Offsite-Kopie, Restore nach Datenverlust: Konten und PIN zurück |

Release: `grundschulbuch:0.1.0` (Tag `v0.1.0` auf `0156ba1`, leichter Tag; `make_release.py` akzeptiert jetzt
leichte und annotierte Tags), Bundle `releases/0.3.6`.
Bundle-Flags: `--version 0.1.0 --platform-version 0.2.0 --bundle-version 0.3.6` plus `--app-version` wie 0.3.5
(bildergalerie=0.1.1 fahrradausbildung=0.2.0 grundschultafel=0.1.5 gswb=0.1.1 losverkauf=0.1.1
schulanmeldung=0.1.1 schulhelfer=0.1.2 schulkasse=0.2.0 schulwissen=0.1.2).

**Offen:** Rollout auf dem echten Server (DNS `buch.<domain>` setzen, `configure`, `apply --reconfigure`,
`app-setup grundschulbuch`); Kinderzugang per QR-Karte und Oberfläche im Browser nur lokal geprüft, nicht in der VM.
