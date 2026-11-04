# Checkliste: Tag der Bereitstellung

Für den echten Server. Alles hier wurde in einer lokalen Ubuntu-24.04-VM mit Test-CA (Pebble) und Test-DNS geprüft. Was nur auf dem echten Server prüfbar ist, steht am Ende unter „Offen“.

## 1. Server beim Hoster bestellen

- Ubuntu Server 24.04 LTS, amd64, **leer** (ohne vorinstalliertes Docker, nginx, Plesk o. Ä.)
- Ausgangsschätzung, nicht gemessen: 16 GB RAM, 4 dedizierte vCPU, 250 GB SSD. Gemessen sind bisher nur die Images: `IMAGES_TOTAL` entpackt (Messung in der Test-VM), davon `abgen-pdf` allein 4,09 GB.
- Feste öffentliche IPv4, IPv6 optional
- Eingehend erreichbar: 22 (oder Ihr SSH-Port), 80, 443. Eine Firewall des Hosters entsprechend öffnen.
- Ausgehend: HTTPS zu `download.docker.com`, `ghcr.io`, `pypi.org`, `acme-v02.api.letsencrypt.org` und Ihrem SMTP-Anbieter

## 2. DNS beim Provider (vorab, TTL niedrig, z. B. 300 s)

Je Hostname **ein A-Eintrag** auf die Server-IPv4. Einen AAAA-Eintrag nur setzen, wenn Sie IPv6 in der Konfiguration angeben. Ein falscher AAAA-Eintrag lässt Let's Encrypt scheitern.

| Zweck | Beispiel |
| --- | --- |
| Verwaltung (Dashboard) | `verwaltung.schule.example` |
| je App | `wissen.schule.example`, `tafel.schule.example`, … |

Fehlende Einträge blockieren die Installation nicht. Die betroffenen Apps stehen auf „DNS ausstehend“ und werden später aktiviert (siehe 6).

## 3. Plattform holen und Vertrauensschlüssel prüfen

```sh
sudo -i
git clone https://github.com/Bingenberger/schulplattform.git /opt/schulplattform
cd /opt/schulplattform && git checkout v0.1.0
```

Release-Bundle (`releases/0.1.0`) und Vertrauensschlüssel getrennt beziehen. Vergleichen Sie den Fingerabdruck auf einem **anderen Weg** (z. B. telefonisch oder aus dieser Dokumentation auf einem anderen Gerät):

```sh
.venv/bin/python -c "from schulplattform.release_bundle import key_fingerprint as f; print(f('release-keys/schulplattform-release.pub'))"
# erwartet: SHA256:f43e8cabe5a101e8463b2f9a4601cc5bcb9fd15ac0dbabee662072a0fc6b3fd7
```

## 4. Prüfen und konfigurieren

```sh
./install.sh preflight          # nur lesend; muss "blockers": [] zeigen
./install.sh configure          # Fragen auf dem Terminal: Domains, Let's-Encrypt-Kontakt, IP, SMTP, Backup
./install.sh smtp-password      # nur bei SMTP mit Anmeldung; Eingabe unsichtbar
./install.sh plan --bundle releases/0.1.0 --trusted-key release-keys/schulplattform-release.pub
```

`plan` zeigt die offenen Abnahmepunkte des Release, etwa die Lizenzprüfung A0.

Beginnen Sie mit `acme_environment = "staging"`.

## 5. Installieren

```sh
./install.sh apply --bundle releases/0.1.0 --trusted-key release-keys/schulplattform-release.pub
```

Erwartet: Am Ende eine Tabelle je App mit `aktiv`, `zertifikat-ausstehend` oder `dns-ausstehend` samt dem fehlenden DNS-Eintrag.

Ein zweiter Aufruf ändert nichts. Ein abgebrochener Aufruf setzt beim letzten nachgewiesenen Schritt fort.

## 6. Nach der Installation

```sh
./install.sh admin-setup              # persönlicher Plattform-Admin, Passwort + TOTP
./install.sh app-setup schulwissen    # Erstzugang je App, nur bei Bedarf
./install.sh reconcile                # nachgezogene DNS-Einträge aktivieren (läuft auch stündlich per Timer)
./install.sh status
```

Wenn alle Hostnamen unter **Staging** `aktiv` sind:
1. In `/etc/schulplattform/platform.toml` `acme_environment = "production"` setzen.
2. `./install.sh apply --bundle … --trusted-key … --reconfigure` ausführen.
3. Mit `./install.sh reconcile` und `./install.sh status` prüfen, dass Zertifikate von Let's Encrypt ausgestellt sind.

Den Backup-Schlüssel `/var/lib/schulplattform/secrets/backup-key` **außerhalb des Servers** verwahren.

## 7. Offen (nur auf dem echten Server prüfbar)

- echtes Let's Encrypt (Staging und Produktion), Rate-Limits
- Erreichbarkeit von Port 80/443 aus dem Internet (die VM prüfte nur von innen)
- Zustellung über den echten SMTP-Anbieter
- Messungen nach Abschnitt 12 des Hauptauftrags (Leerlauf, zehn aktive Personen, Hintergrundlast)
