# schuleva

Prüfdatum: 2026-11-01T10:12:20.458771+00:00; Branch `main`; vollständiger Commit `71c4917ad71880eec7f2cdb415453284e3b70ee5`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Python; FastAPI 0.115.0/Uvicorn 0.30.6; Jinja; bcrypt; matplotlib/WeasyPrint.
- **Dienste:** SQLite mit WAL; schema-/additive Migrationen in app/db.py.
- **Produktionsbetrieb:** systemd und nginx-Vorlage; kein Dockerfile. SECRET_KEY fällt auf bekannten Platzhalter zurück; Produktionsstart muss fehlenden Secret ablehnen.
- **Frontend/Reproduzierbarkeit/Plattform:** requirements teils exakt, WeasyPrint offen; kein vollständiger transitive Lock. TAN-Verbrauch und response-Schreiben sind getrennte Aufrufe: Fehler/Parallelität zwischen beiden testen.
- **Persistenz/Migration:** SQLite, Fragebogendefinitionen in surveys/, Klassen-/Befragungsantworten; anonymisierte Stundenzeitstempel.
- **Externe Abhängigkeiten/Self-Hosting:** Lokal betreibbarer Kern; Fonts/Assets-Lizenzen vor Distribution klären.
- **Schwere Verarbeitung:** Matplotlib-Grafiken und WeasyPrint-PDF-Berichte/TAN-Bögen.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** bcrypt-Passwörter, signierte Starlette-Session mit user_id, Rollen schulleitung/lehrer und CSRF; TAN-/Freigabetoken für Befragung und Ergebnisfreigaben.
- **Öffentliche/alternative Zugänge:** /start, /befragung, /api/tan/check und /api/submit bleiben TAN-geschützt zugänglich; Freigabelinks gesondert schützen.
- **Mail/Konfiguration:** Keine SMTP-Bibliothek/Versandstelle im geprüften app-Code gefunden.
- **Hauptbefund:** Einmal-TAN ist fachliche Autorisierung, kein zentraler Lehrerlogin. Public-Rate-Limiter ist pro Prozess und vertraut direkt X-Forwarded-For; Proxygrenze härten.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Python/Pango-Image und Health; eindeutiger Secret-Zwang, abhängige Pakete sperren. |
| Domainwechsel | kleine Anpassung | 1–3 | Basis-URL-Konfiguration ergänzen; PDF-QR-/Ergebnislinks und vertrauenswürdige Proxyheader prüfen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Zentrale IdP-Einladung; App-Mail nicht erforderlich. |
| SSO | größerer Umbau | 5–9 | OIDC für administrative Sessions ergänzen; Rollen/ShareGrants und TAN-Routen erhalten. |
| Benutzermigration | kleine Anpassung | 2–4 | Lokale users.id und Eigentümer/Ergebnisfreigaben mappen; Kinder/TAN nicht als Personenkonten importieren. |
| Backup/Restore | kleine Anpassung | 2–4 | SQLite-Backup-API plus surveys/ und Konfiguration; TAN/Antwort-Atomarität als Abnahmetest aufnehmen. |

Summe appbezogen: **12–24.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [requirements.txt:1–13](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/requirements.txt#L1-L13)
- [app/main.py:1–65](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L1-L65)
- [app/auth.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L1-L70)
- [app/db.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L1-L70)
- [app/routes/public.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/public.py#L1-L70)
- [app/routes/admin.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L1-L70)
- [app/routes/export.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L1-L70)
- [app/services/tan.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/services/tan.py#L1-L70)
- [app/services/pdf_report.py:1–70](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/services/pdf_report.py#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `app/main.py`: [L11](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L11), [L24](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L24), [L26](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L26), [L56](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L56), [L57](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L57), [L59](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L59), [L63](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/main.py#L63)
- `app/auth.py`: [L21](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L21), [L25](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L25), [L59](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L59), [L65](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L65), [L86](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L86), [L108](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L108), [L131](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L131), [L133](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L133), [L138](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L138), [L143](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L143), [L156](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L156), [L161](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/auth.py#L161)
- `app/db.py`: [L6](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L6), [L9](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L9), [L19](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L19), [L20](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L20), [L21](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L21), [L82](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L82), [L98](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L98), [L101](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L101), [L110](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L110), [L111](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L111), [L112](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/db.py#L112)
- `app/routes/admin.py`: [L14](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L14), [L85](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L85), [L110](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L110), [L128](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L128), [L185](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L185), [L307](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L307), [L418](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L418), [L456](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L456), [L494](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L494), [L553](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L553), [L715](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L715), [L818](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/admin.py#L818)
- `app/routes/export.py`: [L235](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L235), [L238](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L238), [L240](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L240), [L273](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L273), [L276](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L276), [L278](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/routes/export.py#L278)
- `app/services/tan.py`: [L60](https://github.com/Bingenberger/schuleva/blob/71c4917ad71880eec7f2cdb415453284e3b70ee5/app/services/tan.py#L60)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
