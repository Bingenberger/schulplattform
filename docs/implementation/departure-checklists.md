# Austritt – separate Kontensperrung erforderlich

Keine zentrale Sperrung oder garantierte Sperrfrist. Die folgenden Schritte sind
manuelle Betriebschecklisten und wurden nicht gegen echte Konten ausgeführt.

## SL-Journal

- Zuständige Person und Datenübergabe festlegen; verschlüsselte Sicherung samt
  SQLCipher-/Anhangsschlüsseln und Wiederherstellbarkeit prüfen.
- Lokale Zugangsdaten und TOTP/Recoverycodes kontrolliert ersetzen.
- Browser-/Gerätezugänge und bestehende Sessions einzeln beenden; Wirkung prüfen.
- Persönliche externe Zugänge und Geräteberechtigungen entfernen.

## Schulanmeldung

- Lokales Konto sperren/entfernen, Fachzuordnungen und Datenbesitz vorher klären.
- TOTP/Recoveryzugänge und bestehende Sessions separat widerrufen.
- Direkten geschützten APIzugriff mit altem Zugang im zulässigen Testkontext prüfen.
- Zuständige Person dokumentiert Zeitpunkt und Ergebnis; kein Versand echter Testmails.

## Schulkasse

- Übergabe von Finanzdaten, Belegen und Zuständigkeiten dokumentieren.
- Lokalen Zugang, TOTP/Recoverycodes und bestehende Sessions einzeln sperren.
- Externe SMTP-/Geräteberechtigungen prüfen und bei Personenbezug rotieren.
- Verweigerten Zugriff prüfen; historische Buchungszuordnungen erhalten.

Konkrete administrative Kommandos hängen vom jeweiligen unveränderten Deployment
ab. Ohne bestätigte Appfunktionen wird kein nicht vorhandener Sperrendpunkt behauptet.
