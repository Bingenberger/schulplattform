# Grundschultafel: sechste App im lokalen Pilot

Stand: 3. November 2026. Auditiert bei 496466cac7cc2b3e48a6acd2940ebc91029c145f;
[Umsetzungscommit und vollständiger Patch](../../patches/index.json).
Alle Testkonten, PINs, Notizbücher und Bilder sind synthetisch.

## Beobachtet und implementiert

Eigenständiges Compose und Next-Standalone-Image: Node 22.23.4 mit Basisdigest,
Next 16.1.6 aus package-lock.json, amd64. UID/GID 10001, Read-only-Root,
64 MiB /tmp, 512 MiB RAM, eine CPU, 128 PIDs als konfigurierte Grenzen.
[Image](evidence/grundschultafel-image.json),
[Runtimebuild](evidence/grundschultafel-build-runtime.log),
[Testimage](evidence/grundschultafel-build-tests.log).
300284206 Byte Imagegröße ist Docker-Metadatum, keine RAM-Messung.

Keine privaten Unterrichtsmedien oder extern geladenen Schriften im Image.
Systemschriften und vorhandener HTML-Timer; eigene Medien importiert der Betreiber.
Lizenzentscheidung für App und Unterrichtsmedien bleibt offen; kein Registry-Upload.

Expliziter Dateischema-Job (Version 1), keine Migration beim Webstart. Nutzer-UUIDs
und Notizbücher bleiben erhalten. Import eigener Alt-Assets nimmt nur reguläre
Dateien/Verzeichnisse an: identische Dateien bleiben, Konflikte und Links brechen ab.
Fremde Schema-Versionen scheitern. Anonyme Aufrufe erzeugen weder Konto noch Schema.

Persönlicher Kurz-PIN-Zugang mit lokalem Einmalbootstrap, 15 Minuten gültig,
ausschließlich am kontrollierenden Terminal. Danach persönliche sechsstellige PIN.
Nutzeränderungen halten eine prozessübergreifende Sperre über vollständiges
Lesen/Ändern/Schreiben einschließlich Hashberechnung. Notizbücher ebenfalls gesperrt
und atomar; keine inhaltliche Zusammenführung konkurrierender Entwürfe.

Acht-Stunden-Sitzungen prüfen serverseitigen Datensatz, gehashtes Gerätecookie
und aktuellen Nutzer-/PINstand. JWT allein scheitert; PIN-Reset, Löschung und
Logout widerrufen Sitzungen. Gerätecookie ist keine Hardwarebindung: Beide Cookies
zusammen bleiben kopierbar. Persistente PIN-Drosselung: fünf Fehlversuche,
15 Minuten Kontosperre, auch nach Neustart.

Mobile QR-Links verlangen ein durch die Lehrkraft ausgestelltes 15-Minuten-Ticket.
Das Telefon braucht keine Fachanmeldung. Ein Upload pro Ticket; PNG/JPEG/WebP-
Dateisignatur, höchstens 5 MiB, zufälliger Name. Polling und Bilddatei nur für den
Eigentümer. Ticket- und Dateiquoten; keine vollständige Bilddecoder-Prüfung.
Alte flache Uploads ohne verlässliche Eigentümerzuordnung werden nicht freigegeben.

Galerie und YouTube-Suche standardmäßig deaktiviert (503); Readiness bleibt gesund.
Optionale Galerie: konfigurierte Origin, keine Redirects, Zeit-/Größenlimit.
Direkt eingefügte Videos können externe Browserabrufe auslösen.

## Ausgeführt

- Acht Dateilaufzeit-Verträge unter festgelegtem Node 22 ohne Netzwerk:
  acht getrennte konkurrierende Schreibprozesse, Migration/Import,
  Sitzungswiderruf, Ticketverbrauch und Quoten.
  [Rohlog](evidence/grundschultafel-runtime-contracts.log).
- Echtes Standalone-HTTP: Readiness vor Migration 503, geschlossener Erstzugang,
  PIN-Wechsel, vier parallele Nutzeranlagen, Rollen-/Eigentümerdenials,
  kopiertes JWT, Neustart, anonymer Telefonupload, einmaliges Polling, private Bilder,
  persistente PIN-Sperre und Widerruf.
  [Rohlog](evidence/grundschultafel-standalone.log).
