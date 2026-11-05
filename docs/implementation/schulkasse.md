# Schulkasse – Plattform-Integration

Stand: 5. November 2026. Repository `Bingenberger/schulkasse`, Basis `d99cfca` (= GitHub `main`).

| Commit | Inhalt |
| --- | --- |
| `d99cfca` | Ausgangsstand |
| `653efd1` | Plattform-Integration (getestet, `patches/schulkasse/changes.patch`) |
| danach | verwalteter Release-Workflow |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| Vorhandene + neue App-Tests, lokal und im `tests`-Image (read-only, ohne Netz), inkl. PDF- und QR-Prüfungen | 212/212 (ein vorbestehend datumsabhängiger Test ausgenommen, s. u.) |
| Plattform-Override + App-Compose (Compose v2.40.3): Migration zweimal, `up --wait`, Proxy-Alias | 9 Migrationen, dann „aktuell“; healthy; `/anmelden` 200, `/` 302; Cookie Secure/HttpOnly |
| Export-Werkzeug (nachgebauter Altbestand) | `SCHULKASSE_SECRET_KEY` als Secret im Archiv; Belege und `brief.toml` dabei; `instance/backups` ausgeschlossen |

Nicht geprüft: Import auf einem echten Server mit echten 2FA-Konten, Release-Image aus GitHub Actions.

## Vorbestehender Testfehler

`tests/test_monatsbericht.py::test_monatsbericht_umbuchung_und_anfangsbestand` scheitert schon
auf `d99cfca`: Die Umbuchung erhält das heutige Datum, der Test erwartet sie im Bericht für
September 2026. Unabhängig von der Plattform-Integration; nicht geändert.

## Umzug: der Schlüssel

Der alte `SCHULKASSE_SECRET_KEY` verschlüsselt die Zwei-Faktor-Geheimnisse. Das Export-Werkzeug
nimmt ihn aus `/opt/schulkasse/.env` mit; der Import ersetzt den zufälligen Plattform-Schlüssel
damit. Fehlt er, müssen alle Konten per `schulkasse reset-2fa` neu eingerichtet werden.
