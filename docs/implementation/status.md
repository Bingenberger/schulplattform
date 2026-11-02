# Umsetzungsstand vom 2. November 2026

**Der Gesamtauftrag ist nicht abgeschlossen. Es gibt kein freigegebenes
Plattformrelease.** Die folgenden Ergebnisse sind ein überprüfbarer Zwischenstand.
Die bestehenden Auditdokumente wurden nicht als neue Testergebnisse ausgegeben.

## Beobachtet und implementiert

- 13 öffentliche Repositories an den geprüften Commits isoliert ausgecheckt.
  Das private `schulanmeldung` scheiterte beim SSH-Abruf mit Timeout. Kein bestehendes
  App-Deployment verändert. Checkouthelfer setzt unabhängige Abrufe fort.
- Vier lokale App-Commits einschließlich übertragbarer Patches:
  [Basis-/Ergebniscommits](../../patches/index.json).
- gswb: Pflichtsecret; lokale Redaktionsanmeldung; serverseitige Prüfung aller
  `/review`-Pfade; CSRF für Redaktion und Login/Logout; CORS nur öffentliche Lese-API.
  Gefälschte Proxyheader sind keine Identität. Compose mit eigenem Datenbestand,
  Nicht-Root-Prozess, read-only Root-FS, Limits und separatem Migrationskommando.
- Zackboing: Sessionalter maximal 90 Tage, ungültige und zukünftige Zeitwerte
  werden zurückgewiesen. IDs und Besitzzuordnungen unverändert.
- Grundschultafel: keine HTTP-Erzeugung des bekannten Standardadmins; lokaler
  zufälliger Bootstrapcode mit 15 Minuten Gültigkeit und einmaliger Verwendung;
  Eingabe im Login und PIN-Wechsel; private atomare Nutzerdateien.
- Losverkauf: bisheriger Verwaltungszugang zusätzlich an `ADMIN_USERNAME`
  gebunden; alte boolesche Adminsessions reichen nicht. Keine Änderung von
  Eltern- oder Bearbeitungstokens. Noch keine Mehrbenutzerverwaltung.
- Plattformbausteine: JSON-Schema, Artefakt-/Manifestvalidierung, expliziter
  Caddy-Generator mit Headerbereinigung, Hostinventar/Fremdbestand-Prüfung,
  atomarer State-/Lockbaustein, SQLite-Snapshot und Restore.

## Ausgeführte Tests

| Prüfung | Ergebnis | Rohbeleg |
| --- | --- | --- |
| Python-Sicherheits-, Manifest-, Proxy-, Preflight- und SQLite-Tests | 25 bestanden | [Log](evidence/python-tests.log) |
| Zackboing: neue, alte, beschädigte, zukünftige und widerrufene Sessions gegen SQLite | bestanden | [Log](evidence/zackboing-session.log) |
| Grundschultafel: kein Defaultkonto, konkurrierender Bootstrapverbrauch, Ablauf, Dateimodus, beschädigter Store | bestanden | [Log](evidence/grundschultafel-users.log) |
| Grundschultafel TypeScript `tsc --noEmit` | Exit 0 | [Log](evidence/grundschultafel-types.log) |
| gswb amd64-Build aus fixiertem Basisimage und Hash-Lockfile | bestanden, lokales Entwicklungsimage | [Build](evidence/gswb-build.log), [Image](evidence/gswb-image.json) |
| gswb Standalone-Compose: Migration, Start, Zugriff, Restart | bestanden | [Ergebnis](evidence/gswb-container.json), [Log](evidence/sp-gswb-test-6425a0b7.log) |

Die erste Docker-Startprüfung scheiterte am fehlenden Compose-Plugin
([Log](evidence/gswb-container.log)). Danach wurde Compose 2.40.3 ausschließlich
unter `.work/` heruntergeladen und gegen die veröffentlichte SHA256-Prüfsumme
geprüft. Ein weiterer Startversuch zeigte einen YAML-Fehler in der tmpfs-Liste;
dieser wurde korrigiert ([Fehlerlog](evidence/sp-gswb-test-da183a96.log)). Der
anschließende Lauf bestand. Testcontainer/-netze wurden entfernt, Testvolumes
bewusst erhalten. Keine globalen Docker-Aufräumkommandos.

