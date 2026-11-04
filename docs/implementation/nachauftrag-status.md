# Nachauftrag N1–N6: Abnahmestand

Stand 4. November 2026. Abnahme in lokalen Ubuntu-24.04.5-VMs (QEMU/KVM, Testaufbau unter `tests/vm/`) mit Test-ACME-CA (Pebble 2.10.1) und Test-DNS (dnsmasq) für `*.schule.test`. **Das ist keine Abnahme auf dem Zielserver.**

Kategorien: **beobachtet** = durch Test/Code belegt · **gemessen** = mit Rohdaten · **geschätzt** · **offen**.

## N1 Release- und Imagepipeline

| Punkt | Stand | Beleg |
| --- | --- | --- |
| GHCR-Images für 10 Apps (11 Images) aus Tag `v0.1.0`, amd64, SBOM (SPDX) und Provenienz (SLSA) | beobachtet | GitHub-Actions-Läufe, `scripts/make_release.py` prüft Label, Architektur und Attestierungen gegen die Registry |
| Plattform-Images (Dashboard, Mail-Relay) aus Plattform-Tags | beobachtet (rc1, rc2) | `.github/workflows/release-images.yml` |
| Signiertes Bundle, Manipulation abgewiesen (Digest, neu gehashte Fassung ohne Signatur, abweichender Registry-Digest) | beobachtet | `evidence/n1-release-verification.log` |
| Lizenzprüfung A0 | **offen** | im Bundle als `open` geführt, nicht als bestanden |
| gswb-Restore-Nachweis aus den früheren Paketen | **offen** im Manifest; Plattform-Restore inzwischen belegt (N4) | |

Die Images auf GHCR sind öffentlich (abgeleitet von den öffentlichen Repositories). Wegen A0 ist das eine Entscheidung des Auftraggebers.

## N2 Konfiguration und Domainzuordnung

| Punkt | Stand | Beleg |
| --- | --- | --- |
| `platform.toml` mit Schema, Assistent, Prüfung (doppelte Namen, Verwaltungsdomain, IP, ACME-Modus) | beobachtet | `tests/test_production.py` |
| Alle abgeleiteten URLs aus der Konfiguration, keine `localhost`-Konstanten im Produktionspfad | beobachtet | Test `test_render_overrides_use_configured_hostnames_and_fixed_proxy` |
| Keine App brennt ihre öffentliche URL beim Build ein | beobachtet (keine `ARG`/`VITE_`/`NEXT_PUBLIC_` in den Dockerfiles) | |

## N3 DNS-Prüfung und Zertifikate

| Punkt | Stand | Beleg |
| --- | --- | --- |
| ACME über HTTP-01 je Hostname, nur für DNS-geprüfte Namen | beobachtet (Pebble) | `evidence/n3-partial-readiness.log` |
| Teilbereitschaft: 3 Hostnamen ohne DNS → nachgezogen → aktiv | beobachtet | ebd. |
| Domainwechsel mit Elternlink, `BASE_URL` und Konfiguration; erzwungener Rückfall | beobachtet | `evidence/n3-domain-change-rollback.log` |
| Mailinhalt mit neuer Domain, QR-Code-Inhalt | **offen** (nur abgeleitete `BASE_URL` geprüft) | |
| Let's Encrypt Staging/Produktion, Erreichbarkeit aus dem Internet | **offen** (nur auf dem Zielserver prüfbar) | |

## N4 `install.sh apply`

| Punkt | Stand | Beleg |
| --- | --- | --- |
| Leeres Ubuntu 24.04 → Docker 29.1.3 aus dem offiziellen Repo (Schlüssel-Fingerprint geprüft), ufw, 10 Apps, Caddy, Relay/Sink, Dashboard, systemd-Units | beobachtet | Installationsprotokolle in der VM |
| Zweiter Lauf ändert nichts (68 Dateien und alle Container-IDs gleich, 2,4 s) | beobachtet | `evidence/n4-second-run-noop.log` |
| Fortsetzung am letzten nachgewiesenen Schritt nach Fehlschlag | beobachtet (mehrfach: `host`, `infrastructure`, `routes`) | Zustandsdatei-Ereignisse |
| Fortsetzung nach hartem Abbruch (`SIGKILL` im Schritt `apps`) | beobachtet | `evidence/n4-interrupt-resume.log` |
| Fremdbestand (Docker und nginx) → Abbruch, nichts verändert | beobachtet | `evidence/n4-foreign-host-abort.log` |
| Negativ- und Isolationsprüfungen aller 10 Apps über TLS | beobachtet | `evidence/n4-verify-all-apps.json` |
| Neustart des Hosts → alles aktiv | beobachtet | `evidence/n4-reboot-and-idle.log` |
| Backup aller Apps plus Plattform, Offsite-Kopie, isolierte Restore-Probe | beobachtet | `evidence/n4-backup-restore-probe.log` |
| Restore in leere VM (frisches Ubuntu ohne Docker): Plattformsicherung, apply, 10 App-Restores, alle Hostnamen aktiv, alter Elternlink gültig, Zeilen gleich | beobachtet | `evidence/n4-restore-empty-vm.log` |
| Images 8,43 GB; Leerlauf aller Container rund 1,6 GB RAM (VM, Momentaufnahme) | **gemessen** (VM, nicht Zielserver) | `evidence/n4-reboot-and-idle.log` |
| 16 GB / 4 vCPU / 250 GB | **geschätzt** (unverändert) | |

