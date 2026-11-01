# SL-Journal

Prüfdatum: 2026-11-01T10:12:35.163719+00:00; Branch `main`; vollständiger Commit `9dd44a584c7b9a35e28c6a362f97c8c9babb4d98`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Flask >=3.1,<4; SQLCipher/sqlcipher3-binary; Waitress; React/Excalidraw/CodeMirror-Bundles.
- **Dienste:** Verschlüsselte SQLCipher-Datei; systemd-Sync und Maintenance-Timer; kein PostgreSQL.
- **Produktionsbetrieb:** Waitress auf 127.0.0.1:8088, vier Threads; systemd-Härtung vorhanden, kein Dockerfile; native SQLCipher-Binaries und LibreOffice nötig.
- **Frontend/Reproduzierbarkeit/Plattform:** requirements mit Bandbreiten, package-lock für Frontend. SQLCipher und Schlüsselsicherung eigens testen; Standard-sqlite3-Backup kann verschlüsselte Datei nicht einfach öffnen.
- **Persistenz/Migration:** Verschlüsselte Journal-DB, Daten-/Fernet-Schlüssel und Instanzkonfiguration; Notizen, E-Mails, Kontakte, Anhänge, Termine und Geräteberechtigungen.
- **Externe Abhängigkeiten/Self-Hosting:** Optional IMAP, CalDAV/Nextcloud; eigene Server möglich; Quellsysteme und Zugangsdaten separat migrieren.
- **Schwere Verarbeitung:** Poppler pdftoppm/pdftotext, LibreOffice für Vorschauen/Text; Semaphoren begrenzen PDF auf zwei, Office auf einen Vorgang pro Prozess; temporäre Klartextdateien bei Office-Konvertierung.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Genau ein account mit CHECK(id=1), Werkzeug-Passwort + TOTP, session_version; eigene Mobil-API mit gehashten Gerätetokens und 90 Tagen Inaktivität.
- **Öffentliche/alternative Zugänge:** Setup/Login und Mobil-API; Mobil-Bearer ist eigene Vertrauensgrenze. Keine öffentliche Freigabe des Journals ableiten..
- **Mail/Konfiguration:** IMAP-Leseimport, CalDAV und Nextcloud-Integration; kein SMTP-Versand im geprüften journal-Pythoncode gefunden. IMAP-Zugang nicht durch SMTP ersetzen..
- **Hauptbefund:** MIT-Hauptlizenz vorhanden. Kein geeigneter erster SSO-Pilot: Einbenutzermodell und verschlüsselte Daten-/Mobilzugänge erfordern bewusste Fachentscheidung.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | größerer Umbau | 3–6 | Container mit SQLCipher/Poppler/LibreOffice bauen; Schlüssel nur aus geschütztem persistentem Pfad; Timer single instance. |
| Domainwechsel | kleine Anpassung | 1–2 | Proxy- und HTTPS-Einstellungen sowie Mobil-App-Serveradresse prüfen. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | SMTP nicht benötigt; IMAP/CalDAV bleiben getrennte, verschlüsselte Verbindungen. |
| SSO | größerer Umbau | 7–14 | Ein erlaubtes OIDC-Subject auf das bestehende Einzelkonto abbilden und lokale MFA/Notfallzugang erhalten; mehrere gleichberechtigte Personen erfordern neues Besitz-/Rollenmodell. |
| Benutzermigration | größerer Umbau | 3–7 | Keine neue gemeinsame Lehrerbenutzertabelle ins Journal kopieren; Einbenutzerentscheidung vor Migration. |
| Backup/Restore | größerer Umbau | 3–6 | Vorhandene Maintenance-Verfahren mit SQLCipher, Datenkey und Attachments in leerer Umgebung testen; Schlüssel getrennt/offsite sichern. |

Summe appbezogen: **17–35.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** MIT in LICENSE; Copyright-/Lizenzhinweise der gebündelten Editor-/Iconabhängigkeiten mitführen. Vollständiger transitiver/Asset-Abgleich offen.

Gefundene Lizenz-/Hinweisdateien:
- `LICENSE`
- `journal/static/excalidraw/LICENSE.txt`
- `journal/static/icons.LICENSE.txt`
- `journal/static/markdown-editor.LICENSE.txt`

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [requirements.txt:1–11](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/requirements.txt#L1-L11)
- [package.json:1–30](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/package.json#L1-L30)
- [journal/db.py:1–70](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L1-L70)
- [journal/app.py:1–70](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L1-L70)
- [journal/auth.py:1–42](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/auth.py#L1-L42)
- [journal/mobile_api.py:1–70](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L1-L70)
- [journal/integrations.py:1–70](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L1-L70)
- [journal/pdf_preview.py:1–60](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/pdf_preview.py#L1-L60)
- [journal/maintenance.py:1–70](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/maintenance.py#L1-L70)
- [deploy/journal.service:1–24](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/deploy/journal.service#L1-L24)
- [LICENSE:1–21](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/LICENSE#L1-L21)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `journal/db.py`: [L13](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L13), [L14](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L14), [L15](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L15), [L54](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L54), [L73](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L73), [L75](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L75), [L200](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L200), [L268](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L268), [L269](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/db.py#L269)
- `journal/app.py`: [L18](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L18), [L133](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L133), [L159](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L159), [L222](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L222), [L257](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L257), [L368](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L368), [L418](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L418), [L630](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L630), [L856](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L856), [L1112](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L1112), [L1221](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L1221), [L1277](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/app.py#L1277)
- `journal/auth.py`: [L7](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/auth.py#L7), [L30](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/auth.py#L30), [L36](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/auth.py#L36)
- `journal/mobile_api.py`: [L10](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L10), [L75](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L75), [L109](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L109), [L115](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L115), [L120](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L120), [L291](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L291), [L310](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L310), [L313](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L313), [L316](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L316), [L324](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L324), [L399](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L399), [L410](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/mobile_api.py#L410)
- `journal/integrations.py`: [L63](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L63), [L98](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L98), [L121](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L121), [L122](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L122), [L137](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L137), [L139](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L139), [L140](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L140), [L160](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L160), [L166](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L166), [L205](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L205), [L269](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/integrations.py#L269)
- `journal/pdf_preview.py`: [L39](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/pdf_preview.py#L39)
- `journal/maintenance.py`: [L26](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/maintenance.py#L26), [L78](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/maintenance.py#L78), [L80](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/maintenance.py#L80), [L157](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/journal/maintenance.py#L157)
- `LICENSE`: [L10](https://github.com/Bingenberger/SL-Journal/blob/9dd44a584c7b9a35e28c6a362f97c8c9babb4d98/LICENSE#L10)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
