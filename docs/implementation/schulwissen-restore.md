# Schulwissen: kombinierter Restore mit echter Webprüfung

Die zuvor offene Lücke nach dem reinen PostgreSQL-Restore ist geschlossen.
Der Versuch verwendet ausschließlich synthetische Daten im lokalen Pilot
`.work/pilot-v21` und einen unabhängigen neuen Compose-Stack.

[Ergebnis und genaue Grenzen](evidence/schulwissen-http-restore.json),
[ausgeführte Kommandos ohne Nutzdaten/Secrets](evidence/schulwissen-http-restore-operations.json).

## Ausgeführt

1. Drei neue Testidentitäten mit den nativen Rollen Administration/Lehrkraft,
   ein privater Wissensbereich, ein privates Dokument mit Version und eine
   hochgeladene Textdatei wurden über die bestehenden Modelldienste angelegt.
   Vorhandene synthetische Zeilen blieben erhalten.
2. Die Lehrkraft wurde am Quellpilot über TLS mit geprüfter lokaler CA angemeldet;
   ihr erlaubter Mediendownload wurde geprüft. Cookie und zufälliges Passwort
   liegen ausschließlich im ignorierten privaten Fixtureverzeichnis.
3. Alle Webschreiber dieser App wurden gestoppt. PostgreSQL-Custom-Dump und
   Medienarchiv stammen damit aus demselben unveränderten Anwendungsstand.
4. Ein neuer PostgreSQL-Container, eine leere Datenbank und ein eigenständiges
   leeres Medienvolume wurden erzeugt. Die neue Approlle besitzt keine Superuser-,
   CREATEDB- oder CREATEROLE-Rechte.
5. Der Restore lief transaktional in das leere Ziel. Ein zweiter Restore in
   dasselbe, nun nichtleere Ziel wurde abgewiesen. Vor dem ersten HTTP-Aufruf
   waren die Zeilen aller 33 Anwendungstabellen einschließlich Django-Migrationen,
   Sitzungen, Nutzer-/Gruppen-IDs, Rechten und Dateimetadaten identisch.
   Tabellenbesitz und validierte Fremdschlüssel wurden gesondert geprüft.
6. Mediendateien wurden checksumgeprüft in das separate Volume mit UID 10001
   wiederhergestellt; Namen und Bytes stimmen mit der Quelle überein.
7. Dieselbe Runtime mit zwei Gunicorn-Workern startete ohne Migration, Seed oder
   Benutzereinrichtung. Der gesondert erhaltene Signierschlüssel erlaubt die
   Verwendung der bereits vor der Sicherung angelegten Sitzung.
8. Die restaurierte App wurde tatsächlich über ihren ausschließlich an
   Host-Loopback gebundenen HTTP-Port geprüft.

## HTTP- und Negativnachweise

- Bestehende Sitzung öffnet Startseite und private Mediendatei vor jeder neuen
  Anmeldung am Restoreziel.
- Neue persönliche Anmeldungen funktionieren mit unveränderten Konten/Rollen.
  Die berechtigte Lehrkraft sieht Dokument, Eintrag und Originaldatei.
- Eine andere Lehrkraft erhält beim direkten Dokument- und Medienzugriff 404.
  Anonyme Zugriffe führen zur Anmeldung.
- Die Lehrkraft darf keinen administrativen JSON-Export ausführen; die
  Administration erhält den tatsächlichen Inhalt und einen echten PDF-Download.
- Fehlendes CSRF-Token und fremde Origin werden abgewiesen.
  Nach Logout funktioniert eine zuvor kopierte Sitzung nicht mehr.
- App läuft weiterhin ohne Rootrechte mit schreibgeschütztem Rootdateisystem.
  Die Restore-Datenbank hat keinen Hostport.

Ein nachgestellter Zielserver oder eine öffentliche TLS-/DNS-Abnahme wird damit
nicht behauptet. Das Restoreziel verwendet privates Loopback-HTTP; der
Quellzugriff verwendet bereits den geprüften lokalen TLS-Pilot.

## Betrieb und Grenzen

Reproduktion: `scripts/verify_schulwissen_restore_http.py`.
Voraussetzung sind der akzeptierte Pilot und die vorhandenen fixierten Images.
Alle Quell- und Restore-Dienste sind danach gestoppt, Datenvolumes und Schlüssel
bleiben erhalten. Eine fehlgeschlagene Fixture wird nicht in echte Konten
überführt; folgende Versuche verwenden neue synthetische Identitäten.

Der Signierschlüssel wurde separat aus dem privaten Quellstore bereitgestellt.
Das ist kein Nachweis eines verschlüsselten vollständigen Secret-/Plattformbackups
und kein Offsite-Transport. RPO/RTO sind weiterhin nicht bestätigt.
Auch ein Image-Rollback ersetzt keinen Datenbank-Rollback: Der Versuch spielt
einen gemeinsam gesicherten Daten-/Medienstand in eine zur unveränderten Runtime
passende Umgebung zurück und führt keine Schema-Downgrades aus.

Änderungspaket: `13498abd4c7684d4200afa7cd09ccc2037f95c2e`. [Geprüfter Commitbeleg](evidence/restore-metrics-work-package-commit.log).
