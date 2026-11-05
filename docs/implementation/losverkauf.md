# Losverkauf: fünfter lokaler Pilotdienst

Beobachtet am 3. November 2026. Appcommit und Patch stehen in
[patches/index.json](../../patches/index.json). Keine Produktionsfreigabe.

## Implementiert

- Eigenständige Compose-Datei mit ergänzendem Plattform-Override. Python 3.12.12,
  Flask 3.1.3, Gunicorn 26.2.0 und ReportLab 5.1.0, Hash-Lockfiles und
  fixiertes Basisimage. Nur amd64 geprüft.
- UID:GID 10001:10001, Init, Read-only-Root, tmpfs 64 MiB,
  gesetzte Grenzen 384 MiB/1 CPU/128 Prozesse.
  Ein Webprozess mit vier HTTP-Threads, ein Maildispatcher und ein PDF-Slot.
- Pflicht-Session- und Elterntoken. Kein tokenloser Entwicklungszugang.
  Persönlicher Verwaltungsname mit Passwort-Hashdatei; bestehende Env-Namen
  bleiben möglich. Lokale Terminaleinrichtung ersetzt keine bestehenden Schlüssel.
- Explizite SQLite-Migration mit Lock, BEGIN IMMEDIATE und Fremdschlüsselprüfung.
  Kein DDL im Import oder Webrequest. Bekannte Legacy-Anmeldungen behalten
  IDs und edit_tokens; unbekannte Bestandsfelder blockieren die Konvertierung.
- CSRF für Verwaltungsformulare, Login, Logout und JSON-/DELETE-Schreibpfade.
  Logout ist POST; PDF-Personenwerte werden maskiert.
- Dauerhafte Eingangs-Mailqueue: atomar mit der Anmeldung, maximal 200 offene
  Aufträge, ein Dispatcher, begrenzte Wiederholungen und Wiederaufnahme von
  sending-Aufträgen nach Neustart. Keine unbeschränkten Hintergrundthreads.
- BASE_URL zur Laufzeit, explizite Proxy-IP-Adressen und sichere Cookies bei HTTPS.
  Individuelle Mail-Links nehmen mit bestehendem edit_token den gleichen Besitz
  in einem neuen Browser beziehungsweise auf der neuen Domain wieder auf.
- Leaflet 1.9.4 lokal samt BSD-2-Clause-Lizenz und geprüftem Dateiinventar.
  Keine CDN-Anfrage und standardmäßig keine externen Hintergrundkacheln.
  Reale Schulbezirke, PDF-Vorlagen und Kontaktdaten sind nicht im Image.

## Ausgeführt

| Prüfung | Beobachtetes Ergebnis |
| --- | --- |
| Isolierter Laufzeit-/Sicherheitstest | 16 bestanden, ohne Netzwerk |
| Standalone ohne Plattform-Override | Migration, Token-Gate, persönlicher Admin, CSRF, PDF/CSV, lokale Assets und Sink-Zustellung bestanden |
| Parallele Anmeldung | 8 gleichzeitige HTTP-Anmeldungen auf 1 freien Platz: 1 Zusage und 7 fachliche 409 |
| SMTP-Ausfall/Neustart | Sink pausiert, Readiness weiterhin 200; vorgemerkter Auftrag überlebt Appneustart, danach alle 3 Aufträge abgeschlossen |
| Lokaler kombinierter Restore | Neues leeres Volume, SQLite-.backup plus maps/mails, App ohne Migration/Setup gestartet; gleiche IDs, Tokens, Queue, Mailprotokolle, Karte und private Maildatei |
| Domaintransaktion | Lokales TLS, Login, persönlicher Elternzugang und Mail-URL auf neuer Domain; erzwungener Prüffehler mit automatischem Rückfall |
| Lebenszyklus | Zwei No-op-Installationsläufe; gleiche Container/Schlüssel/Checkpoints; Stop mit 503-Wartungsroute und Start ohne Migration |
| Dashboard | Neu gebaut und erneut über TLS/Unix-Steuerdienst geprüft; explizite Rechteprojektion für Losverkauf per Python-Test |

Rohbelege: [Image/Versionen](evidence/losverkauf-image.json),
[Build](evidence/losverkauf-build-final.log),
[Laufzeittests](evidence/losverkauf-runtime.log),
[JavaScript-Syntax ohne Browserausführung](evidence/losverkauf-javascript-syntax.log),
[Standalone](evidence/losverkauf-standalone.json),
[Standalonekommandos](evidence/losverkauf-standalone-operations.json),
[Restore](evidence/losverkauf-restore.json),
[Restorekommandos](evidence/losverkauf-restore-operations.json),
[Domain/Lifecycle](evidence/losverkauf-platform.json),
[Pilotkommandos](evidence/pilot-v10-operations.jsonl),
[Lokale Erstkonfiguration und Leaflet-Inventar](evidence/losverkauf-local-setup.json).

