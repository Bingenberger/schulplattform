# zackboing

Prüfdatum: 2026-11-01T10:12:25.923532+00:00; Branch `main`; vollständiger Commit `05e78a1e829a7634cd35deb5ab06c7c8a5e9d365`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Node >=18; Express 4.21; Socket.IO 4.8; better-sqlite3 11.10.
- **Dienste:** SQLite WAL; aktive Spiele/Teilnehmer im Node-Prozessspeicher; HTTP plus WebSockets.
- **Produktionsbetrieb:** systemd auf Port 3100, Code default 3000; kein Dockerfile. npm Lock vorhanden; better-sqlite3 native Binding unter Host-Node26 hier nicht erfolgreich gebaut.
- **Frontend/Reproduzierbarkeit/Plattform:** Serverseitiges HTML/JS statisch plus Express-API; kein reines statisches Frontend. ARM64 nativ ungeprüft; Node-LTS passend zu better-sqlite3 festlegen.
- **Persistenz/Migration:** ZACKBOING_DATA/zackboing.db; Quiz-/User-/Session-/Settingdaten und lokale Uploads; aktive Spiele sind flüchtig und überleben Neustart nicht.
- **Externe Abhängigkeiten/Self-Hosting:** Bildgalerie mit konfigurierbarer URL, Vorgabe pix.foerster.rocks; HTTP-Proxy für Bildsuche; Quizkern lokal.
- **Schwere Verarbeitung:** Socket.IO-Broadcast und zahlreiche offene Verbindungen; scryptSync blockiert Event Loop bei Loginspitzen; Uploads.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** crypto.scryptSync-Passwörter; serverseitige sessions mit token/user_id ohne Ablaufprüfung in userForToken; Cookie 90 Tage; admin/teacher; erstes offenes Registrierkonto wird Admin.
- **Öffentliche/alternative Zugänge:** Spiel-PIN/Teilnehmerzugang ohne Lehrkraftkonto; Hostrechte am WS-Handshake/Events separat; keine pauschale Auth vor Socket.IO.
- **Mail/Konfiguration:** Keine SMTP-/Mailversandstelle im server-Code gefunden.
- **Hauptbefund:** Ein erfolgreicher npm-ci-Lockinstall ohne natives Binding ist noch kein erfolgreicher Produktionsbuild. Game-State braucht kein PostgreSQL, aber geplante Neustarts.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | größerer Umbau | 3–5 | Node-LTS/native Binding im isolierten CI-Image validieren; Nicht-Root-Image und Readiness; offene Erstregistrierung durch Bootstrap ersetzen. |
| Domainwechsel | kleine Anpassung | 1–3 | Galerie-URL, Host-/Join-QR und Socket.IO-Origin/Upgrade im Proxy testen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Mail nicht erforderlich; IdP-Einladungen. |
| SSO | größerer Umbau | 6–11 | OIDC für Hosts/Lehrkräfte, Sessionablauf und Widerruf ergänzen; bestehende WS-Verbindungen bei Sperrung schließen. |
| Benutzermigration | kleine Anpassung | 2–4 | User.id und Quizbesitz erhalten; Gäste/PIN-Teilnehmer nicht ins zentrale Verzeichnis aufnehmen. |
| Backup/Restore | kleine Anpassung | 2–4 | SQLite-Backup und Uploads; Spiele vor Wartung drainen und flüchtigen Spielverlust im Betriebsvertrag benennen. |

Summe appbezogen: **14–27.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [package.json:1–25](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/package.json#L1-L25)
- [server/auth.js:1–70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L1-L70)
- [server/db.js:1–70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L1-L70)
- [server/index.js:1–70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L1-L70)
- [server/game.js:1–70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/game.js#L1-L70)
- [deploy/zackboing.service:1–25](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/deploy/zackboing.service#L1-L25)
- [test/e2e.js:1–70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `server/auth.js`: [L6](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L6), [L8](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L8), [L12](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L12), [L19](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L19), [L21](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L21), [L25](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L25), [L26](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L26), [L32](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L32), [L52](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L52), [L64](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L64), [L69](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L69), [L70](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/auth.js#L70)
- `server/db.js`: [L1](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L1), [L7](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L7), [L10](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L10), [L11](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L11), [L20](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L20), [L46](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L46), [L56](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L56), [L59](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L59), [L61](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L61), [L66](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L66), [L80](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L80), [L105](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/db.js#L105)
- `server/index.js`: [L33](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L33), [L52](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L52), [L68](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L68), [L101](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L101), [L263](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L263), [L311](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L311), [L423](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L423), [L452](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L452), [L500](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L500), [L518](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L518), [L531](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L531), [L765](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/server/index.js#L765)
- `test/e2e.js`: [L45](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L45), [L57](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L57), [L65](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L65), [L73](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L73), [L80](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L80), [L103](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L103), [L143](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L143), [L190](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L190), [L194](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L194), [L197](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L197), [L206](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L206), [L453](https://github.com/Bingenberger/zackboing/blob/05e78a1e829a7634cd35deb5ab06c7c8a5e9d365/test/e2e.js#L453)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
