# gswb

Prüfdatum: 2026-11-01T10:12:23.839415+00:00; Branch `main`; vollständiger Commit `7c2875b0439395487431ffaf543b0bbb3f37a8bf`. Zugriff: available. Isolierter Checkout; keine Produktivänderung.

## Beobachtet – Code und Betrieb

- **Stack:** Flask >=3,<4; Gunicorn >=22,<24; SQLite; rapidfuzz; google-genai.
- **Dienste:** SQLite, JSON-Reviewverzeichnis, Audio/Bilder und Uploads; keine Benutzer-DB.
- **Produktionsbetrieb:** Appfactory vorhanden; Produktions-Gunicorn ergänzen, kein Dockerfile. Bekannter SECRET_KEY im Factory-Default und festgelegte Pfade; Env-/Secret-Vertrag ergänzen.
- **Frontend/Reproduzierbarkeit/Plattform:** Keine Benutzeridentität für Suche nötig; Proxy-Anmeldung nur für Redaktion sachgerecht, wenn direktes Backend geschlossen und alle Schreibpfade erfasst. Schema-Init bei Start, keine nummerierten Migrationen.
- **Persistenz/Migration:** SQLite-Wortbestand, data/import_words, static/images/audio/uploads; Schreibproben können personenbezogen sein.
- **Externe Abhängigkeiten/Self-Hosting:** Gemini/Vertex für Handschriftanalyse und Generatoren; HANDWRITING_MODE=mock ersetzt die Funktion nur durch Testantwort, kein gleichwertiges lokales OCR. Wörterbuchsuche ohne KI lokal..
- **Schwere Verarbeitung:** Externe Bild-/Handschriftanalyse und Wörtergenerierung; fuzzy Suche lädt Wörterliste in Prozesscache; Audio-TTS-Skripte extern.

## Beobachtet – Identität und Daten

- **Login, Rechte und Sessions:** Im geprüften Blueprint keine Anmeldung/Rollen für /review und verändernde Review-POSTs; öffentliche Wörterbuch-API mit CORS *.
- **Öffentliche/alternative Zugänge:** /, /search, /word, /api/autocomplete und /api/word öffentlich; /review muss geschützt, /writing-check limitiert und datenschutzgerecht gestaltet werden.
- **Mail/Konfiguration:** Keine SMTP-Versandstelle im geprüften Pythoncode gefunden.
- **Hauptbefund:** Vollständig gleichwertiges Self-Hosting der KI-Funktionen derzeit nicht nachgewiesen. Ungeschützte Redaktion ist ein vorrangiger Befund.

„Nicht gefunden“ bezieht sich auf die geprüften Source-/Manifestdateien und ist kein vollständiger Negativbeweis. Fundstellenindex und deklarierte Paketversionen stehen in [source-inventory.json](../evidence/source-inventory.json). Deklarierte Bandbreiten sind keine gemessenen Laufzeitversionen.

## Geschätzt – konkrete Integrationsschritte

| Bereich | Kategorie | Arbeitstage | Änderung/Begründung |
| --- | --- | ---: | --- |
| Containerbetrieb | kleine Anpassung | 2–4 | Nicht-Root-Gunicorn-Image, Pfad-/Secret-Env und Readiness; Schreibrechte auf Datenverzeichnisse begrenzen. |
| Domainwechsel | kleine Anpassung | 1–2 | Kanonische URL konfigurierbar machen; API-CORS nur bei absichtlich öffentlichem Lesemodus *, Bearbeitung same origin. |
| Zentraler Mailversand | bereits vorhanden | 0–0.5 | Mail nicht erforderlich. |
| SSO | kleine Anpassung | 3–6 | Redaktion hinter OIDC-fähige Policy/BFF oder nativen Authlib-Schutz; alle /review-POSTs und CSRF serverseitig prüfen. |
| Benutzermigration | bereits vorhanden | 0–1 | Kein lokales Benutzerkonto zu migrieren; für Redaktion Subject-Zulassung, keine fingierte Kontenintegration. |
| Backup/Restore | kleine Anpassung | 2–4 | SQLite-Backup plus JSON, Audio/Bilder und Uploads; Schreibproben kurz aufbewahren und aus öffentlichem static-Pfad verschieben. |

