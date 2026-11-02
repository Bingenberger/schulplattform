# Schulplattform – Umsetzung in Arbeit

Dieses Repository enthält den Beginn der Umsetzung des
[Auftrags](Coding_Agent_Umsetzungsauftrag_Schulplattform.md), **keine fertige oder
produktionsreife Plattform**. Maßgeblich bleibt der
[Umfangsbeschluss](docs/platform-audit/scope-decision.md).

Aktuell vorhanden: Sicherheitsänderungen in vier isolierten App-Repositories,
gswb-Standalone-Container mit expliziter Migration, Manifest-Schema und Validierung,
explizite Caddy-Konfigurationserzeugung, SQLite-Snapshot/Restore und ein lesender
Installer-Preflight. Stand und offene Abnahmen stehen im
[Umsetzungsbericht](docs/implementation/status.md).

## Lokale Entwicklung

```sh
python3 scripts/checkout_apps.py
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Die Appquellen liegen ausschließlich in ignorierten, eigenständigen Git-Repositories
unter `.work/apps/`. Änderungen werden als Commits und übertragbare Patches unter
`patches/` geliefert. Keine Appquellen werden zu einem Monorepo zusammengeführt.
Auf einem frischen Checkout die Patches auf die jeweils in `patches/index.json`
genannten Basiscommits mit `git am` anwenden, bevor die App-Integrationstests laufen.
Der Checkouthelfer erhält bereits vorhandene Arbeitsstände und verweigert
abweichende Commits; nach Patchanwendung nicht erneut als Resetwerkzeug verwenden.

```sh
.venv/bin/python -m pytest -q tests
sh install.sh preflight
```

Der Preflight verändert keine Hostdienste. Vorhandenes Docker/nginx erfordert einen
gesonderten Übernahmeplan. `plan --bundle VERZEICHNIS` prüft ausschließlich Manifeste
und Nachweisdateien. **`apply` ist noch nicht implementiert und bricht ab.** Es gibt
kein freigegebenes Releasebundle und kein Ein-Kommando-Deployment aller zehn Apps.

## Betriebsgrenzen

Keine Produktivänderung, DNS-Änderung oder echten E-Mails. Kein externer SMTP-Upstream.
Kein Keycloak. Keine zentrale Benutzersperrung oder zentraler Logout. Lokale Logins
bleiben erhalten; gswb-Redaktion erhält vorerst eine lokale abgesicherte Anmeldung.

SQLite-Snapshots sind nur ein getesteter Baustein. Verschlüsseltes Offsitebackup,
PostgreSQL-/Datei-Konsistenz, Secret-/Schlüsselrestore und die vollständige leere
Wiederherstellung sind noch nicht umgesetzt. Keine RPO-/RTO-Zusage.

Docker-Testvolumes bleiben erhalten. Zum Stoppen niemals `compose down -v` verwenden.
App-Images werden noch nicht veröffentlicht. Der lokale gswb-Entwicklungstag ist
kein freigegebenes Registry-Image mit Distribution-Digest.