Die Python-Tests verwenden synthetische Daten und teilweise andere Paketversionen
als das vollständig aufgelöste Container-Lockfile. Der echte Container wurde
separat mit HTTP-Tests geprüft. Kein kompletter Browsertest der Bootstrapoberfläche.

## Pakete und nicht ausgeführte Abnahmen

| Paket | Stand | Fehlend |
| --- | --- | --- |
| A0 | offen | gewählte Projektlizenz, Fremdmaterialprüfung, private Repoerreichbarkeit |
| A1 | teilweise implementiert und getestet | Live-Proxy-Negativtest, direkte Backendisolation im Gesamtstack; vollständige Abnahme |
| A2 | Schema/Validierung vorhanden | signierte Releasebundles, Registry-Digests, SBOM, reproduzierbare Gesamtbuilds |
| A3 | nur Caddy-Konfigurationserzeugung | Infrastrukturstack, Relay/Queue/Sink, Secretstore-Lebenszyklus |
| A4 | gswb-Standalone-Teilnachweis | schulwissen-Anpassungen, gemeinsamer Plattformstart, TLS |
| A5 | lesender Preflight und Manifestplan | Provisionierung, persistente Installationszustandsmaschine, Bootstrap aller Apps, Resume/No-op auf leerem Ubuntu; `apply` verweigert Ausführung |
| A6 | nicht implementiert | komplette Domaintransaktion mit Zertifikat, Links, Appkonfiguration und Rückfall |
| A7 | SQLite-Primitiven getestet | PostgreSQL, Dateikonsistenz, Verschlüsselung, Offsite, Secret-/Schlüsselrestore, vollständiger leerer Restore |
| A8 | nicht implementiert | Dashboard mit TOTP und eingeschränkter authentifizierter Deployment-Dienst |
| A9 | nicht implementiert | acht weitere Containerintegrationen und sämtliche Appabnahmen |
| A10 | nicht ausgeführt | Zielserver, Leerlauf, 10-Personen-Last, Dauerlauf und Hintergrundkonkurrenz |
| A11 | bewusst nicht begonnen | Voraussetzungen A5–A9 nicht abgenommen |

Keine App ist nach der vollständigen Definition des Auftrags fertig. Insbesondere
ist gswbs lokaler Standalone-Test **kein** Restore-/Domain-/Plattformnachweis.
Das Compose-Override für gswb wurde noch nicht im gemeinsamen Proxyverbund geprüft.

## Grenzen und Entscheidungen

- Lizenzwahl wurde angefragt und liegt noch nicht vor. Keine Lizenz erfunden und
  keine Images veröffentlicht. Fremdmaterial bleibt separat zu prüfen.
- Leerer Ubuntu-24.04-Testserver samt Testdomains wurde angefragt und liegt noch
  nicht vor. Der vorhandene Entwicklungsrechner wurde nicht zum Zielserver umgebaut.
- Geschätzt bleiben 16 GB RAM, 4 dedizierte vCPU und 160–200 GB SSD für zehn Apps.
  Ohne Zielservermessung gibt es keine bestätigte Kapazitäts- oder RPO/RTO-Zusage.
- Kein zentraler Logout, keine zentrale Sperrung, keine gemessene Sperrfrist.
  [Austrittschecklisten](departure-checklists.md) für die drei getrennten TOTP-Apps.
- Grundschultafels Gerätebindung ist offen. Atomare Nutzerdateien verhindern
  unvollständige Dateien, aber noch keine verlorenen parallelen Listenänderungen.
- gswb-Redaktionslogin hat noch keine Login-Drosselung; BFF/Nextcloud ist offen.
- Kein produktiver SMTP-Upstream, keine echte E-Mail, kein echtes Konto, keine DNS-
  oder Produktivumstellung. Weitere Implementierungsarbeit ist auch unabhängig von
  Lizenzwahl und Testserver noch erforderlich.