Summe appbezogen: **8–17.5 Personentage**. Annahmen: eine Schule/24 Lehrkräfte/max. 10 gleichzeitige Personen, ein erfahrener Entwickler, keine neue Fachfunktion, synthetische Abnahmedaten, zentrale Infrastruktur bereits da. Vertrauensgrad mittel für gelesenen Code, niedrig für nicht ausgeführte native/Browser-/Migrationspfade. Lizenzfreigabe und Plattformarbeit nicht eingerechnet; Aufwände überlappen teilweise und sind kein Liefertermin.

## Lizenz und gemeinsame Distribution

**Beobachtet/offen:** Keine projektweite Lizenzdatei gefunden. Gemeinsame Weitergabe des Anwendungscodes ist damit nicht freigegeben; Rechteinhaberfreigabe/Lizenz ergänzen. Vorhandene Einzellizenzen von Assets ersetzen keine Hauptlizenz.

Gefundene Lizenz-/Hinweisdateien:
- Keine benannte Lizenzdatei im untersuchten Baum gefunden.

Für Abhängigkeiten: vollständige installierte SBOM mit Version/Hash/Lizenz und tatsächlichen Assets vor Imagefreigabe erzeugen. Bibliothekslizenz und Assetlizenz getrennt behandeln; private Vorlagen, Logos, Unterschriften, Texte und Medien nicht pauschal mitverteilen. [Lizenzübersicht](../licenses.md).

## Commitgebundene Belege

- [requirements.txt:1–5](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/requirements.txt#L1-L5)
- [grundschul_woerterbuch/__init__.py:1–60](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L1-L60)
- [grundschul_woerterbuch/db.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/db.py#L1-L70)
- [grundschul_woerterbuch/routes.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L1-L70)
- [grundschul_woerterbuch/repository.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/repository.py#L1-L70)
- [grundschul_woerterbuch/services/handwriting_service.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/services/handwriting_service.py#L1-L70)
- [grundschul_woerterbuch/services/json_review_service.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/services/json_review_service.py#L1-L70)
- [gemini-tts-wortliste.py:1–70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/gemini-tts-wortliste.py#L1-L70)

Weitere Fundstellen mit genauen Zeilennummern: [Quellinventar](../evidence/source-inventory.json). Die Links beziehen sich auf den geprüften Commit; private Links benötigen GitHub-Zugriff.

## Gemessen und offen

Ausgeführte und fehlende Tests sind zentral in [tests.md](../tests.md) dokumentiert. Für diese App gibt es keine repräsentative Kapazitätsmessung, sofern dort nicht ausdrücklich genannt. Offen bleiben vollständiger Produktionsimage-Build, ARM64-Build, Header-/CSRF-/CORS-Negativtests über den Zielproxy, Abgleich sämtlicher Export-/Löschpfade und vollständiger Restore samt Dateidaten im Plattformverbund. Keine App erhält aufgrund dieser Codeprüfung eine belastbare Maximalnutzerzahl.

## Ergänzende genaue Codeanker

- `grundschul_woerterbuch/__init__.py`: [L27](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L27), [L31](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L31), [L41](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L41), [L45](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L45), [L47](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L47), [L49](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/__init__.py#L49)
- `grundschul_woerterbuch/db.py`: [L100](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/db.py#L100), [L101](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/db.py#L101), [L107](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/db.py#L107), [L108](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/db.py#L108)
- `grundschul_woerterbuch/routes.py`: [L65](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L65), [L66](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L66), [L70](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L70), [L74](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L74), [L75](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L75), [L120](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L120), [L128](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L128), [L138](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L138), [L290](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L290), [L292](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L292), [L298](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L298), [L299](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/routes.py#L299)
- `grundschul_woerterbuch/repository.py`: [L9](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/repository.py#L9), [L10](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/repository.py#L10), [L13](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/repository.py#L13), [L326](https://github.com/Bingenberger/gswb/blob/7c2875b0439395487431ffaf543b0bbb3f37a8bf/grundschul_woerterbuch/repository.py#L326)

Aufgelöste Lockfileversionen und Datei-SHA256: [lock-inventory.json](../evidence/lock-inventory.json). Das sind beobachtete Lockdaten, keine erfolgreich gebaute Laufzeit aller Plattformen.