- Generischer Snapshot mit expliziten Einzeldateien sowie Verzeichnissen.
  Alle Schreiber gestoppt; vollständiger JSON-/Notizbuch-/Asset-Snapshot,
  Prüfsumme, neues leeres Volume, Originalschlüssel separat bereitgestellt.
  Start ohne Migration/Bootstrap; Nutzer-ID, Notizbuch, Bild und Rollen erhalten.
  Fremder Zugriff und gelöschtes Konto bleiben abgewiesen. Nichtleeres Ziel scheitert.
  [Ergebnis](evidence/grundschultafel-restore.json),
  [Kommandos](evidence/grundschultafel-restore-operations.json),
  [Snapshot-Negativtests](evidence/grundschultafel-snapshot-tests.log).
- Sechserpilot mit verifizierter lokaler CA: ausschließlich Caddy-TLS auf Loopback,
  private Rootless-Backends. Domainwechsel prüft Login, Nutzer-ID, Notizbuch,
  QR-Ziel und Origin-Denial; erzwungener Prüffehler rollt zurück.
  Zwei No-op-Läufe erhalten Container, Schlüssel und Checkpoints.
  Stop liefert 503, Start erhält Daten ohne erneute Migration.
  [Ergebnis](evidence/grundschultafel-platform.json),
  [Kommandos](evidence/pilot-v12-operations.jsonl).

- Der reale Dashboardcontainer steuert Grundschultafel über den authentifizierten
  Unix-Dienst: TOTP, CSRF, Start/Stop, kein Docker-Socket und kein Fachzugang durch
  die Plattformrolle. [Ergebnis](evidence/dashboard-container.json).
- Der vollständige Patch lässt sich auf den Auditcommit anwenden und erzeugt
  denselben Quellbaum. [Patch-Replay](evidence/grundschultafel-patch-replay.log),
  [Appcommit](evidence/grundschultafel-app-commit.log),
  [Secretprüfung](evidence/grundschultafel-secret-scan.log).

## Reproduktion

Nach Checkout und Anwendung der Apppatches:

~~~sh
.venv/bin/python scripts/build_grundschultafel.py
.venv/bin/python scripts/prove_grundschultafel_standalone.py
.venv/bin/python scripts/verify_grundschultafel_restore.py
./install.sh pilot-up --state-dir .work/pilot-neu --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel
~~~

Fünf weitere Images und gepinnte Infrastruktur/Compose müssen gemäß
[Pilotanleitung](pilot.md) bereitstehen. Bestehende Pilotordner behalten Auswahl
und Image-IDs. Ein neuer Zustandsordner übernimmt keine Altvolumes.
Der Domainversuch ist ein synthetischer Fixturelauf für .work/pilot-v12,
kein allgemeiner produktiver Domaincontroller.

## Offen und Grenzen

Keine Ubuntu-Neuinstallation, öffentliche DNS-/Besitz-/ACME-Prüfung,
Lastmessung, ARM64-Abnahme oder vollständige Fach-/Browserprüfung.
QR-Ziel per HTTP geprüft; kein Kamerascan oder visueller Canvas-Test.
Konfigurierte Limits sind keine gemessene Kapazität.

Sicherung lokal und unverschlüsselt. Plattform-/Secretstore-/Offsite-Gesamtbackup,
Rotation und Alarmierung bleiben offen. Restore kann alte Sitzungs-/Bootstrapstände
reaktivieren; produktiver Restore braucht geplanten Widerruf und Schlüsselwechsel.
Keine zentrale Sperrung oder zentraler Logout.

Testdienste gestoppt, Volumes/Schlüssel erhalten. Eigene gestoppte alte
Testcontainer und Netze gezielt entfernt, um Docker-Subnetze freizugeben;
keine Bestandsvolumes oder fremden Dienste gelöscht. Vier weitere Appintegrationen
und vollständige Releaseabnahme bleiben offen.

