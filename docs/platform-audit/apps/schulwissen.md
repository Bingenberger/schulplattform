# schulwissen

Prüfdatum: 2026-11-01T10:12:33.484145+00:00; Branch `main`; vollständiger Commit `a9673bc343a3a6eea1c15f533d0e89061e669b32`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Python 3.12; Django 5.2; Gunicorn; Tiptap-Build.
- **Dienste:** PostgreSQL 16 mit pg_trgm/GIN und Volltext; optional Nextcloud-Index-Timer.
- **Produktionsbetrieb:** Dockerfile und Compose vorhanden, interner Port 8000; docker/start.sh führt migrate und rollen_einrichten aus; drei Gunicorn-Worker als Vorgabe. Image verwendet latest und uv-Installation ungepinnt: Release-Härtung nötig.
- **Frontend/Reproduzierbarkeit/Plattform:** UV-Lock vorhanden; frontend/package-lock prüfen. serverseitiges HTML, statische Dateien über WhiteNoise; kein WS-/Offline-Pfad im geprüften Kern belegt.
- **Persistenz/Migration:** PostgreSQL, /medien, versionierte Anhänge, Arbeitspläne und Gruppen; Migrationen in kern/fachdaten/deutsch.
- **Externe Abhängigkeiten/Self-Hosting:** Nextcloud WebDAV/Index optional; gehosteter Dienst ist für den Kern nicht erforderlich.
- **Schwere Verarbeitung:** WeasyPrint-PDF, Office/PDF-Textgewinnung, Excel/JSON-Import; Suchindex in PostgreSQL, kein separater Suchserver erforderlich.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Django-Nutzer mit E-Mail als Login, Gruppen/Fachrechten; Passwort-Reset; Authlib-OIDC mit PKCE S256, State/Nonce und expliziter issuer/sub-Verknüpfung vorhanden.
- **Öffentliche/alternative Zugänge:** Lokaler Login, Passwort-Reset und OIDC-Callback; fachliche Ansichten und Django-Admin getrennt prüfen.
- **Mail/Konfiguration:** Django SMTP: SW_SMTP_HOST/PORT/NUTZER/PASSWORT/TLS und SW_ABSENDER; sonst Konsolenausgabe.
- **Hauptbefund:** Geeigneter Pilot: einzig im Code gefundene ausgearbeitete OIDC-Kontoverknüpfung. Vorhandene Tests beweisen noch keinen Keycloak-/Mehr-App-Browserablauf.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 1–2 | Image nach Commit bauen und per Digest referenzieren; Health-/Readiness-Endpunkte ergänzen; Startmigration vom normalen Neustart trennen. |
| Domainwechsel | kleine Anpassung | 1–2 | SW_OEFFENTLICHE_URL, SW_ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS und exakte /anmelden/nextcloud/callback-URI gemeinsam umstellen. |
| Zentraler Mailversand | kleine Anpassung | 0.5–1 | SW_SMTP_* auf internes Relay setzen, Test-Reset nur an Mail-Sink. |
| SSO | kleine Anpassung | 3–6 | OIDC-Anbieterbezeichnung verallgemeinern; Appfreigabe vor Sessionerstellung und pro Request durchsetzen; Logout/Sperrereignisse ergänzen. |
| Benutzermigration | kleine Anpassung | 2–4 | Vorhandene OIDCIdentitaet verwenden; lokale Nutzer-PKs und Gruppen erhalten. |
| Backup/Restore | kleine Anpassung | 1–3 | pg_dump plus konsistenter Medienstand; Restore und Rollenbesitz testen. |

Summe appbezogen: **8.5–18 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [pyproject.toml:1–48](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/pyproject.toml#L1-L48)
- [Dockerfile:1–45](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/Dockerfile#L1-L45)
- [docker-compose.yml:1–52](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker-compose.yml#L1-L52)
- [docker/start.sh:1–16](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker/start.sh#L1-L16)
- [schulwissen/einstellungen.py:1–70](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L1-L70)
- [kern/oidc.py:1–70](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L1-L70)
- [kern/models.py:1–70](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L1-L70)
- [kern/rechte.py:1–70](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L1-L70)
- [fachdaten/migrations/0001_trigramm.py:1–12](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/fachdaten/migrations/0001_trigramm.py#L1-L12)
- [tests/test_phase4.py:1–70](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `Dockerfile`: [L37](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/Dockerfile#L37)
- `docker-compose.yml`: [L3](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker-compose.yml#L3), [L17](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker-compose.yml#L17), [L33](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker-compose.yml#L33)
- `docker/start.sh`: [L8](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker/start.sh#L8), [L9](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/docker/start.sh#L9)
- `schulwissen/einstellungen.py`: [L35](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L35), [L43](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L43), [L73](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L73), [L113](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L113), [L127](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L127), [L136](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L136), [L138](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L138), [L141](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L141), [L145](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L145), [L209](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L209), [L211](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L211), [L215](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/schulwissen/einstellungen.py#L215)
- `kern/oidc.py`: [L1](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L1), [L20](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L20), [L30](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L30), [L36](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L36), [L49](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L49), [L56](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L56), [L66](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L66), [L112](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L112), [L118](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L118), [L132](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L132), [L149](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L149), [L151](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/oidc.py#L151)
- `kern/models.py`: [L26](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L26), [L30](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L30), [L45](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L45), [L48](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L48), [L90](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L90), [L99](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L99), [L140](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L140), [L148](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L148), [L1018](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L1018), [L1190](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L1190), [L1197](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L1197), [L1205](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/models.py#L1205)
- `kern/rechte.py`: [L6](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L6), [L19](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L19), [L20](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L20), [L21](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L21), [L26](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L26), [L37](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L37), [L41](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L41), [L45](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L45), [L51](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/kern/rechte.py#L51)
- `tests/test_phase4.py`: [L1](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L1), [L139](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L139), [L152](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L152), [L158](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L158), [L195](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L195), [L210](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L210), [L218](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L218), [L228](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L228), [L236](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L236), [L245](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L245), [L255](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L255), [L370](https://github.com/Bingenberger/schulwissen/blob/a9673bc343a3a6eea1c15f533d0e89061e669b32/tests/test_phase4.py#L370)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
