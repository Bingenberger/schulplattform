# grundschultafel

Prüfdatum: 2026-11-01T10:12:35.003819+00:00; Branch `main`; vollständiger Commit `496466cac7cc2b3e48a6acd2940ebc91029c145f`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Next.js 16.1.6; React 19.2.3; Node; ungenutzte node:sqlite-Typdeklaration; Fabric 7; bcryptjs/jose.
- **Dienste:** Next-Server, users.json und benutzerspezifische JSON-/Dateispeicher; Galerie ist externer HTTP-Dienst.
- **Produktionsbetrieb:** npm build/start, Port 3000; kein Dockerfile/Compose. package.json legt keine Node-Engine fest; node:sqlite existiert nur als Typdeklaration, kein Laufzeitimport im src-Code gefunden; JSON-Dateischreiben ohne DB-Transaktion.
- **Frontend/Reproduzierbarkeit/Plattform:** package-lock vorhanden; SSR/API, keine reine statische App. Immutable Image braucht beschreibbare data/ und definierte Asset-Volumes; paralleles users.json-Schreiben absichern.
- **Persistenz/Migration:** data/users.json und data/<user-id> für Notizbücher; öffentliche Assets/Backgrounds/Journal und mobile Uploads; lokale Browserzustände gesondert prüfen.
- **Externe Abhängigkeiten/Self-Hosting:** YouTube Data API/YOUTUBE_API_KEY, externe Galerie pix.foerster.rocks und Fontlibrary-CSS; für vollständigen Offline-/Selfhost-Modus Ersatz/Deaktivierung erforderlich.
- **Schwere Verarbeitung:** Fabric-Canvas überwiegend Browser; Galerie-/Bild-Proxy und Uploadverarbeitung; Server-GPU daraus nicht ableitbar.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** bcrypt-Hashes in data/users.json; admin/teacher; HS256-Cookie mit 30 Tagen; Middleware/API-Sessionprüfungen, bekannte Initialkombination admin/123456.
- **Öffentliche/alternative Zugänge:** /login, /api/auth/login, /api/auth/users, /upload, /api/mobile-upload laut Middleware; Uploadberechtigungen separat prüfen.
- **Mail/Konfiguration:** Keine SMTP-Versandstelle im src-Code gefunden.
- **Hauptbefund:** Fester Erstzugang und 30-Tage-Claims-Sessions sind vor zentralem Betrieb zu korrigieren. Reine Proxyanmeldung löst Besitzrechte nicht.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | größerer Umbau | 3–6 | Unterstützte Node-LTS-Version festlegen, standalone Next-Image und Health; Standardzugang durch einmaligen Bootstrap ersetzen. |
| Domainwechsel | kleine Anpassung | 2–4 | Basis-URL für Mobile/QR und externe Galerie konfigurierbar machen, Cookie-/Proxy-/APIpfade testen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Mail nicht erforderlich; IdP übernimmt Einladungen. |
| SSO | größerer Umbau | 6–11 | OIDC-BFF und widerrufbare serverseitige Sessions; bestehende API-Autorisierung pro User-ID/Rolle beibehalten. |
| Benutzermigration | größerer Umbau | 3–7 | UUIDs und data/<id>-Verzeichnisse erhalten; JSON-Userstore transaktional oder atomar/gesperrt schreiben; kein E-Mail-Zwang. |
| Backup/Restore | größerer Umbau | 3–6 | Schreibpause für JSON-/Dateibestand plus Konfiguration der externen Galerie, alle beschreibbaren public-Assetpfade erfassen. |

Summe appbezogen: **17–34.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden; README.md:214 erklärt ausdrücklich „Nicht zur Weitergabe bestimmt“. Gemeinsame Distribution ist ohne gesonderte Rechtefreigabe blockiert. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [package.json:1–39](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/package.json#L1-L39)
- [src/lib/users.ts:1–70](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L1-L70)
- [src/lib/session.ts:1–58](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L1-L58)
- [src/lib/gallery.ts:1–70](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/gallery.ts#L1-L70)
- [src/middleware.ts:1–57](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L1-L57)
- [src/app/api/notebooks/route.ts:1–55](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/notebooks/route.ts#L1-L55)
- [src/app/api/mobile-upload/route.ts:1–70](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L1-L70)
- [src/app/api/youtube/route.ts:1–32](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/youtube/route.ts#L1-L32)
- [src/app/layout.tsx:1–33](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/layout.tsx#L1-L33)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `src/lib/users.ts`: [L11](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L11), [L12](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L12), [L25](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L25), [L29](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L29), [L30](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L30), [L32](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L32), [L68](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L68), [L72](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L72), [L73](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L73), [L77](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L77), [L87](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L87), [L88](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/users.ts#L88)
- `src/lib/session.ts`: [L5](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L5), [L6](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L6), [L13](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L13), [L14](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L14), [L25](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L25), [L30](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L30), [L38](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L38), [L39](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L39), [L43](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L43), [L44](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L44), [L55](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L55), [L57](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/lib/session.ts#L57)
- `src/middleware.ts`: [L3](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L3), [L6](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L6), [L19](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L19), [L22](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L22), [L31](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L31), [L35](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L35), [L36](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L36), [L37](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L37), [L41](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L41), [L45](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/middleware.ts#L45)
- `src/app/api/notebooks/route.ts`: [L4](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/notebooks/route.ts#L4), [L8](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/notebooks/route.ts#L8), [L9](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/notebooks/route.ts#L9), [L13](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/notebooks/route.ts#L13)
- `src/app/api/mobile-upload/route.ts`: [L5](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L5), [L6](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L6), [L7](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L7), [L32](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L32), [L35](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L35), [L38](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L38), [L44](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L44), [L48](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L48), [L49](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L49), [L83](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L83), [L87](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L87), [L88](https://github.com/Bingenberger/grundschultafel/blob/496466cac7cc2b3e48a6acd2940ebc91029c145f/src/app/api/mobile-upload/route.ts#L88)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
