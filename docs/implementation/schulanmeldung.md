# Schulanmeldung (SL-Office) – Plattform-Integration

Stand: 5. November 2026. Repository `Bingenberger/schulanmeldung` (**privat**), Basis `b6b6c3d` (= GitHub `main`).

| Commit | Inhalt |
| --- | --- |
| `b6b6c3d` | Ausgangsstand |
| `5dcc86a` | Plattform-Integration (getestet, `patches/schulanmeldung/changes.patch`) |
| `fbe5993` | verwalteter Release-Workflow |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| 445 vorhandene + 5 neue Tests (unittest), lokal und im `tests`-Image (read-only, ohne Netz) | 450/450 |
| Image `final`: Schriften vorhanden (`check-schriften`), Unterschrift nicht enthalten | ok |
| Plattform-Override + App-Compose (Compose v2.40.3): `db upgrade` (18 Revisionen), app + worker | beide healthy; `/login` 200, `/` 302, `/eltern/` 200 |
| Erinnerungslauf und Worker-Schleife im Container | läuft, Herzschlag geschrieben |
| Export-Werkzeug (nachgebauter Altbestand) | Datenbank- und Uploadpfad aus `.env`, Unterschrift → `data/briefkopf/` |

Nicht geprüft: Mailversand über das Plattform-Relay mit echtem Anbieter, Import auf einem echten
Server, Release-Image aus GitHub Actions (setzt öffentliches Repository oder öffentliches GHCR-Paket voraus).

## Hinweise

- Das Repository ist privat. Die Plattform lädt Images ohne Anmeldung; vor dem Release das
  Repository oder das Paket `schulanmeldung` auf GHCR öffentlich stellen.
- `assets/briefkopf/FrenteH1-Regular.ttf` ist laut Asset-README aus einer systemweit installierten
  Schrift erzeugt; die Lizenz für die Weitergabe im öffentlichen Image gehört in die Prüfung A0.
- `SL_OFFICE_SECRET_KEY` muss beim Umzug nicht mit: TOTP-Geheimnisse liegen unverschlüsselt in der
  Datenbank, Eltern-Zugangstoken als SHA-256. Alle melden sich einmal neu an.
- Bestandsdatenbanken müssen einen Alembic-Stand haben (`docs/DATENBANKMIGRATIONEN.md`: Baseline
  `ed2b53c79584`); der Altserver aktualisiert per `db upgrade` beim Deploy.
