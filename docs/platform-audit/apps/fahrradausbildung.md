# fahrradausbildung

Prüfdatum: 2026-11-01T10:12:19.568325+00:00; Branch `main`; vollständiger Commit `d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Python >=3.12,<3.13; FastAPI/Uvicorn; SQLAlchemy/Alembic.
- **Dienste:** PostgreSQL 16; kein externer Queue-Dienst im geprüften Startpfad.
- **Produktionsbetrieb:** Nicht-Root-Dockerfile mit Pango/HarfBuzz und Healthcheck /gesund; Compose Port 8000; uv sync --frozen; Alembic-Start. Proxyvertrauen derzeit bei Loopback-Bind erklärt, bei Plattformnetz explizit begrenzen.
- **Frontend/Reproduzierbarkeit/Plattform:** HTML/Jinja, Posten-JS und Service Worker. Linux amd64 plausibel; Pango/Pillow/psycopg/WeasyPrint auf ARM64 noch nicht gebaut.
- **Persistenz/Migration:** PostgreSQL, schuleigene /vorlagen; Posten-Web-App speichert offline im Browser/IndexedDB.
- **Externe Abhängigkeiten/Self-Hosting:** OSM-Kartenkacheln konfigurierbar; Offline-Kartenabdeckung und Lizenz-/Attributionsbedingungen separat klären.
- **Schwere Verarbeitung:** WeasyPrint, Pillow, QR/Segno, Kartenbilder und Auswertungs-PDFs.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Argon2id; serverseitige AdminSitzung mit gehashtem Cookie, CSRF, 120 min Leerlauf/12 h Maximum; Schule/Benutzer und Posten-Tokens getrennt.
- **Öffentliche/alternative Zugänge:** Posten-Zugang per Token und /gesund; Posten-PWA/Service Worker erhalten, keinen pauschalen Login davorsetzen.
- **Mail/Konfiguration:** Kein SMTP-Versand im geprüften Anwendungscode gefunden; zentrale Einladungen zunächst im IdP.
- **Hauptbefund:** Das vorhandene Schulmodell ist kein Nachweis vollständig geprüfter Mehrmandantenfähigkeit. Offline-Sperren können erst beim Wiederverbinden greifen.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 1–2 | Bestehendes Image versionieren; nichtöffentliches Backend und dedizierte Netze. |
| Domainwechsel | kleine Anpassung | 1–2 | FP_OEFFENTLICHE_URL und Karten-/Posten-Links, Proxy-IPs, QR-Codes testen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Keinen künstlichen SMTP-Dienst in App ergänzen; Einladung im IdP. |
| SSO | größerer Umbau | 5–9 | Authlib-Code-Flow mit PKCE ergänzen; lokale sitzung_anlegen erst nach issuer/sub-Mapping und Appfreigabe; Postenmodus separat lassen. |
| Benutzermigration | kleine Anpassung | 2–4 | Benutzer.id, Schule und laufbezogene Rechte erhalten; Konten nur kontrolliert verknüpfen. |
| Backup/Restore | kleine Anpassung | 1–3 | pg_dump, Vorlagen/Logos und nachweisbarem Offline-Synchronisationsstand sichern; ungesyncte Browserdaten sind kein Serverbackup. |

Summe appbezogen: **10–20.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- `app/posten_app/vendor/idb.LICENSE`
- `app/static/vendor/leaflet/LICENSE`
- `app/static/vendor/phosphor/LICENSE`

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [pyproject.toml:1–34](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/pyproject.toml#L1-L34)
- [Dockerfile:1–41](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/Dockerfile#L1-L41)
- [docker-compose.yml:1–53](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/docker-compose.yml#L1-L53)
- [app/config.py:1–43](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/config.py#L1-L43)
- [app/modelle.py:1–70](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L1-L70)
- [app/web/sitzung.py:1–70](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L1-L70)
- [app/web/anmeldung.py:1–70](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L1-L70)
- [app/posten/api.py:1–70](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L1-L70)
- [app/posten_app/sw.js:1–70](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten_app/sw.js#L1-L70)
- [app/token.py:1–58](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/token.py#L1-L58)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `docker-compose.yml`: [L3](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/docker-compose.yml#L3), [L17](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/docker-compose.yml#L17), [L33](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/docker-compose.yml#L33)
- `app/config.py`: [L11](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/config.py#L11)
- `app/modelle.py`: [L44](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L44), [L100](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L100), [L103](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L103), [L104](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L104), [L105](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L105), [L116](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L116), [L419](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L419), [L488](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/modelle.py#L488)
- `app/web/sitzung.py`: [L7](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L7), [L39](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L39), [L42](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L42), [L59](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L59), [L80](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L80), [L131](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L131), [L165](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L165), [L168](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/sitzung.py#L168)
- `app/web/anmeldung.py`: [L4](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L4), [L17](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L17), [L29](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L29), [L44](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L44), [L57](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L57), [L64](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L64), [L73](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L73), [L75](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L75), [L76](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L76), [L97](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L97), [L106](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L106), [L113](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/web/anmeldung.py#L113)
- `app/posten/api.py`: [L31](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L31), [L101](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L101), [L135](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L135), [L144](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L144), [L159](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L159), [L178](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L178), [L286](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L286), [L293](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L293), [L312](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L312), [L336](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L336), [L357](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L357), [L376](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/posten/api.py#L376)
- `app/token.py`: [L18](https://github.com/Bingenberger/fahrradausbildung/blob/d9a9a6c8e02dd7fd5a14a5e2151948d7ec32c207/app/token.py#L18)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