## N5 Dashboard

| Punkt | Stand | Beleg |
| --- | --- | --- |
| Domains (mit Vorschau und Bestätigung), Zertifikate, Mail (Passwort nur schreibbar, Testversand), Sicherungen, Updates, Lebenszyklus | beobachtet in Unit-Tests | `tests/test_dashboard_admin.py` |
| Feste Aktionen mit Parameterschema, HMAC, Nonce, Audit | beobachtet | `tests/test_production_services.py` |
| Einrichtungsmodus ohne Admin (keine Anmeldung möglich) | beobachtet (Test und VM) | |
| Bedienung der Oberfläche in der VM mit echtem Admin | **offen** (`admin-setup` braucht ein Terminal) | |
| Angriffsflächen | dokumentiert | `docs/betrieb/dashboard.md` |

## N6 Datenübernahme

| Punkt | Stand | Beleg |
| --- | --- | --- |
| Inventur und Export (nur Standardbibliothek, lesend, verschlüsselt) | beobachtet | `scripts/altserver/` |
| losverkauf (nativ, SQLite): Zeilen vollständig, Secrets übernommen, **alter Elternlink gültig** | beobachtet | `evidence/n6-import-vm.log` |
| fahrradausbildung (Compose, PostgreSQL 16): Alembic 0007 → 0008, Zeilen vollständig, Eigentümer App-Rolle | beobachtet | ebd. |
| schulhelfer (nativ, `create_all`): Migration verweigert, Rückfall auf Sicherung | beobachtet; **Adoptionspfad offen** (App-Code) | ebd. |
| schulwissen, leseflux, abgen, gswb, zackboing, kompetenz-manager, grundschultafel | **nicht getestet** | |
| Runbook | dokumentiert | `docs/betrieb/umzug.md` |

## In der Abnahme gefundene und behobene Fehler

- Caddy-Konfiguration als Einzeldatei-Mount: Änderungen waren nach dem atomaren Ersetzen unsichtbar.
- Dynamische App-Adressen konnten die feste Proxy-Adresse belegen.
- Domainwechsel prüfte gegen die alten Namen und fiel deshalb immer zurück.
- Gehaltene Docker-Pakete galten als nicht installiert (zweiter Lauf scheiterte).
- Docker-Bridge `172.17/16` konnte SSH-Antworten verschlucken; jetzt `10.232/16`.
- SSH-Port-Erkennung bei socket-aktiviertem sshd.
- Eine einzelne CDN-Zeitquelle lag eine Stunde daneben; jetzt Median aus drei Quellen.
- DNS-Vergleich Tupel gegen Liste.
- Live-`tar` scheiterte an sich ändernden Dateien; jetzt kurzes Pausieren.
- Wiederhergestellte Volumes gehörten `root`.
- Mitgenommene Secrets wurden nicht in den Secretstore übernommen.
- Das Dashboard startete ohne Admin nicht.

## Offen und blockiert (Zusammenfassung)

1. A0 Lizenzen; Sichtbarkeit der GHCR-Pakete.
2. Zielserver: Let's Encrypt, Erreichbarkeit aus dem Internet, echter SMTP-Anbieter, Messungen nach Abschnitt 12.
3. N6: Adoptionspfad schulhelfer; Import für 7 weitere Apps nicht getestet.
4. N5: Oberfläche in der VM mit echtem Admin bedienen.
5. Netzänderungen bei bestehenden Installationen (z. B. Proxy-Adressbereich) verlangen das Stoppen der angehängten Apps; kein automatischer Migrationspfad.
6. schulwissen-Datenbank ohne Speicherlimit (bereits in der Standalone-Compose).
