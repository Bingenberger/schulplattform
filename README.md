# Schulplattform – Umsetzung in Arbeit

Die Plattform bündelt eigenständige Apps für einen selbst gehosteten Schulserver.
Maßgeblich sind der [Auftrag](Coding_Agent_Umsetzungsauftrag_Schulplattform.md) und
der [Umfangsbeschluss](docs/platform-audit/scope-decision.md).

**Aktuell ist der lokale Zehn-App-Pilot einschließlich abgen geprüft.** Die vollständige
Installation auf leerem Ubuntu 24.04 sowie Produktions- und Releaseabnahme sind noch offen.
[Umsetzungsstand und Testnachweise](docs/implementation/status.md).
Abgen ist eigenständig und im gemeinsamen Pilot mit PostgreSQL 18,
Yjs, PDF und Domainrückfall geprüft: [Abnahme und Grenzen](docs/implementation/abgen.md).

## Lokale Entwicklung

```sh
python3 scripts/checkout_apps.py
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Die Appquellen liegen in ignorierten eigenständigen Git-Repositories unter
`.work/apps/`. Die [Patchübersicht](patches/index.json) nennt Basis- und Ergebnis-
commits. Auf einem frischen Checkout die zugehörigen Patches mit `git am`
anwenden. Der Checkouthelfer erhält bestehende Änderungen und setzt abweichende
Commits nicht zurück.

```sh
.venv/bin/python -m pytest -q tests
./install.sh preflight
```

Der Preflight erfasst den Host lesend. Vorhandenes Docker, Proxy- oder
Datenbankdienste erfordern einen ausdrücklichen Übernahmeplan.

## Zweierpilot

Nach den [Vorbereitungsschritten](docs/implementation/pilot.md):

```sh
./install.sh pilot-up --state-dir .work/pilot-v2
./install.sh pilot-status --state-dir .work/pilot-v2
./install.sh pilot-stop --state-dir .work/pilot-v2
./install.sh pilot-start --state-dir .work/pilot-v2
```

Der Pilot verwendet die eigenständigen Compose-Dateien mit ergänzenden Overrides,
eigene Testvolumes, getrennte Appnetze, Caddy-TLS und Mailpit. Nur der Proxy ist am
Host-Loopback erreichbar. Keine DNSänderung oder globale CA-Installation.
Wiederholte Installation ist ohne Versionswechsel ein No-op; gestoppte Apps
werden über den gesonderten Startbefehl aktiviert.

Zackboing lässt sich in einer neuen Pilotinstallation ergänzen:

```sh
.venv/bin/python scripts/build_zackboing.py
./install.sh pilot-up --state-dir .work/pilot-v3 --apps gswb,schulwissen,zackboing
```

[Standalone, Bootstrap, Spieltest und Restore](docs/implementation/zackboing.md).
Bestehende Installationen behalten ihre Auswahl. Für den Viererpilot zusätzlich
`scripts/build_schulhelfer.py` ausführen und in einem neuen Zustandsordner
`--apps gswb,schulwissen,zackboing,schulhelfer` wählen.
[Schulhelfer: Standalone, Domainwechsel und Restore](docs/implementation/schulhelfer.md).

Losverkauf ergänzt einen neuen Fünferpilot nach dem Build mit
`scripts/build_losverkauf.py` und Auswahl
`--apps gswb,schulwissen,zackboing,schulhelfer,losverkauf` in einem neuen
Zustandsordner. [Abnahme, Mailqueue und Grenzen](docs/implementation/losverkauf.md).

Grundschultafel ergänzt einen neuen Sechserpilot nach dem Build mit
scripts/build_grundschultafel.py und der Auswahl
gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel über --apps.
[Persönliche PINs, mobile Uploads, Domainwechsel und Dateirestore](docs/implementation/grundschultafel.md).

Fahrradausbildung ergänzt nach scripts/build_fahrradausbildung.py einen neuen
Siebenerpilot mit --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung.
[Migration, Posten-PWA, QR-Domainwechsel und PG-/Dateirestore](docs/implementation/fahrradausbildung.md).

## Releaseprüfung

```sh
./install.sh plan --bundle /pfad/zum/bundle --trusted-key /separat/provisionierter/release-key.pem
```

Der Schlüssel muss unabhängig vom Bundle bereitgestellt sein. Die CLI prüft
Ed25519-Signatur, signiertes Dateiinventar, Hashes, Manifest-Schema, Image-Digests
und Abnahmenachweise. Ohne gültige Signatur gibt es keinen gültigen Plan.
Es existiert noch kein freigegebenes Releasebundle. `apply` bleibt bis zur
vollständigen Host-Provisionierung gesperrt.

## Betriebsgrenzen

Die lokalen Prüfungen belegen Standalone-Starts, privaten Backendzugang, TLS,
Negativzugriffe, Mail in den Sink, Domainwechsel mit Rückfall und einen synthetischen
PostgreSQL-Restore sowie einen kombinierten Zackboing-DB-/Medienrestore. Sie ersetzen keine vollständige Produktionsabnahme.

Das [Dashboard](docs/implementation/dashboard.md) mit TOTP und eingeschränktem
Unix-Steuerdienst unterstützt die zehn Pilot-Apps; aktive Zackboing-Spiele blockieren Stop.
Verschlüsseltes Offsitebackup, konsistente gemeinsame DB-/Datei-/Schlüsselsicherung,
weitere Dashboardfunktionen und Zielservermessungen sind offen.
RPO/RTO und die geschätzten 16 GB RAM/4 vCPU sind noch nicht bestätigt.

Kein Keycloak, keine zentrale Benutzersperrung und kein zentraler Logout.
Lokale Appanmeldungen bleiben erhalten. Testvolumes werden bei Stop behalten.
Kein externer SMTP-Upstream; keine Produktiv- oder DNSumstellung.

Leseflux ergänzt einen neuen Achterpilot nach scripts/build_leseflux.py mit
--apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung,leseflux.
[Lokale Kinderzugänge, Sitzungswiderruf und Restore](docs/implementation/leseflux.md).

Kompetenz-Manager ergänzt nach scripts/build_kompetenz.py den Neunerpilot mit
--apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung,leseflux,kompetenz-manager.
[SQLite, lokale Rechte, begrenzte PDF-Exporte und Restore](docs/implementation/kompetenz-manager.md).

Abgen ergänzt nach scripts/build_abgen.py den Zehnerpilot in einem neuen Zustandsordner:

```sh
./install.sh pilot-up --state-dir .work/pilot-v21 --apps gswb,schulwissen,zackboing,schulhelfer,losverkauf,grundschultafel,fahrradausbildung,leseflux,kompetenz-manager,abgen
```

Eigenes PostgreSQL 18, privater Chromium-Dienst und dauerhafter Yjs-Zustand; die
Erstmigration erzeugt kein Konto. [Standalone, Domain-/QR-/WSS-Rückfall, Dashboard und Restore](docs/implementation/abgen.md).