Quell-/Integrationspaket im Plattformrepository: bb28c35;
[Commit-Rohbeleg](evidence/grundschultafel-work-package-commit.log).

## Release 0.1.1 (6. November 2026)

Auf dem echten Server fehlten Bildergalerie und YouTube-Suche: Die Plattform setzte beide fest auf
aus (`GALLERY_ORIGIN: ""`, `TAFEL_YOUTUBE_ENABLED: "0"`), und die Tafel konnte den API-Schlüssel nur
als Umgebungsvariable lesen. Commit `1519d40` liest ihn aus `YOUTUBE_API_KEY_FILE` (Fallback
`YOUTUBE_API_KEY`); fehlt er, antwortet die Suche 503 statt 500. Die Plattform stellt die
Galerie-Adresse über `gallery_origin` in `platform.toml` und den Schlüssel über
`./install.sh youtube-key` bereit; ohne beides bleibt alles aus.

Lokal im gebauten Runtime-Image (read-only, cap-drop ALL, echte Anmeldung mit Erstzugang und PIN)
geprüft: ohne Einstellungen beide 503; leere Schlüsseldatei 503; Testschlüssel erreicht Google
(Antwort 500 wegen ungültigem Schlüssel); Galerie mit `https://pix.foerster.rocks` liefert 24 Treffer
und Vorschaubilder. Mit einem echten YouTube-Schlüssel nicht geprüft.

## Release 0.1.2 (6. November 2026)

Eingebettete Videos zeigten auf dem Server „Fehler 153“ (Konfiguration des Videoplayers). Die
Plattform-Integration setzt `Referrer-Policy: no-referrer` für alle Antworten; YouTube verweigert
eingebettete Player ohne Referrer. Commit `79cbeba` gibt nur dem YouTube-iframe
`referrerPolicy="strict-origin-when-cross-origin"`: YouTube erhält die Origin der Tafel, keinen Pfad;
alle übrigen Anfragen bleiben bei `no-referrer`. In Chromium (Playwright 1.64.1) gegen das echte
YouTube geprüft: Seite mit `no-referrer` ohne Attribut → Fehler 153, mit Attribut → Video lädt.

## Release 0.1.3 (6. November 2026)

Übernimmt vier Commits vom Nutzer (`745df91`..`b1f5c6a`):
- Eingebettete Elemente wie Timer oder YouTube bleiben beim Speichern erhalten. Gespeichert wird zentral über einen einzigen Canvas-Commit. Fehler werden gemeldet, und große Bilder werden vor dem Speichern verkleinert.
- Zu große Notizbücher (über 20 MB) lehnt der Server mit 413 ab. Ein beschädigtes Notizbuch blendet in der Liste nicht mehr alle anderen aus. Für die Namen in der Liste liest der Server nur den Anfang jeder Datei.
- Sperren, die ein abgestürzter Prozess hinterlassen hat, werden übernommen. Das funktioniert auch, wenn der Neustart dieselbe PID hat (Instanz-ID) oder die Sperre älter als 30 s ist.
- Ist die Grenze von 10 Sitzungen erreicht, endet die älteste Sitzung, statt den Login abzuweisen. Beschädigte Sitzungsdateien blockieren den Login nicht mehr.
- Hochgeladene Handy-Bilder werden nach der Übernahme gelöscht. Was nach einem Tag nicht abgeholt ist, wird aufgeräumt.
- Login-Schutz: Prüfen und Zählen eines Versuchs passieren in einem gesperrten Schritt. Auf einem Gerät, auf dem sich das Konto schon angemeldet hat, gibt es einen eigenen Fehlerzähler. Grundlage ist das signierte Cookie `tafel_known` (365 Tage, enthält kein Sitzungsrecht, weil `decrypt` eine `sid` verlangt). Wer fremde PINs rät, sperrt die Lehrkraft dadurch nicht aus.

Tests im Test-Image (read-only, ohne Netz): 10/10. `prove_grundschultafel_standalone.py` mit dem neuen Runtime-Image ist grün, auch die Sperre nach fünf Fehlversuchen über einen Neustart hinweg.

