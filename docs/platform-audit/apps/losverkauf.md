# losverkauf

Prüfdatum: 2026-11-01T10:12:24.566025+00:00; Branch `main`; vollständiger Commit `2e471ea8abc5fb6acac8acabb292d8e99ede2787`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Flask >=3; Gunicorn >=21; SQLite; ReportLab; Leaflet-Frontend.
- **Dienste:** SQLite mit timeout=10 und BEGIN IMMEDIATE für Anmeldungen; Mail in lokalen Hintergrundthreads, keine dauerhafte Appqueue.
- **Produktionsbetrieb:** Gunicorn-systemd und nginx-/Deployskripte; kein Dockerfile. Fehlender ELTERN_TOKEN schaltet Entwicklungszugang frei; Produktionsstart muss das verhindern.
- **Frontend/Reproduzierbarkeit/Plattform:** Ungepinntes requirements; SECRET_KEY ohne Konfiguration zufällig, persistent setzen. Kein lokales Konten-SSO ohne neuen Identitätsbezug; Adminproxy kann nur gemeinsame Rolle schützen.
- **Persistenz/Migration:** Anmeldungen, Personen-/Kontakt-/Bezirksdaten, edit_tokens, mail_log, config/Bezirke und Karte; lokale DB_PATH.
- **Externe Abhängigkeiten/Self-Hosting:** Leaflet/OpenStreetMap-Karten und Import über OSM-Daten; Inhalte/Tile-Policy für isolierten Betrieb berücksichtigen.
- **Schwere Verarbeitung:** ReportLab-PDF und Kartenimport; konkurrierende Anmeldungen fachlich auf Maximalplätze testen.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Ein gemeinsames ADMIN_PASSWORD aus Env mit compare_digest, Adminflag in Flask-Cookie; Eltern-Token und persönliche edit_tokens; keine lokale Personen-/Usertabelle für Admins.
- **Öffentliche/alternative Zugänge:** Elternroute /?t=..., /api/bezirke, Anmeldungen und tokengebundene Löschung; /healthz vorhanden.
- **Mail/Konfiguration:** smtplib; SMTP_HOST/PORT/SICHERHEIT/USER/PASSWORD, MAIL_FROM/REPLY_TO; ohne SMTP_HOST lokale .eml unter data/mails.
- **Hauptbefund:** Tokenleerer Entwicklungsmodus und verlorene Hintergrundmails beim Prozessneustart sind betriebliche Risiken.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Nicht-Root-Gunicorn-Image, /healthz nutzen; Secret/Elterntoken verpflichtend, Threads/Mailzustellung absichern. |
| Domainwechsel | kleine Anpassung | 1–3 | Mail-/Elternlinks und Proxy-Host prüfen, eventuell BASE_URL ergänzen; alte Links befristet erhalten. |
| Zentraler Mailversand | kleine Anpassung | 1–3 | SMTP_* zum Relay und Mail-Sink; Threadverlust vor Relayannahme durch dauerhafte Outbox beheben. |
| SSO | größerer Umbau | 4–8 | Für gemeinsame Adminfunktion Proxy-/BFF-Policy zulässig; individuelle Auditidentität braucht native OIDC-/Sessionanpassung; Elternpfade getrennt. |
| Benutzermigration | kleine Anpassung | 1–3 | Keine Admin-Usertabelle vorhanden; neue Identitätszuordnung bewusst einführen, edit_tokens/Anmeldungsbesitz erhalten. |
| Backup/Restore | kleine Anpassung | 2–4 | SQLite-Backup plus Bezirke/Kartendaten und Mailoutbox; Integrität/Platzlimits nach Restore prüfen. |

Summe appbezogen: **11–25 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [requirements.txt:1–3](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/requirements.txt#L1-L3)
- [app.py:1–70](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L1-L70)
- [mail.py:1–70](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L1-L70)
- [deploy/losverkauf.service:1–29](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.service#L1-L29)
- [deploy/losverkauf.env.example:1–18](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L1-L18)
- [templates/index.html:1–70](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/templates/index.html#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `app.py`: [L6](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L6), [L11](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L11), [L12](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L12), [L35](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L35), [L40](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L40), [L236](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L236), [L237](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L237), [L270](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L270), [L323](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L323), [L348](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L348), [L349](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L349), [L455](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/app.py#L455)
- `mail.py`: [L2](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L2), [L6](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L6), [L8](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L8), [L21](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L21), [L23](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L23), [L25](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L25), [L31](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L31), [L37](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L37), [L58](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L58), [L61](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L61), [L65](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L65), [L69](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/mail.py#L69)
- `deploy/losverkauf.env.example`: [L3](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L3), [L6](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L6), [L7](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L7), [L10](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L10), [L11](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L11), [L12](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L12), [L14](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L14), [L15](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L15), [L16](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/deploy/losverkauf.env.example#L16)
- `templates/index.html`: [L54](https://github.com/Bingenberger/losverkauf/blob/2e471ea8abc5fb6acac8acabb292d8e99ede2787/templates/index.html#L54)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
