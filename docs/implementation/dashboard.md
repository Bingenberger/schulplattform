# Administration und eingeschränkter Steuerdienst

Das Dashboard ist eine serverseitige Flask-Anwendung mit eigener kleiner SQLite-
Datenbank. Es verwaltet Plattformadministration, Sitzungen, eine Zugangsprojektion
und das Betriebsprotokoll. Fachbenutzer und Fachrollen werden nicht übernommen
oder zusammengeführt.

## Administrationsanmeldung

Ein persönlicher Admin wird lokal eingerichtet:

```sh
python -m schulplattform.dashboard setup --state-dir /privater/pfad --username PERSOENLICHER_NAME
```

Passwort, Bestätigung und TOTP-Einrichtung laufen über das kontrollierende Terminal.
Es gibt kein Standardkonto und keinen HTTP-Registrierungsweg. Der TOTP-Schlüssel
wird ausschließlich auf dem Terminal ausgegeben und vor Einrichtung mit einem
aktuellen Code geprüft. Nicht in Shellargumente oder Protokolle kopieren.

Im Betrieb sind Passwort und TOTP erforderlich. Verbrauchte TOTP-Zeitschritte
können nicht nochmals zur Anmeldung verwendet werden. Fünf Fehlversuche sperren
für 15 Minuten; die Sperre wird in der Datenbank gespeichert und gilt über
Worker und Neustarts. Unbekannte Benutzernamen teilen einen begrenzten Bucket.
Sitzungen liegen als Hash im Store, gelten maximal eine Stunde und werden bei
Logout serverseitig gelöscht.

TOTP-Seeds werden mit Fernet verschlüsselt. Der zugehörige Wrapping-Key und der
Cookie-Key liegen im privaten Secretstore. Fehlen Schlüssel bei bestehender
Datenbank, wird kein Ersatz generiert. Ein vollständiger verschlüsselter
Offsite-/Schlüsselrestore ist noch offen.

Die Oberfläche enthält weder Passwörter noch TOTP-Seeds, Sitzungstokens oder den
Steuerdienst-Schlüssel. Formulare verwenden eigene sitzungsgebundene CSRF-Nonces.
Cookies sind Secure, HttpOnly und SameSite=Strict. Die produktive Oberfläche
gehört hinter TLS.

## Kacheln und Rechte

Öffentliche Apps dürfen eine öffentliche Kachel erhalten. Für geschützte Apps
reicht die Plattform-Adminrolle nicht: Sie erscheinen erst in der expliziten
Zugangsprojektion. Diese ist noch nicht automatisch mit den tatsächlichen
Appkonten synchronisiert. Im getesteten Standard wird deshalb nur gswbs öffentliche
Suche als Kachel gezeigt. Die Administration listet separat den Betriebszustand
aller im Pilot bekannten Apps.

Es gibt keine Oberfläche zum Anlegen oder Ändern von Fachbenutzern.

## Steuerkanal

Der separate Deployment-Dienst hört ausschließlich auf einem Unix-Socket.
Er prüft die lokale Peer-UID sowie HMAC-signierte Anfragen mit kurzer Gültigkeit
und einer persistenten einmaligen Nonce. Antworten sind ebenfalls authentifiziert
und an die Anfragenonce gebunden.

Erlaubte Aktionen sind derzeit `status`, `start` und `stop`; bekannte Ziele sind
`gswb`, `schulwissen`, optional `zackboing`, `schulhelfer`, `losverkauf` und `grundschultafel`. Unbekannte Felder, Apps, Aktionen, manipulierte MACs,
abgelaufene Zeitstempel und Wiederholungen werden abgewiesen. Die Oberfläche
kann weder Hostpfade noch argv, Compose-Fragmente oder Shellkommandos vorgeben.

```sh
.venv/bin/python -m schulplattform.deployment \
  --pilot-state .work/pilot-v2 \
  --service-state .work/deployment-service \
  --socket .work/management/deploy.sock \
  --allowed-uid 10001
```

