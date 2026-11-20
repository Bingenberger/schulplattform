# Schulkasse – Plattform-Integration

Stand: 5. November 2026 (Release 0.2.0: 20. November 2026). Repository `Bingenberger/schulkasse`, Basis `d99cfca` (= GitHub `main`).

| Commit | Inhalt |
| --- | --- |
| `d99cfca` | Ausgangsstand |
| `653efd1` | Plattform-Integration (getestet, `patches/schulkasse/changes.patch`) |
| `725eebb` | verwalteter Release-Workflow |
| `64d9f10` | Test Monatsbericht mit festem Buchungszeitpunkt (getesteter Release-Stand) |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| Vorhandene + neue App-Tests, lokal und im `tests`-Image (read-only, ohne Netz), inkl. PDF- und QR-Prüfungen | 213/213 |
| Plattform-Override + App-Compose (Compose v2.40.3): Migration zweimal, `up --wait`, Proxy-Alias | 9 Migrationen, dann „aktuell“; healthy; `/anmelden` 200, `/` 302; Cookie Secure/HttpOnly |
| Export-Werkzeug (nachgebauter Altbestand) | `SCHULKASSE_SECRET_KEY` als Secret im Archiv; Belege und `brief.toml` dabei; `instance/backups` ausgeschlossen |

Nicht geprüft: Import auf einem echten Server mit echten 2FA-Konten, Release-Image aus GitHub Actions.

## Behobener Testfehler

`tests/test_monatsbericht.py::test_monatsbericht_umbuchung_und_anfangsbestand` scheiterte schon
auf `d99cfca`: Die Umbuchung erhielt das heutige Datum, der Test erwartete sie im Bericht für
September 2026. Der Test setzt den Buchungszeitpunkt jetzt fest; die App bleibt unverändert.

## Umzug: der Schlüssel

Der alte `SCHULKASSE_SECRET_KEY` verschlüsselt die Zwei-Faktor-Geheimnisse. Das Export-Werkzeug
nimmt ihn aus `/opt/schulkasse/.env` mit; der Import ersetzt den zufälligen Plattform-Schlüssel
damit. Fehlt er, müssen alle Konten per `schulkasse reset-2fa` neu eingerichtet werden.

## Release 0.2.0 (20. November 2026, Plattform-Release 0.3.4)

Übernimmt den Nutzer-PR #1 „Richtlinie Schulgirokonten“ (`c64d244`, gemergt als `3d05a05`, Tag `v0.2.0`):
Kontoauszüge mit Überwachungslisten nach § 8 (Seite, PDF im Layout der Anlage 1, Excel über `openpyxl`),
Prüfvermerk mit Änderungserkennung, Anmerkung je Umsatz, Jahresendmitteilung nach § 9, Erinnerungszettel
(A7/A6), Klassenlisten für die Klassenleitungen und ein neues Design mit lokal ausgelieferten Phosphor-Icons
(MIT, kein CDN). Migration 0010 legt `kontoauszug` und `umsatz_anmerkung` an und ergänzt die leere Spalte
`konto.geldinstitut`. Readiness prüft wie bisher „alle Migrationen angewendet“; auf Plattform-Seite ändert
sich nichts. Schulanschrift (Briefvorlage) und Geldinstitut (Konto) stellt man in der App ein.

`patches/schulkasse/changes.patch` enthält die drei Integrations-Commits und den Merge als Diff gegen den
ersten Elternteil. Anwenden mit `git am --keep-cr` (die Phosphor-Lizenz hat CRLF-Zeilenenden); das Ergebnis
ist baumgleich mit `3d05a05`.

| Prüfung | Ergebnis |
| --- | --- |
| App-Tests im `tests`-Image (read-only, ohne Netz) | 226/226 |
| Update mit Bestand: DB mit Image 0.1.0 (Admin, Demo, 2 CAMT-Importe), dann `migrate` mit 0.2.0 | 0009 → 0010, zweiter Lauf „aktuell“; 249 Zeilen in 26 Tabellen unverändert (nur neue leere Spalte), `integrity_check` ok |
| Start nach Update | `/health/ready` 200, `/anmelden` 200, Phosphor-CSS/-Font 200 |
| Plattform-Tests | 232 bestanden |
| VM-Update 0.3.3 → 0.3.4 mit Bestand ([Log](evidence/schulkasse-vm-0.3.4.log)) | 0009 → 0010, 249 Zeilen unverändert; HTTPS, Überwachungsliste PDF/XLSX, Prüfvermerk mit Saldenkontrolle, Jahresendmitteilung, Klassenlisten, Erinnerungszettel, Backup |

Nicht geprüft: Anmeldung mit echtem TOTP im Browser, echte Bankdaten, Abnahme auf dem echten Server.
