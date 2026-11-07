# Schulplattform

Die Schulplattform installiert zehn eigenständige Schul-Apps gebündelt auf **einem** selbst gehosteten Linux-Server und macht sie zentral wartbar:

- Installation mit einem Befehl
- je App eine eigene Subdomain mit automatischem TLS-Zertifikat (Let's Encrypt)
- zentrales Dashboard mit Domains, Zertifikaten, Mailversand, Sicherungen und Updates
- verschlüsselte Sicherung und Wiederherstellung
- Werkzeug für den Umzug vom bisherigen Server

Jede App bleibt ein eigenes Repository mit eigener `docker-compose.yml` und lässt sich auch **ohne** Plattform betreiben. Die Plattform legt nur eine Override-Datei darüber.

| App | Zweck | Repository | Release-Image |
| --- | --- | --- | --- |
| gswb | Grundschul-Wörterbuch (öffentliche Suche, Redaktion) | [gswb](https://github.com/Bingenberger/gswb) | `ghcr.io/bingenberger/gswb` |
| schulwissen | Schulinterne Wissens- und Beschlussdatenbank | [schulwissen](https://github.com/Bingenberger/schulwissen) | `ghcr.io/bingenberger/schulwissen` |
| zackboing | Quiz und Klassenspiele | [zackboing](https://github.com/Bingenberger/zackboing) | `ghcr.io/bingenberger/zackboing` |
| schulhelfer | Helferlisten für Schulfeste | [schulhelfer](https://github.com/Bingenberger/schulhelfer) | `ghcr.io/bingenberger/schulhelfer` |
| losverkauf | Losverkauf mit Elternanmeldung | [losverkauf](https://github.com/Bingenberger/losverkauf) | `ghcr.io/bingenberger/losverkauf` |
| grundschultafel | Digitale Tafel für Lehrkräfte | [grundschultafel](https://github.com/Bingenberger/grundschultafel) | `ghcr.io/bingenberger/grundschultafel` |
| fahrradausbildung | Radfahrausbildung mit Posten-App | [fahrradausbildung](https://github.com/Bingenberger/fahrradausbildung) | `ghcr.io/bingenberger/fahrradausbildung` |
| leseflux | Leseflüssigkeitstraining | [leseflux](https://github.com/Bingenberger/leseflux) | `ghcr.io/bingenberger/leseflux` |
| kompetenz-manager | Kompetenzbeobachtung und Schülerakte | [kompetenz-manager](https://github.com/Bingenberger/kompetenz-manager) | `ghcr.io/bingenberger/kompetenz-manager` |
| abgen | Arbeitsblatt-Editor (gemeinsames Bearbeiten, PDF) | [abgen](https://github.com/Bingenberger/abgen) | `ghcr.io/bingenberger/abgen`, `…/abgen-pdf` |
| fundkiste | Fundsachen mit Foto und QR-Code | [fundkiste](https://github.com/Bingenberger/fundkiste) | `ghcr.io/bingenberger/fundkiste` |
| schuleva | Schulbefragungen mit TANs und Auswertung | [schuleva](https://github.com/Bingenberger/schuleva) | `ghcr.io/bingenberger/schuleva` |
| schulkasse | Klassen- und Schulkassen | [schulkasse](https://github.com/Bingenberger/schulkasse) | `ghcr.io/bingenberger/schulkasse` |
| schulanmeldung | Schulanmeldung und Sekretariat (SL-Office) | privat | `ghcr.io/bingenberger/schulanmeldung` |
| sl-journal | Schulleitungsjournal (verschlüsselt) | [SL-Journal](https://github.com/Bingenberger/SL-Journal) | `ghcr.io/bingenberger/sl-journal` |
| bildergalerie | KI-Bilder (CC0) mit Suche und JSON-API für die Tafel | [bildergalerie](https://github.com/Bingenberger/bildergalerie) | `ghcr.io/bingenberger/bildergalerie` |

Infrastruktur auf dem Server:
- Caddy als Proxy mit ACME
- ein Postfix-Mail-Relay (`schulplattform-relay`)
- das Dashboard (`schulplattform-dashboard`)
- ein lokaler Steuerdienst; nur er hat Docker-Zugriff

## Installation auf einem neuen Server

### Voraussetzungen

- **Ubuntu Server 24.04 LTS, amd64, leer.** Kein vorinstalliertes Docker, nginx, Apache oder Datenbankdienst; der Installer bricht sonst ab, statt etwas zu überschreiben.
- root-Zugang per SSH, Internetzugang (HTTPS) zu `github.com`, `ghcr.io`, `download.docker.com`, `pypi.org` und Let's Encrypt
- feste öffentliche IPv4-Adresse; eingehend erreichbar sind 22, 80 und 443
- je App ein DNS-A-Eintrag auf diese Adresse, dazu einer für die Verwaltungsdomain. Fehlende Einträge können nachgereicht werden.

**Vorab installieren muss man nichts.** Ein Standard-Ubuntu-24.04 (geprüft am offiziellen Cloud-Image) enthält bereits `git`, `python3` (3.12), `curl`, `gpg`, `ufw` und `tar`.

`install.sh` richtet beim ersten Aufruf selbst ein:
- `python3-venv` und eine Python-Umgebung aus `requirements-host.lock`, mit Hash-Prüfung
- Docker 29.1.3 samt Compose-Plugin aus der offiziellen Docker-Paketquelle; der Fingerabdruck des Repository-Schlüssels wird geprüft
- die Firewall (`ufw`)
- die Systemdienste

Nur bei stark reduzierten Images ohne `git` vorher `apt install git` ausführen.

### So kommt `install.sh` auf den Server

Das Repository ist öffentlich. Auf dem Server als root:

```sh
git clone https://github.com/Bingenberger/schulplattform.git /opt/schulplattform
cd /opt/schulplattform
```

Ohne git geht es auch so:

```sh
curl -fsSLO https://github.com/Bingenberger/schulplattform/archive/refs/heads/main.tar.gz
```

Danach entpacken.

Der Branch `main` enthält den Code des aktuellen Release, dessen **signiertes Bundle** (`releases/0.3.0`) und den öffentlichen Prüfschlüssel (`release-keys/schulplattform-release.pub`). Vergleichen Sie den Fingerabdruck des Schlüssels auf einem zweiten Weg, etwa telefonisch oder auf einem anderen Gerät:

```sh
python3 -c "import hashlib,base64;k=open('release-keys/schulplattform-release.pub').read().split('\n')[1];print('SHA256:'+hashlib.sha256(base64.b64decode(k)[-32:]).hexdigest())"
# erwartet: SHA256:f43e8cabe5a101e8463b2f9a4601cc5bcb9fd15ac0dbabee662072a0fc6b3fd7
```

Das Release fixiert jedes Image über Version **und** Digest. Ein verändertes Bundle oder Image wird abgewiesen.

### Installieren

```sh
./install.sh preflight      # nur lesend; muss "blockers": [] melden
./install.sh configure      # Assistent: Domains je App, Verwaltungsdomain, Let's-Encrypt-Kontakt, IP, SMTP, Backup
./install.sh smtp-password --bundle releases/0.3.0 --trusted-key release-keys/schulplattform-release.pub  # nur bei SMTP mit Anmeldung (verdeckte Eingabe)
./install.sh apply --bundle releases/0.3.0 --trusted-key release-keys/schulplattform-release.pub
./install.sh admin-setup    # persönlicher Plattform-Admin mit TOTP
./install.sh app-setup APP  # Erstzugang je App, bei Bedarf
```

Beginnen Sie mit `acme_environment = "staging"` und stellen Sie auf `production` um, wenn alle Hostnamen aktiv sind.

`apply` ist wiederholbar: Ein zweiter Lauf ändert nichts, und ein abgebrochener Lauf setzt am letzten geprüften Schritt fort. Apps, deren DNS-Eintrag noch fehlt, stehen auf „DNS ausstehend“ und werden mit `./install.sh reconcile` (läuft auch stündlich) aktiviert.

Ausführliche Checkliste: [docs/betrieb/bereitstellung.md](docs/betrieb/bereitstellung.md)

## Betrieb

| Befehl | Zweck |
| --- | --- |
| `./install.sh status` | Zustand je App: DNS, Zertifikat, aktiv |
| `./install.sh reconcile [--app APP]` | DNS erneut prüfen, Zertifikate holen |
| `./install.sh domain-change APP HOST` | Domain wechseln, mit automatischem Rückfall |
| `./install.sh start\|stop APP` | App starten oder stoppen (Daten bleiben) |
| `./install.sh backup --all` | Plattform und alle Apps sichern, verschlüsselt, mit Kopie ins externe Ziel |
| `./install.sh restore-probe APP` | Sicherung isoliert prüfen |
| `./install.sh restore APP ARCHIV --confirm-replace` | App-Daten wiederherstellen |
| `./install.sh restore-platform ARCHIV --confirm-replace` | Server nach Totalausfall neu aufbauen (vor `apply`) |
| `./install.sh youtube-key` | YouTube-Suche der Tafel ein-/ausschalten ([Galerie, Wörterbuch und YouTube](docs/betrieb/bereitstellung.md#bildergalerie-wörterbuch-und-youtube-suche-grundschultafel)) |
| `./install.sh gallery-ai-key DATEI\|--off` | KI-Metadaten der Bildergalerie ein-/ausschalten ([Bildergalerie](docs/betrieb/bereitstellung.md#bildergalerie-app-bildergalerie)) |

Das Dashboard unter der Verwaltungsdomain zeigt dasselbe und erlaubt Domains, Mail, Sicherungen und Lebenszyklus (ausblenden, stoppen, deinstallieren, Daten löschen) über fest definierte Aktionen.

Weitere Dokumentation:
- Privilegien und Angriffsflächen: [docs/betrieb/dashboard.md](docs/betrieb/dashboard.md)
- Updates und Rollback: [UPGRADE.md](UPGRADE.md)

## Umzug vom bisherigen Server

`scripts/altserver/schulplattform_altserver.py` läuft auf dem Altserver ausschließlich lesend: Es inventarisiert und exportiert verschlüsselt.

Auf dem neuen Server:
1. `./install.sh import-key` legt den Transferschlüssel an.
2. `./install.sh import APP ARCHIV --dry-run` prüft das Archiv.
3. `./install.sh import APP ARCHIV --confirm-replace` übernimmt die Daten.

Runbook: [docs/betrieb/umzug.md](docs/betrieb/umzug.md)

## Stand und Grenzen

Release 0.1.0 ist in lokalen Ubuntu-24.04-VMs mit Test-CA und Test-DNS abgenommen. 0.1.1 korrigiert nur die interaktiven Konsolenabfragen (`configure`, `admin-setup`, `app-setup`, `smtp-password`); App-Images sind unverändert: [docs/implementation/nachauftrag-status.md](docs/implementation/nachauftrag-status.md).

0.2.0 (5. November 2026) ergänzt fünf Apps: fundkiste, schuleva, schulkasse, schulanmeldung und sl-journal. Die zehn bisherigen App-Images sind unverändert. Die neuen Apps sind lokal mit Docker Compose und der Plattform-Konfiguration geprüft, aber noch nicht auf dem Server. Aktualisieren: [docs/betrieb/bereitstellung.md](docs/betrieb/bereitstellung.md#aktualisieren-auf-ein-neues-release). 0.2.1 korrigiert die Admin-Anmeldung von losverkauf (403 im Browser, losverkauf 0.1.1). 0.2.2 bringt schulhelfer 0.1.1, das die mit `create_all` angelegte Altdatenbank nach Strukturprüfung übernimmt. 0.2.3 bringt grundschultafel 0.1.1: Bildergalerie und YouTube-Suche lassen sich einschalten ([Anleitung](docs/betrieb/bereitstellung.md#bildergalerie-wörterbuch-und-youtube-suche-grundschultafel)); außerdem Korrekturen an Sicherung und Altserver-Export aus den Umzügen. 0.2.4 bringt grundschultafel 0.1.2: eingebettete YouTube-Videos zeigen nicht mehr „Fehler 153“. 0.2.5 bringt grundschultafel 0.1.3 (Login-Schutz je Gerät, robusteres Speichern) und schulhelfer 0.1.2 (neue Optik, keine CDN-Abrufe). 0.3.0 (7. November 2026) ergänzt die App **bildergalerie** (0.1.1, JSON-API v1, kein Standardkonto) und bringt grundschultafel 0.1.4 (Wörterbuch in Blitzlesen/Silbenrutsche, Galerie über die API, Vorlagen und Klassenwerkzeuge) sowie gswb 0.1.1 (Wortlisten-API, korrekte Bildtypen); die Tafel nutzt eigene Galerie und eigenes Wörterbuch automatisch ([Anleitung](docs/betrieb/bereitstellung.md#bildergalerie-wörterbuch-und-youtube-suche-grundschultafel)).

Offen sind:
- die Abnahme auf dem echten Server (Let's Encrypt, Erreichbarkeit, SMTP-Anbieter, Lastmessungen)
- die Lizenzprüfung (A0)
- der Übernahmeweg für alte schulhelfer-Datenbanken

Es gibt kein Single Sign-on, keine zentrale Benutzersperrung und keinen zentralen Logout; die Apps behalten ihre eigenen Anmeldungen.

## Entwicklung

```sh
python3 scripts/checkout_apps.py          # App-Repositories nach .work/apps/ (ignoriert)
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q tests
```

- **Plattformcode:** `schulplattform/` mit Katalog, Konfiguration, Stack, Routing, Backups, Installer, Dashboard und Steuerdienst. Die Schemas liegen in `schemas/`, der Release-Builder in `scripts/make_release.py`.
- **App-Änderungen:** Die Plattform-bezogenen Änderungen der App-Repos sind in `patches/` nachvollziehbar (`patches/index.json`).
- **VM-Abnahme:** `tests/vm/` startet QEMU/KVM im Container mit Pebble und Test-DNS (`prepare.sh`, `vm.py`, `sync.sh`).
- **Lokaler Pilot:** Der frühere Zehn-App-Pilot (`./install.sh pilot-up --state-dir .work/pilot-vN --apps …`) bleibt für die Entwicklung erhalten. Berichte je App stehen in [docs/implementation/](docs/implementation/).

Aufträge und Audit:
- [Umsetzungsauftrag](Coding_Agent_Umsetzungsauftrag_Schulplattform.md)
- [Nachauftrag](Coding_Agent_Nachauftrag_Installation_Domains.md)
- [Audit](docs/platform-audit/)
