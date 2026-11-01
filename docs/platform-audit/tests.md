# Ausgeführte und offene Prüfungen

Alle Repositoryversionen in [repositories.json](evidence/repositories.json), Zugriff-/Anweisungsprüfung in [access-checks.txt](evidence/access-checks.txt). Keine vorhandenen Produktivcontainer, Datenbanken, DNS-Einträge oder Konten verändert. Neu angelegte Container eindeutig `schulplattform-audit-*`, nur synthetische Daten.

| Prüfung | Ergebnis / Beleg | Aussagegrenze |
| --- | --- | --- |
| 14 isolierte Gitcheckouts und Sourceprüfung | 14/14, SHA/Branch/Datum vorhanden; source-inventory.json | Kein Build aller Apps |
| Python-Syntax über gelesene Bäume | 644 Dateien, 0 Syntaxfehler; python-syntax.json | Keine Ausführung/Typ-/Sicherheitsgarantie |
| Schulwissen frozen UV-Installation Python3.12 | erfolgreich; schulwissen-install.log | Kein vollständiger Dockerimage-Build |
| Schulwissen Produktions-collectstatic | erfolgreich, 147 kopiert/735 nachbearbeitet; schulwissen-collectstatic.log | Frontend-npm-Editor nicht neu gebaut |
| Schulwissen tests/test_phase4.py, isoliertes PG16 | 24 bestanden in 12,32 s; schulwissen-tests.log | Signierte RSA-IDtokens mit simulierten Providerrequests, kein Mehr-App-SSO aus diesen Tests allein |
| Schulhelfer Bestandstests | 52 bestanden in 13,71 s; schulhelfer-tests.log | SMTP absichtlich 127.0.0.1:1, kein Sinknachweis aus dieser Suite, keine konkurrierende Last |
| Schulanmeldung unittest discover | 445 Tests, 444 ohne Fehler, ein TOTP-Testfehler; schulanmeldung-tests.log | Gesamtlauf nicht grün; einzelne Bibliothekswarnings/absichtlich injizierte Fehlertracebacks sind keine zusätzlichen Testfehler |
| Schulanmeldung TOTP-Einzelwiederholung | 1 bestanden; schulanmeldung-totp-rerun.log | Zeitfensterabhängigkeit vermutet, nicht abschließend bewiesen |
| TOTP-Replaytest mit konstanter Zeit im selben Schritt | 1 bestanden; schulanmeldung-totp-fixed-time.log | Lokaler deterministischer Wrapper, keine Änderung am Appcode; kein allgemeiner MFA-Audit |
| gswb öffentliche Redaktionsänderung | Anonymer POST /review/audit/approve 302 und JSON tatsächlich geändert; gswb-checks.log | Bestätigter Schutzbedarf, ausschließlich künstlicher Eintrag |
| gswb SQLite-Backup/Restore/Reinit | 1.000 Wörter, integrity_check ok, zweimal Init ohne Verlust | Nur DB, keine Medien-/IdP-/Keywiederherstellung |
| gswb Gunicorn-Smoke mit 10 VUs | 298 Requests/30 s, 0 Fehler, p95 8,416 ms | Keine Plattformkapazität; gleiches Gerät/tmpfs, kurze Leselast |
| Zackboing npm ci ohne Installskripte | erfolgreich; zackboing-install.log | Native Binding fehlt deshalb zunächst absichtlich |
| Zackboing native Aktivierung/Start | nicht erfolgreich; native-build*.log / server.log | npm12 verlangt spezifische Scriptfreigabe; danach Node26 ohne Prebuilt und node-gyp-Cache außerhalb erlaubter Schreibpfade. Zweiter CLIversuch mit devdir/nodedir von npm12 abgelehnt. Kein Beleg für generelle Appinkompatibilität; Node-LTS-Containerbuild offen |
| Echter lokaler OIDC-Browserteilstack | A→synthetischer RP B SSO, B verweigert unberechtigte API, öffentliche Route, IDtokenablauf; prototype-browser.log | Kein zweiter realer Schulappadapter; IdP H2/start-dev; siehe neun Punkte im Prototype |
| IdP-Logout vs. lokale A-Session | IdP verlangt danach wieder Passwort, A liefert weiter 200; prototype-logout-confirmed.log | Globale Logout-/Sperrfrist **nicht erfüllt**, als Integrationslücke dokumentiert |
| SMTP → lokaler Mailpit | Django akzeptiert eine Mail, Sink total=1; prototype-mail*.json/log | Direkt in Sink, kein konfiguriertes Postfix-Relay/Retry-/Senderpolicy-Nachweis |
| Synthetischer Schulwissen PGrestore | pg_dump -Fc→leere audit_restore, gleiche Nutzer/Dokument/Mapping/Besitz/Gruppen; prototype-pg-restore.log | DBteilrestore, keine vollständige Plattform oder RTOmessung |
| PG-Neustart und wiederholtes Init | Datensätze bleiben; prototype-reinit.log / restart-proof.json | Kein vollständiger IdP-/Alle-App-Neustart |
| Kurze Infrastrukturressourcenstichprobe | prototype-resources*.jsonl/json | Nur vier Testdienste, keine gemeinsame 14-App-Grundlast oder 60-min-Speicherprüfung |

