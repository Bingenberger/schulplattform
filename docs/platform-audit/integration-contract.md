# Plattform-/Appvertrag v0.1 (Entwurf)

Ein Appmanifest wird gegen ein versioniertes JSON-Schema geprüft, ohne ausführbaren benutzerdefinierten Shellcode. Dieses Dokument definiert den Vertrag; ein vollständiger Deployment-Controller ist noch nicht implementiert. Unbekannte Schlüssel/Versionen ablehnen, Änderungen als Plan mit Hash und Audit-ID behandeln. Image-Digest, Herkunftscommit, SBOM und Kompatibilitätsfreigabe gehören zum Release.

```yaml
schemaVersion: 1
id: schulwissen
name: Schulwissen
source:
  commit: a9673bc343a3a6eea1c15f533d0e89061e669b32
image:
  repository: registry.example.invalid/school/schulwissen
  version: audit-a9673bc
  digest: REQUIRED_AFTER_VERIFIED_BUILD  # vor Start SHA256 verlangen
services:
  - {id: postgres16, database: schulwissen, account: schulwissen_app}
port: 8000
health:
  live: {path: /health/live, intervalSeconds: 30, timeoutSeconds: 3}
  ready: {path: /health/ready, includes: [database, migration-version]}
  implementationStatus: proposed  # im geprüften Appstand ergänzen
configuration:
  SW_OEFFENTLICHE_URL: {type: https-origin, required: true}
  SW_ALLOWED_HOSTS: {type: hostname-list, required: true}
  SW_DATABASE_URL: {type: secret-reference, required: true}
  SW_SECRET_KEY: {type: secret-reference, required: true}
  SW_WORKER: {type: integer, min: 1, max: 4, default: 1}
persistence:
  - {id: media, mount: /medien, ownership: '10001:10001', backup: required}
migration:
  argv: [python, manage.py, migrate, --noinput]
  postMigrationArgv: [python, manage.py, rollen_einrichten]
  executor: signed-release-job
  exclusiveLock: schulwissen-schema
  automaticOnRestart: false  # Docker-Startskript dafür anpassen
resources:
  memoryReservationMiB: 256
  memoryLimitMiB: 768
  cpus: 1.0
  pidsLimit: 128
  tempLimitMiB: 256
  pdfConcurrency: 1
publicRoutes:
  - {path: /anmelden, methods: [GET, POST], purpose: local-emergency-login}
  - {path: /anmelden/nextcloud, methods: [GET], purpose: oidc-start}
  - {path: /anmelden/nextcloud/callback, methods: [GET], purpose: oidc-callback}
  # Passwort-Reset-/Assetrouten aus aktueller urls.py vervollständigen;
  # publicRoutes ist kein Recht auf Lesen fachlicher Daten.
authentication:
  mode: native-oidc-bff
  localMapping: [issuer, subject]
  accessGrant: app:schulwissen:access
  revocationMaximumSeconds: 60
  oidc:
    clientId: schulwissen
    issuer: https://login.example.invalid/realms/school
    secretRef: school/schulwissen/oidc-client
    redirectUris: [https://wissen.example.invalid/anmelden/nextcloud/callback]
    pkce: S256
    scope: [openid, profile, email]
  integrationStatus: partial-in-upstream
smtp:
  needed: true
  host: relay.internal
  port: 587
  tls: starttls
  credentialRef: school/schulwissen/relay
  allowedFrom: [schulwissen@example.invalid]
backup:
  database: {engine: postgres16, commandId: pg-dump-custom, consistent: true}
  files: [media]
  consistency: pause-writers-during-db-and-file-snapshot
  secretRefs: [school/schulwissen/config]
  restoreCommandId: schulwissen-restore-v1
  verify: [schema-version, foreign-keys, media-hashes, ownership, denied-access]
  restoreStatus: not-yet-executed
lifecycle:
  visible: true
  desiredState: running
  uninstallDataPolicy: retain-unless-separately-authorized
```

Das Beispiel enthält bewusst als erforderlich/offen gekennzeichnete Werte und ist kein bereits ausrollbares Release. Platzhalter-Digest und vorgeschlagene Healthpfade müssen die Releasevalidierung blockieren. Secrets sind Referenzen, keine Werte. Manifest-Migrationskommandos stammen ausschließlich aus geprüften signierten Releases; UI-Nutzer dürfen keine argv-/Shellkommandos eingeben. Konfigurationsschema akzeptiert nur erlaubte Typen, Ports, Hostnamen und Pfade; Pfadtraversal und Hostmounts außerhalb genehmigter Volumes ablehnen.

## Verbindliche Schnittstellen vor Produktivfreigabe

- Konfiguration: Runtime-Env oder Secretdateien; Adapter übersetzt gemeinsame Namen in SW_*, FP_*, SL_OFFICE_*, MAIL_* etc. Für Vite/Next buildgebundene öffentliche Werte kennzeichnen und bei Domainwechsel neu bauen, falls Laufzeitkonfiguration noch fehlt. Secretdateien nur App-UID lesbar, keine Werte in `docker compose config`-Export/Logs.
- Health: Liveness ohne externe KI/SMTP; Readiness mit eigener DB und Migrationsstand. Externer Dienstausfall als degraded, nicht endlose Neustartschleife. Öffentlicher Healthstatus verrät keine Verbindungsstrings. Vorhandene /gesund, /healthz, /api/health verwenden, wenn deren Semantik geprüft wurde; keine behauptete Vollabdeckung aller Apps.
- Auth: etablierte Bibliothek, lokale ID bleibt fachlicher Schlüssel. Revokations-/Freigabeereignis versioniert und replayfest; Backend und WS setzen Appfreigabe und Fachrechte um. Proxyauth nur bei tatsächlich identitätsloser Funktion (gswb-Redaktion bzw. bewusst gemeinsamer Adminfunktion).
- SMTP: interne authentifizierte Submission, per App gebundene Absender, Timeout und Outbox/Retry mit Idempotenzkennung. Kein Password-/Reset-/Elternlink in Logs. SMTP-Relayannahme ist keine Zustellgarantie.
- Backup: Appadapter liefert konsistenten Snapshot und Dateiliste, schema-/versions-/hashgebundenes Inventar. Restore nur in leere Zielumgebung, danach Fachinvarianten, Rollen und Zugriffssperren prüfen. Verschlüsselungsschlüssel und IdP-Daten nicht vergessen.
- Ressourcen: je Prozess/Containerlimits, Exportslots und begrenzte Queue; bei Überlast 429/503 statt unbegrenztem Chromium-/LibreOffice-Start. Obergrenzen aus Benchmark prüfen. Slots je Prozess zählen; mehrere Worker multiplizieren eine lokale Semaphore.

## Lebenszyklus

**Ausblenden:** nur Kachel verbergen, laufende APIs und bestehende Freigaben unverändert. **Stoppen:** App/Worker kontrolliert drainen/stoppen, Daten/Secrets/Backups behalten; öffentlicher Wartungsstatus und keine neuen Jobs. **Deinstallieren:** definierte Container-/Routenentfernung, standardmäßig Daten archivieren/behalten. Datenvernichtung ist eigener irreversibler Vorgang mit Ziel-/Backupnachweis und ausdrücklicher Freigabe; `compose down -v` ist nie normale Deaktivierung. Wiederaktivierung derselben App-ID verwendet bestehende Volumes und führt keine Seeds oder Bootstrap-Neuanlage aus.