Die acht Anmeldungen prüfen Platzgrenzen, keine Kapazität oder Latenz.
Bildgrößen sind Docker-Metadaten, keine RAM-/SSD-Empfehlung.

## Wiederholung

```sh
.venv/bin/python scripts/build_losverkauf.py
.venv/bin/python scripts/check_losverkauf_runtime.py
.venv/bin/python scripts/verify_losverkauf_standalone.py
.venv/bin/python scripts/verify_losverkauf_restore.py
./install.sh pilot-up --state-dir .work/pilot-v10 --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf
.venv/bin/python scripts/verify_losverkauf_platform.py
```

Der Restoretreiber verwendet die zuletzt erfolgreich erzeugte private
Standalonefixture. Der Plattformtreiber richtet ausschließlich eine separate
synthetische persönliche Adminprojektion ein; die Plattform liefert kein
Standardkonto. Eltern- und Bearbeitungstokens gelangen nicht in Berichte oder argv.

Ein vorheriger Pilot wurde nach dem zusätzlichen Legacy-Negativtest durch eine
neue Testgeneration mit neu gebundenem Image ersetzt. Der Installationsplan
wurde nicht zurückgesetzt oder auf einen anderen Build umgeschrieben.
Zwischen den Testgenerationen mussten ausschließlich eigene gestoppte Container
und Netzwerke freigegeben werden, weil Dockers Adresspools erschöpft waren.
Volumes und Schlüssel blieben erhalten; kein globales Prune und kein down -v.

## Grenzen

- Die Queue sichert Eingangsbestätigungen. Vorhandene Admin-Mailaktionen sind
  teilweise synchron. Keine appübergreifende persistente Relayqueue.
  Nach SMTP-Annahme und Absturz vor lokalem Abschluss kann eine Mail doppelt
  ankommen; keine Exactly-once-Zusage.
- Fünf gescheiterte Versuche enden im Fehlerstatus. Aufbewahrung, Alarmierung
  und eine zentrale Queue-/Retry-Oberfläche sind noch offen.
- Der Restore verwendet die ursprünglichen Konfigurations-/Schlüsseldateien.
  Kein verschlüsseltes Offsite-/Secretstore-Gesamtbackup.
- Keine automatische Cookieübertragung zwischen Hosts. Individuelle Maillinks
  ermöglichen denselben Besitz; keine zentrale Sitzungssperrung oder Revokation.
- Der geprüfte Domainflow verwendet eine lokale CA; keine öffentliche
  DNS-/Besitz-/ACME-Abnahme. Keine QR-/WebSocket-/OIDC-Funktion in diesem Appflow.
- Browserautomation und tatsächliche Karteninteraktion sind nicht ausgeführt.
  Straßen und Hintergrundkacheln müssen als eigene Datenbestände mit
  Freigabe-/Nutzungsnachweis bereitgestellt werden. Der optionale Overpass-Import
  wurde nicht ausgeführt.
- Historische native Serverautomationen sind für den neuen Vertrag noch nicht
  abgenommen. Keine produktiven Dienste, echten Benutzerkonten, DNSdaten oder
  realen E-Mail-Zustellungen verändert.
- Projektlizenz, vollständige SBOM, Registry-Veröffentlichung, Ubuntu-Zielserver,
  ARM64 und Last-/Dauerlauf bleiben offen. Fünf weitere Apps fehlen.

Alle Testdienste sind gestoppt; lokale synthetische Daten und Archive bleiben erhalten.

## Release 0.1.1 (5. November 2026)

Auf dem echten Server lehnte losverkauf 0.1.0 die Admin-Anmeldung mit 403 ab. Die App sendete
`Referrer-Policy: no-referrer`. Bei dieser Policy schicken Browser beim Absenden eines Formulars
`Origin: null`, und die Herkunftsprüfung wies jede Admin-Formularsendung ab. Die Tests mit dem
Flask-Testclient und `curl` setzten nie einen Browser-Origin. Darum blieb der Fehler unbemerkt.
Ausdrücklich steht das auch oben unter „Browserautomation … nicht ausgeführt“.

Commit `b40e06d` stellt auf `same-origin`. Gleichursprüngliche Formulare tragen damit die echte
Herkunft, fremde Ziele erhalten keinen Referrer, und der Elterntoken in der URL bleibt geschützt.
Ein neuer Test sendet das Login-Formular wie ein Browser, einmal mit echtem und einmal mit
`null`-Origin.

Die übrigen Apps mit Herkunftsprüfung (abgen, leseflux, grundschultafel, zackboing,
kompetenz-manager) senden ihre Formulare per `fetch` oder setzen keine `no-referrer`-Policy und
sind darum nicht betroffen.
