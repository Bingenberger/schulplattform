# leseflux

Prüfdatum: 2026-11-01T10:12:19.869569+00:00; Branch `main`; vollständiger Commit `6ad61b28a31d41d98e03d3be835a6c678ad6e439`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Node/TypeScript; Fastify 5, Prisma 5.20; React 18/Vite 5.
- **Dienste:** PostgreSQL 16; API+Web+nginx aus Compose; Prisma-Migrationen.
- **Produktionsbetrieb:** Compose mit PostgreSQL-Port 5433 auf allen Hostadressen und nginx auf 80/443: unter Plattform entfernen. API-Port 3001; Production-Migration mit prisma migrate deploy statt dev.
- **Frontend/Reproduzierbarkeit/Plattform:** npm package-lock vorhanden; Build shared→api→web; CORS_ORIGIN muss zur veröffentlichten Domain passen, VITE_API_URL ist Vite-Konfiguration; echte Produktionsbuilds noch nicht ausgeführt.
- **Persistenz/Migration:** Prisma-User-UUIDs, Klassen, Gruppen, Trainings-/Diagnostikergebnisse; schema.prisma enthält qrTokenRaw zusätzlich zu qrTokenHash, entgegen älterer CLAUDE-Beschreibung.
- **Externe Abhängigkeiten/Self-Hosting:** Anton-QR als opaker String, keine Anton-API im geprüften Pfad; keine gehostete DB erforderlich.
- **Schwere Verarbeitung:** Training läuft überwiegend im Browser; API-Adaptions-/Diagnostiklogik und CSV/QR-Ausgabe; keine serverseitige Chromium-PDF-Abhängigkeit in API package.json.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Argon2 für Erwachsene; JWT 8 h Lehrkräfte/24 h Kinder; Kind-QR und Login-Code; TEACHER/ADMIN/CHILD und Klassenbeziehungen.
- **Öffentliche/alternative Zugänge:** Kinderlogin /api/auth/login-child und login-child-code bleiben eigenständig; Erwachsene per OIDC; Kinderdaten nicht öffentlich.
- **Mail/Konfiguration:** Kein SMTP-Versand im API-Quellcode gefunden; IdP übernimmt neue Mitarbeitereinladungen.
- **Hauptbefund:** Lange selbsttragende JWTs verhindern ohne Umbau die gewünschte schnelle Sperrung. Quellenbeschreibung zur QR-Speicherung ist veraltet; aktuelles Schema maßgeblich.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Compose auf Plattformproxy umstellen, DB-Hostport entfernen; frozen npm ci und Prisma-Generation/Health prüfen. |
| Domainwechsel | kleine Anpassung | 1–3 | CORS_ORIGIN, Frontend-APIpfad und SameSite-Verhalten gemeinsam umstellen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Einladung im IdP; kein zusätzlicher Mailserver in App erforderlich. |
| SSO | größerer Umbau | 6–11 | OIDC-BFF für Erwachsene; JWT-Widerruf/Statusprüfung ergänzen, Kinder-Codefluss gezielt erhalten. |
| Benutzermigration | größerer Umbau | 3–7 | UUIDs und Class/GroupMember-Beziehungen beibehalten; QR-Rohwerte wie Zugangsdaten schützen und rotieren. |
| Backup/Restore | kleine Anpassung | 1–3 | pg_dump einschließlich Schülerfortschritt und QR-Zugangsdaten; Seeds nur synthetisch und nicht bei jedem Start. |

Summe appbezogen: **13–28.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [package.json:1–25](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/package.json#L1-L25)
- [apps/api/package.json:1–48](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/package.json#L1-L48)
- [docker-compose.yml:1–53](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/docker-compose.yml#L1-L53)
- [apps/api/Dockerfile:1–30](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/Dockerfile#L1-L30)
- [apps/api/src/app.ts:1–48](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/app.ts#L1-L48)
- [apps/api/src/plugins/auth.ts:1–46](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/plugins/auth.ts#L1-L46)
- [apps/api/src/modules/auth/routes.ts:1–70](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L1-L70)
- [apps/api/prisma/schema.prisma:1–70](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L1-L70)
- [apps/api/src/modules/teacher/routes.ts:1–70](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L1-L70)
- [apps/web/src/store/authStore.ts:1–22](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/web/src/store/authStore.ts#L1-L22)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `apps/api/package.json`: [L8](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/package.json#L8)
- `docker-compose.yml`: [L8](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/docker-compose.yml#L8), [L25](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/docker-compose.yml#L25)
- `apps/api/src/plugins/auth.ts`: [L37](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/plugins/auth.ts#L37)
- `apps/api/src/modules/auth/routes.ts`: [L24](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L24), [L27](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L27), [L32](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L32), [L50](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L50), [L53](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L53), [L58](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L58), [L76](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L76), [L79](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L79), [L83](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L83), [L87](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L87), [L98](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L98), [L110](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/auth/routes.ts#L110)
- `apps/api/prisma/schema.prisma`: [L7](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L7), [L15](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L15), [L21](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L21), [L29](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L29), [L34](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L34), [L48](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L48), [L179](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L179), [L202](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L202), [L254](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L254), [L269](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L269), [L271](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L271), [L277](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/prisma/schema.prisma#L277)
- `apps/api/src/modules/teacher/routes.ts`: [L15](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L15), [L137](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L137), [L234](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L234), [L359](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L359), [L430](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L430), [L475](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L475), [L553](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L553), [L649](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L649), [L731](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L731), [L1131](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L1131), [L1306](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L1306), [L1475](https://github.com/Bingenberger/leseflux/blob/6ad61b28a31d41d98e03d3be835a6c678ad6e439/apps/api/src/modules/teacher/routes.ts#L1475)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
