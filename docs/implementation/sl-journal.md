# Schulleitungsjournal (sl-journal) – Plattform-Integration

Stand: 5. November 2026. Repository `Bingenberger/SL-Journal` (öffentlich), Basis `9dd44a5` (= GitHub `main`).
App-Kennung in der Plattform: `sl-journal` (Kennungen und Image-Namen sind klein geschrieben;
`.work/apps/sl-journal` verweist auf den Checkout `SL-Journal`).

| Commit | Inhalt |
| --- | --- |
| `9dd44a5` | Ausgangsstand |
| `424bd10` | Plattform-Integration (getestet, `patches/sl-journal/changes.patch`) |
| `25e7090` | verwalteter Release-Workflow |

## Nachweise (lokal, 2026-11-05)

| Prüfung | Ergebnis |
| --- | --- |
| 297 vorhandene + 6 neue Tests, lokal und im `tests`-Image (read-only, ohne Netz, mit Poppler/Tesseract/LibreOffice) | 303/303 |
| Office→PDF, Texterkennung (deu) und PDF-Vorschau im read-only-Container, UID 10001 | 0,8 s; „Elterngespräch Klasse 4a“ fehlerfrei erkannt; PNG |
| Plattform-Override + App-Compose (Compose v2.40.3), Fernet-Schlüssel aus der neuen Secret-Art | `migrate` ok; app + worker healthy; `/api/v1/me` 401, `/` 302 → `/setup`; ohne HTTPS 400; `init` nennt die Plattform-Adresse |
| Export-Werkzeug (nachgebauter Altbestand nach Server-Anleitung) | Abbruch bei laufendem `journal.service`; `master.key` aus `/etc` als Secret; Instanz ohne App-Backups |

Nicht geprüft: echte IMAP-/CalDAV-Konten, Import einer echten verschlüsselten Instanz auf dem
Server, Release-Image aus GitHub Actions, Android-App gegen die Plattform-Adresse.

## Plattform-Erweiterungen dafür

- Secret-Art `fernet:<name>`: erzeugt einen gültigen Fernet-Schlüssel (32 Zufallsbytes, base64url);
  ein Import ersetzt ihn durch den mitgebrachten Originalschlüssel.
- Export-Werkzeug: `secret_files` (Schlüsseldateien außerhalb der Daten), `requires_stopped`,
  `env_defaults`, Ausschlüsse je Quellverzeichnis.

## Entscheidung: Netzfreigabe (2026-11-05)

Das Journal ist auf der Plattform **öffentlich** erreichbar. Die VPN-Beschränkung der mitgelieferten
nginx-Vorlage stammte aus dem bisherigen Betrieb (LXC-Container auf einem Heimserver hinter einem
externen Reverse-Proxy) und entfällt. Schutz: HTTPS, Passwort (≥ 14 Zeichen), TOTP und
serverseitige Begrenzung von Fehlversuchen. Eine Beschränkung auf Adressbereiche ist nicht nötig.
