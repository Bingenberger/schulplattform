# schulkasse

Prüfdatum: 2026-11-01T10:12:21.272057+00:00; Branch `main`; vollständiger Commit `d99cfca9eb26acb606234ff664ffa2b38ff3352c`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Python >=3.12; Flask 3.1.3; Gunicorn 26.2; Argon2, WeasyPrint 70.
- **Dienste:** SQLite mit WAL, busy_timeout 5 s und BEGIN IMMEDIATE; nummerierte SQL-Migrationen.
- **Produktionsbetrieb:** systemd/Gunicorn, Install-/Update-/Backup-Timer vorhanden; kein Dockerfile. Gepinnte requirements aber ohne Hash-Lock; Pango/HarfBuzz nötig.
- **Frontend/Reproduzierbarkeit/Plattform:** SQLite für 10 gleichzeitige Personen nicht ohne Messung ersetzen. Export/Anonymisierung vorhanden; Buchungsintegrität und gleichzeitige Umbuchungen vor SSO-Umstellung testen.
- **Persistenz/Migration:** Finanz-/Beitrags-/Schüler-/Kontodaten, Bankimporte und Buchungen, Brief-Konfiguration und Schlüssel für 2FA; DB-Datei aus SCHULKASSE_*.
- **Externe Abhängigkeiten/Self-Hosting:** Bankdateiimport (z. B. CAMT) lokal; kein nachgewiesener Zahlungsprovider/API-Zwang.
- **Schwere Verarbeitung:** WeasyPrint-Briefe/Monatsberichte, CAMT-Import und Matching; keine echte Online-Zahlung aus Namen ableiten.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Serverseitige sitzung-Tabelle, acht Stunden Inaktivität, Argon2id; MFA/TOTP; admin/kasse/lehrkraft, Projektzugriff für verantwortliche User-ID, CSRF.
- **Öffentliche/alternative Zugänge:** Mitarbeiterlogin und statische Assets; fachliche Daten durch Rollen und Projektbesitz schützen.
- **Mail/Konfiguration:** Keine SMTP-Versandstelle im Anwendungscode gefunden; Briefe/PDF sind kein Mailversand.
- **Hauptbefund:** Finanzdatenintegrität hat Vorrang vor Vereinheitlichung. Kein pauschaler Umzug auf gemeinsame fachliche DB.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Nicht-Root-Python/Pango-Image, SQL-Migration als Einmaljob und Readiness. |
| Domainwechsel | kleine Anpassung | 1–2 | Proxy-/Cookie-Einstellungen und absolute Brief-/QR-Daten prüfen; SCHULKASSE-Konfiguration in Manifest. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Keinen unnötigen SMTP-Code ergänzen. |
| SSO | größerer Umbau | 6–11 | OIDC mit MFA-Claim/Policy für Finanzrollen und serverseitiger Sessionrevokation ergänzen; lokale Kassenrechte bleiben maßgeblich. |
| Benutzermigration | größerer Umbau | 3–6 | benutzer.id und verantwortlich_user_id unverändert; Kasse/Admin nicht aus allgemeiner Plattformgruppe ableiten. |
| Backup/Restore | kleine Anpassung | 2–4 | SQLite-Backup-API plus Briefvorlage/Keys; Salden-/Buchungs-/Umbuchungsabgleich nach Restore; Ereignis-RPO enger als täglich prüfen. |

Summe appbezogen: **14–27.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [requirements.txt:1–30](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/requirements.txt#L1-L30)
- [pyproject.toml:1–26](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/pyproject.toml#L1-L26)
- [schulkasse/auth.py:1–70](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L1-L70)
- [schulkasse/db.py:1–70](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L1-L70)
- [schulkasse/config.py:1–63](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L1-L63)
- [schulkasse/zwei_faktor.py:1–70](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/zwei_faktor.py#L1-L70)
- [schulkasse/buchung.py:1–70](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/buchung.py#L1-L70)
- [schulkasse/anonymisierung.py:1–70](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/anonymisierung.py#L1-L70)
- [deploy/schulkasse-backup.service:1–11](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/deploy/schulkasse-backup.service#L1-L11)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `schulkasse/auth.py`: [L1](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L1), [L13](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L13), [L40](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L40), [L60](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L60), [L74](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L74), [L81](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L81), [L91](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L91), [L94](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L94), [L148](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L148), [L182](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L182), [L188](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L188), [L199](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/auth.py#L199)
- `schulkasse/db.py`: [L13](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L13), [L17](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L17), [L28](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L28), [L56](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L56), [L105](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/db.py#L105)
- `schulkasse/config.py`: [L36](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L36), [L38](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L38), [L40](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L40), [L44](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L44), [L47](https://github.com/Bingenberger/schulkasse/blob/d99cfca9eb26acb606234ff664ffa2b38ff3352c/schulkasse/config.py#L47)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
