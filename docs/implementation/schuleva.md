# Schulbefragung (schuleva) – Plattform-Integration

Stand: 5. November 2026. Repository `Bingenberger/schuleva`, Basis `71c4917` (= GitHub `main`).

| Commit | Inhalt |
| --- | --- |
| `71c4917` | Ausgangsstand |
| `a5c4608` | Plattform-Integration (getestet, `patches/schuleva/changes.patch`) |
| danach | verwalteter Release-Workflow (einziger Unterschied zum getesteten Stand) |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| App-Tests (17 vorhandene + 10 neue), lokal und im `tests`-Image (read-only, ohne Netz) | 27/27 |
| Auswertungs-PDF (53 Fragen, Diagramme) und TAN-Bogen im read-only-Container, UID 10001 | erzeugt; Liberation Sans/DejaVu eingebettet; Domain aus BASE_URL |
| Plattform-Override + App-Compose (Compose v2.40.3): Migrationsjob, `up --wait`, Proxy-Alias | healthy; `/admin/login` 200, `/admin/users` 303; WebSocket erreicht die App (unbekannte Sitzung → 403) |
| Export-Werkzeug (nachgebauter Altbestand) | `surveys/` → `data/surveys`, `data/backups/` ausgeschlossen, eine Datenbank |

Nicht geprüft: vollständiger geführter Modus mit angemeldeter Lehrkraft hinter Caddy,
Import auf einem echten Server, Release-Image aus GitHub Actions.

## Hinweise

- Sitzungen bleiben beim Umzug nicht erhalten (neuer Schlüssel); Konten, Befragungen,
  Antworten und Freigabelinks schon.
- Die Brute-Force-Sperre zählt jetzt je Client (X-Forwarded-For nur vom Proxy) statt
  für alle gemeinsam.