## Release 0.1.4 (7. November 2026): Wörterbuch und Galerie-API v1

Enthält die Commits des Nutzers `8f7e01d`..`a3fa220` (Autosave, Vorlagen der Schule, Klassenlisten,
Mathe-Material, Blitzlesen und Silbenrutsche, Wörterbuch-Anbindung) und `fe927dd`:

- **Wörterbuch (B1):** `WOERTERBUCH_ORIGIN` kommt von der Plattform: eigenes gswb, wenn installiert,
  sonst leer; `woerterbuch_origin` in `[apps.grundschultafel]` überschreibt (`""` = aus). Die Tafel ruft
  gswb über dessen **öffentliche Adresse** auf; die App-Netze bleiben getrennt (kein gemeinsames Netz),
  die gswb-Lese-APIs sind ohnehin öffentlich. Medienpfade ohne kodierte oder gepunktete Segmente.
  Dabei gefunden: gswb lieferte `.webp` als `application/octet-stream` (Python-Slim ohne
  `/etc/mime.types`), die Tafel wies die Bilder mit 415 ab; behoben in gswb `7c46741` (0.1.1).
- **Galerie (B3):** `src/lib/gallery-client.cjs` nutzt nur noch `/api/v1/images` und `/api/v1/tags`
  (kein HTML-Auslesen, auch nicht als Rückfall), Bearer-Token aus `GALLERY_TOKEN_FILE`, nur die
  konfigurierte Origin, keine Redirects, 6 s, Größenlimits, Antworten geprüft. Der Bild-Proxy erlaubt nur
  `/media/thumbnails/…` und `/media/display/…` mit geprüftem Content-Type. Alle Galerie-Routen verlangen
  jetzt eine Anmeldung (vorher konnte jeder die Tafel als Proxy zur Galerie benutzen). Das Galerie-Fenster
  zeigt Schlagworte (als Filter), den Lizenzhinweis und blättert über `total_pages`. Bestehende Hefte mit
  Data-URLs bleiben unverändert gültig.

**Achtung beim Update des echten Servers:** Dort steht `gallery_origin = "https://pix.foerster.rocks"`.
Die alte Galerie hat keine API v1; mit Tafel 0.1.4 meldet die Galeriesuche dann „nicht erreichbar“, bis
pix.foerster.rocks durch die Plattform-Galerie ersetzt ist (Zeile entfernen = eigene Galerie).

Nachweise (lokal):

| Prüfung | Ergebnis |
| --- | --- |
| `node scripts/test-runtime.cjs` (auch im `tests`-Image, read-only, ohne Netz) | 11/11, neu: Galerie-Client mit Token, Paging, Feldprüfung, Redirect, HTML statt JSON, Übergröße, Proxy-Pfade, SVG, ohne Token |
| `tsc --noEmit`, `next build` | fehlerfrei |
| `prove_grundschultafel_standalone.py` (Anmeldung, Hefte, Handy-Upload, PIN-Sperre, Abmelden) | alle bestanden, kein Rückschritt |
| Verbund Tafel + private Galerie (Token, 88 Bilder) + gswb (5.814 Wörter) als Container, Browser per Playwright: `tafel-gallery-woerterbuch.json` | Wörterbuch: Filter, 2-Silben-Liste mit Bild, Bild `image/webp`, Ton `audio/mpeg`, anonym 401, Traversal 400; im Browser „Aus dem Wörterbuch …“ sichtbar und Liste geladen. Galerie: Suche, Blättern, Schlagworte, Vorschaubilder (36/36 geladen), Lizenzhinweis, Filter per Schlagwort; Proxy weist `/static/…`, `../`, `/media/uploads/…` und fremde Hosts ab; Galerie direkt ohne/mit falschem Token 401. Bild eingefügt, Autosave: Heft enthält `data:image/…`, keine Galerie-URL. Ohne Galerie/Wörterbuch: 503, Knopf fehlt, Readiness 200 |

Nicht geprüft: YouTube-Suche mit echtem Schlüssel (unverändert), Abnahme auf dem echten Server.
