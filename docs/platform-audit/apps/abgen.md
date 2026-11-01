# abgen

Prüfdatum: 2026-11-01T10:12:25.575811+00:00; Branch `main`; vollständiger Commit `50db999ccc689cdad3a6b2c930d24dee650eaec2`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Node >=22, pnpm-Workspace; Fastify 5/Drizzle/pg; React 19/Vite 8; Playwright 1.64.1.
- **Dienste:** PostgreSQL 18-alpine, Web/nginx, API 3000 und eigener Chromium-PDF-Dienst 3001; WebSockets/Yjs.
- **Produktionsbetrieb:** Drei Dockerfiles und Compose samt Healthchecks. Default-DBpasswort und COOKIE_SECURE=false nur für Beispiel; Plattform muss sichere Werte erzwingen. PG18-Pfad /var/lib/postgresql beachten.
- **Frontend/Reproduzierbarkeit/Plattform:** pnpm-lock und Node >=22 vorhanden; native Argon2/Chromium/Fonts auf ARM64 nicht gebaut. PostgreSQL18 nicht ungeprüft mit PG16 zusammenlegen.
- **Persistenz/Migration:** PostgreSQL, Content-hash-Assets in /app/data/assets, Browserzustand/Offline-Dokumente; Drizzle-Migrationen.
- **Externe Abhängigkeiten/Self-Hosting:** Wörterbücher/Fonts lokal im Bestand, Fetch-Skripte beim Build; externe Medienherkunft und Nutzungsrechte trotzdem prüfen.
- **Schwere Verarbeitung:** Persistenter lazy Chromium-Browser, je /render neue Seite; PDF/26 Varianten und 60s Timeout; Yjs-Kollaboration/WebSockets.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Argon2 via @node-rs/argon2, Cookie-Sessions; Registrierung standardmäßig zu, erstes Konto ausgenommen; Eigentümer/Freigaben, öffentliche Spiel-/Kurzcodes.
- **Öffentliche/alternative Zugänge:** Print-/Share-/Play-/Kurzcoderouten nach jeweiligem Token; Drucktoken erlauben Dienstzugriff, nicht pauschal OIDC davor.
- **Mail/Konfiguration:** Kein SMTP-/Nodemailer-Versand im Servercode gefunden.
- **Hauptbefund:** Zusätzlicher PG18- und Chromium-Betrieb macht 14-App-Installation deutlich schwerer als statische Frontends. Font-/Wörterbuchlizenzen einzeln erhalten.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Digest-Images, produktive Secrets/Cookieflags erzwingen; PDF-Dienst nur intern, Parallelität und Queue hart begrenzen. |
| Domainwechsel | kleine Anpassung | 2–4 | WEB_ORIGIN, Druckseiten, WS-Origin, Cookie-/CORS und Tokenlinks atomar ändern. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Mail nicht benötigt; IdP-Einladung. |
| SSO | größerer Umbau | 7–13 | OIDC-BFF für Konten; WS-Handshake und laufende Verbindungen auf Sperrung prüfen, Share/Print/Play getrennt lassen. |
| Benutzermigration | größerer Umbau | 3–7 | Lokale Account-IDs, Dokumentbesitzer und Freigaben erhalten; Offline-Konflikte bei Wiedersynchronisierung testen. |
| Backup/Restore | größerer Umbau | 3–6 | PG18 pg_dump und Assetvolume zusammen sichern; Restore mit Fonts/Wörterbüchern/Versionsstand, offene Yjs-Sessions vorher drainen. |

Summe appbezogen: **17–34.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- `assets/dictionaries/de-AT/license`
- `assets/dictionaries/de-CH/license`
- `assets/dictionaries/de-DE/license`
- `assets/fonts/abeezee/OFL.txt`
- `assets/fonts/andika/OFL.txt`
- `assets/fonts/atkinson/OFL.txt`
- `assets/fonts/fibel-nord/OFL.txt`
- `assets/fonts/grundschrift/LICENSE.txt`
- `assets/fonts/opendyslexic/OFL.txt`
- `assets/fonts/playwrite-at/OFL.txt`
- `assets/fonts/playwrite-de-grund/OFL.txt`
- `assets/fonts/playwrite-de-la/OFL.txt`
- `assets/fonts/playwrite-de-sas/OFL.txt`
- `assets/fonts/playwrite-de-va/OFL.txt`

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [package.json:1–44](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/package.json#L1-L44)
- [docker-compose.yml:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker-compose.yml#L1-L70)
- [docker/pdf.Dockerfile:1–17](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker/pdf.Dockerfile#L1-L17)
- [apps/server/src/config.ts:1–52](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/config.ts#L1-L52)
- [apps/server/src/app.ts:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/app.ts#L1-L70)
- [apps/server/src/auth/session.ts:1–41](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L1-L41)
- [apps/server/src/routes/auth.ts:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L1-L70)
- [apps/server/src/routes/collab.ts:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/collab.ts#L1-L70)
- [apps/server/src/pdf/service.ts:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L1-L70)
- [apps/server/src/db/schema.ts:1–70](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `docker-compose.yml`: [L32](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker-compose.yml#L32), [L92](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker-compose.yml#L92)
- `docker/pdf.Dockerfile`: [L1](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker/pdf.Dockerfile#L1), [L9](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/docker/pdf.Dockerfile#L9)
- `apps/server/src/config.ts`: [L10](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/config.ts#L10), [L13](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/config.ts#L13)
- `apps/server/src/auth/session.ts`: [L3](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L3), [L6](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L6), [L8](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L8), [L15](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L15), [L30](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L30), [L31](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L31), [L34](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L34), [L40](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/auth/session.ts#L40)
- `apps/server/src/routes/auth.ts`: [L6](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L6), [L10](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L10), [L38](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L38), [L42](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L42), [L54](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L54), [L67](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L67), [L106](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L106), [L120](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L120), [L128](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L128), [L155](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L155), [L165](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L165), [L180](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/routes/auth.ts#L180)
- `apps/server/src/pdf/service.ts`: [L2](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L2), [L46](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L46), [L55](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L55), [L80](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L80), [L89](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L89), [L126](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L126), [L128](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/pdf/service.ts#L128)
- `apps/server/src/db/schema.ts`: [L20](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L20), [L23](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L23), [L25](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L25), [L34](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L34), [L35](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L35), [L44](https://github.com/Bingenberger/abgen/blob/50db999ccc689cdad3a6b2c930d24dee650eaec2/apps/server/src/db/schema.ts#L44)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