## Wesentliche nicht ausgeführte Prüfungen

Produktionsbuilds der übrigen Apps, komplette frontend-/native-/ARM64-Buildmatrix, Ziel-OS-Ubuntu-Lauf, gesamter 14-App-Start, vollständige Lizenz-/SBOMprüfung aller Images, vollständige Appfach-/API-/Header-/CSRF-/CORS-Negativabnahme, interaktive Migrationsoberfläche, Domainwechsel/Callbackrollback, echte Mitarbeiterrevokation innerhalb von 60 Sekunden, lokale/IdP-/Backchannel-Logoutmatrix für alle Apps, Relayauth/Absenderbindung/Retry/Rate-Limit, allumfassender verschlüsselter Offsitebackup-/leerer IdP-/Datei-/Schlüsselrestore und RPO/RTO.

Lastszenarien Leerlauf aller Apps, 10-Personen-Appmix, 30/120/250 aktive Personen, Loginburst/Tokenrefresh, konkurrierende Finanz-/Buchungs-/TANschreibvorgänge, WS-/Broadcastlast, PDF-/Office-/Import-/Backupkonkurrenz und 60-min-Dauerlauf **nicht ausgeführt**. Grund: heterogene Appadapter/Produktionsimages/Testfixtures nicht fertig, geteilter Host statt repräsentativem Zielserver. Keine fehlenden Messwerte durch Schätzwerte ersetzt. Das Benchmarkpaket ist ausführbare Grundlage mit ausdrücklich benannten noch fehlenden Fachadaptern.

## Reproduktion der wichtigsten Appchecks

```bash
# Im jeweiligen isolierten Checkout, Sourcepfade siehe checkout.py:
SW_DEBUG=true \
SW_DATABASE_URL=postgresql://postgres:audit-local-only@127.0.0.1:25432/audit \
.venv/bin/python -m pytest tests/test_phase4.py -q
# Schulhelfer, in eigener Testvenv mit requirements + pytest/httpx:
python -m pytest tests -q
# Schulanmeldung mit exakt requirements.txt, Testmodus/Mails unterdrückt:
SL_OFFICE_ENV=testing python -m unittest discover -s tests -t . -q
```

Auf Testkonfiguration und künstliche Daten achten; Schulanmeldung-Tests verwenden In-memory-DB und MAIL_SUPPRESS_SEND, Schulhelfer nutzt die frische Checkout-test.db. Keine Tests in produktiven Arbeitskopien ausführen. Die finalen Testpaketversionen und Image-Digests sind separat aufgezeichnet; unterschiedliche Apps für dauerhafte Reproduktion in getrennte Venvs/Container setzen.
