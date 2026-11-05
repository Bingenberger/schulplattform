# Fundkiste – Plattform-Integration

Stand: 5. November 2026. Quelle: bisher nur lokal; neues öffentliches Repository
`Bingenberger/fundkiste` (nur Code, keine Daten).

| Commit | Inhalt |
| --- | --- |
| `c93781b` | Erstimport, unveränderter Stand vor der Plattform (Basis) |
| `4d90f2e` | Plattform-Integration (getesteter Stand, `patches/fundkiste/changes.patch`) |
| `08d222d` | verwalteter Release-Workflow (einziger Unterschied zum getesteten Stand) |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| App-Tests (pytest, lokal und im `tests`-Image, schreibgeschützt, ohne Netz) | 8/8 bestanden |
| Image `final`: UID 10001, read-only, ohne Capabilities; Migration zweimal, Start, `/health/ready` | 200, Migration wiederholbar |
| Plattform-Override + App-Compose mit Docker Compose v2.40.3: Migrationsjob, `up --wait`, Proxy-Alias | healthy, kein veröffentlichter Port, Checks 200/404 |
| Kopie der echten Altdatenbank (user_version 0) | übernommen, Zeilen gleich, Team-Schlüssel unverändert |
| Export-Werkzeug: Team-Schlüssel aus `Environment=` der Unit → `data/team_key.txt` | im Archiv, Datenbank als SQLite-Kopie |

Nicht geprüft: Import auf einem echten Plattform-Server, Release-Image aus GitHub Actions
(Repository muss angelegt werden), VM-Gesamtabnahme.

## Verhalten, das gleich bleibt

Eltern sehen Fundstücke und offene Suchanzeigen **einschließlich der freiwilligen
Kontaktangabe** und Abholmeldungen mit Namen (wie bisher). Wer die Team-URL kennt,
kann alles anlegen und löschen; es gibt keine persönlichen Konten.