Bei Zackboing verweigert der Controller Stop während eines aktiven Spiels. Die
Oberfläche antwortet mit 409 und protokolliert den blockierten Vorgang. Der Dienst
stoppt erst nach Spielende; Daten bleiben erhalten. Nicht installierte Apps
werden als nicht installiert gemeldet.

Schulhelfer ist im Viererpilot ein weiteres festes Ziel. Sein eigener Erstadmin
wird über die lokale App-CLI eingerichtet; Plattformadmins erhalten dadurch
keine automatischen Fachrechte. Die Zugangsprojektion bleibt ausdrücklich bestätigt.

Losverkauf ist im Fünferpilot ein weiteres festes Ziel. Elternzugänge und
individuelle Bearbeitungstokens werden nicht in das Dashboard übernommen;
Fachzugriff wird weiterhin ausdrücklich projiziert.

Grundschultafel ist im Sechserpilot ein weiteres festes Ziel. Ihre Lehrkraftkonten
und PINs bleiben in der App. Der letzte reale Dashboard-/Unix-Test steuerte
Start und Stop von Grundschultafel; die öffentliche Kachel bleibt ohne bestätigte
Fachzugangsprojektion verborgen.

Das ist der lokale Pilot-Controller. Ein vollständig signierter Produktions-
Releasecontroller mit Update, Migration, Restore und Lifecycle-Archivierung
ist noch nicht angeschlossen.

Das Dashboard hat keinen Docker-Socket. Der Deployment-Dienst hat dagegen
Docker-Berechtigungen und kann damit grundsätzlich den Host übernehmen.
Die Begrenzung seiner API beseitigt dieses verbleibende Privileg nicht. In einer
Zielinstallation müssen Dashboard und Deployment-Dienst getrennte Betriebskonten
und getrennte Dateirechte erhalten.

Der Socket liegt in einem Verzeichnis, das die Dashboardgruppe nur durchsuchen,
aber nicht verändern darf; der Socket selbst erlaubt dieser Gruppe die Verbindung.
Zusätzlich muss die Peer-UID zur Dashboard-UID passen. Der API-Schlüssel wird pro
Dienst über eine separate Credentialdatei bereitgestellt. Compose-Dateisecrets
allein sind keine Verschlüsselung auf dem Host. Verwaiste Socketdateien werden
nicht blind ersetzt; ein späterer systemd-Installationspfad ist noch offen.

## Container und Tests

`Dockerfile.dashboard` verwendet einen Nicht-Root-Benutzer, Hash-Lockfile und ein
fixiertes Python-Basisimage. Das Composeprofil begrenzt Ressourcen, verwirft
Capabilities und schreibt nur in das Datenvolume und das begrenzte tmpfs.
Nach lokalem Setup startet der eigentliche Server über Gunicorn hinter TLS.

Das Diagnoseserver-Kommando `serve` bindet nur Loopback und ersetzt keine TLS-
Installation. Für den Container konfiguriert `from_env()` ausschließlich Dateipfade
für Zustand, Socket, Credentials und Appkatalog sowie erlaubte Hostnamen.

Die Tests verwenden ausschließlich synthetische Adminprofile, private Testvolumes
und lokale Pilotumgebungen; zuletzt den Sechserpilot mit Grundschultafel. Sie prüfen unter anderem Login/CSRF, TOTP-Replay,
Sitzungswiderruf, Peer-UID, MAC/Nonce-Replay und die tatsächlichen Start-/Stop-Aktionen
über den authentifizierten Kanal.

Noch offen sind insbesondere produktive Serviceinstallation, Domain-/Update-/
Backupoberfläche, SMTP-Einstellungen und Testversand aus dem Dashboard,
vollständige tatsächliche Appzugangsprojektion und die Aufnahme aller zehn Apps.
