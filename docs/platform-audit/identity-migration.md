# Identität, Rechte und Migration

**Beobachtet:** Schulwissen hat issuer/sub-Mapping, Authlib-Codeflow mit PKCE und explizite Verknüpfung. Andere untersuchte Appauthentifizierungen sind lokale Cookies/JWTs, gemeinsame Adminpasswörter, Kinder-/Elterncodes oder ein Einzelkonto. Ein Proxy kann diese Modelle nicht automatisch zusammenführen. [Matrix](repository-matrix.csv) und [Schulwissen](apps/schulwissen.md) belegen die Unterschiede.

## Zielvertrag (Entwurf)

Keycloak ist das führende Verzeichnis der Mitarbeiteridentität. Plattformadministrator verwaltet Installation, Domains und Releases; Appadministrator verwaltet die jeweilige App; fachliche Rollen bleiben in der App. Eine Plattformadministration liest nicht automatisch Journale, Finanz- oder Diagnostikdaten. Appfreigaben z. B. `app:schulwissen:access` sind Zugangsvoraussetzung, niemals Ersatz für Klassen-/Gruppen-/Objektrechte. Rollenvergaben mit Auswirkungen auf Kassenrechte oder Schulleitungsdaten brauchen explizite fachliche Freigabe.

Je Anwendung separater Client, Authorization Code + PKCE S256, exakte HTTPS-Redirects, keine Wildcards. Serveranwendungen/BFF halten Clientsecret und Tokens serverseitig; Browser enthält nur HttpOnly/Secure/SameSite=Lax-Sitzungscookie mit eigenem Namen, ohne Domainattribut über alle Apps. Falls künftig eine reine SPA eingesetzt wird: öffentlicher Client ohne Secret, etablierte OIDC-Bibliothek, Tokens bevorzugt nur im Speicher; BFF für sensible Daten bevorzugt. API-Middleware prüft Signatur, erlaubte Algorithmen, JWKS-Rotation, issuer, audience/azp soweit erforderlich, Ablauf/nbf, State und Nonce nach Bibliotheksvertrag. Kein selbst gebauter JWT-Parser.

Bei Login: Tokenvalidierung → Appfreigabe → Mapping auf lokale ID → lokale Aktivität/Rollen → neue lokale Session. Bei jedem geschützten API-/WebSocket-Zugriff dieselben Zugangs- und Fachregeln; bei WebSocket auch laufende Verbindungen neu bewerten. Negative API-Tests dürfen nicht nur Redirects/Kacheln prüfen.

SSO über verschiedene Hauptdomains funktioniert über Browserredirects zum gleichen IdP und dessen eigene Session; gemeinsame Domaincookies sind dafür nicht erforderlich. Third-Party-Cookie-Abhängigkeit vermeiden, Top-Level-Redirect testen. Öffentliches Eltern-/Kinder-/Kiosk-/Share-/Print-Routing explizit im Manifest zulassen und innerhalb der App mit den bisherigen Tokens/Rechten schützen.

## Kontrollierter Migrationsablauf

1. Schreibgeschützten Bestandsauszug in geschützter Arbeitsumgebung erzeugen: lokale ID, Aktivität, Rollen und Fremdschlüsselzählungen. Keine echten Konten/Hashes in Auditdateien. Vorher konsistente Sicherung erstellen.
2. Zentrales Konto per persönlicher Einladung/administrativer Identitätsprüfung anlegen; Mailbestätigung allein rechtfertigt keine Übernahme eines bestehenden Appkontos. Konten ohne E-Mail erhalten eine stabile IdP-Kennung und betreuten Aktivierungskanal. Kinder/Eltern bleiben im vorhandenen Fachzugang, solange keine ausdrückliche zentrale Kontenentscheidung getroffen wurde.
3. Lokale Tabelle `external_identity(issuer, subject, local_user_id, linked_at, linked_by, proof_method)` ergänzen. Unique(issuer, subject); weitere Unique-Bedingungen nach gewünschter Zahl externer Identitäten pro lokalem Konto. Vorhandene Schulwissen-Tabelle weiterverwenden.
4. Verknüpfung nach erneuter lokaler Anmeldung und erneutem IdP-Login oder mit dokumentiertem Vier-Augen-Adminverfahren. Ein kurzlebiger signierter Verknüpfungsauftrag bindet lokale ID, Issuer, erwartetes Subject und Ablauf; wiederholte Nutzung abweisen. Gleiche unbestätigte E-Mail führt nie zum Merge.
5. Duplikate/umbenannte Adressen als Konfliktliste behandeln. Vor Merge Fachbesitz, Klassenzuordnungen, Historie und geteilte Dokumente vergleichen; keine stillschweigende Umnummerierung. Wenn zwei lokale Konten derselben Person gehören, bleibt die fachliche Zusammenführung ein eigenes, reversibles Verfahren mit Nachweis aller FKs.
6. Passwort-Hashes verbleiben zunächst lokal. Django/Werkzeug/Argon2/bcrypt/scrypt sind nicht pauschal in den IdP importierbar; kein Klartext und kein generisches Hash-Umschreiben. Neue zentrale Passwörter per Einladung/Reset, lokale Passwörter für zeitlich begrenzten Rückfall erhalten oder nach erfolgreicher Abnahme gezielt deaktivieren.
7. Trockenlauf mit synthetischen IDs: Vorher/nachher FK-Anzahlen, Eigentümer, Klassen-/Gruppenrechte, verbotene Zugriffe, Audit und Wiederholung vergleichen. Dann kontrollierte Benutzergruppen umstellen, lokales Notfallkonto separat prüfen. Rollback macht Zuordnung rückgängig, keine fachlichen Tabellen löschen.

## Appbezogene Sonderfälle

| Appgruppe | Zu erhaltende Beziehung / Ausnahme |
| --- | --- |
| Schulwissen | Nutzer-PK, Gruppen, Fachrechte, vorhandene OIDCIdentitaet |
| Fahrrad | Benutzer-PK und Schule; Posten-Token/Offline-Daten bleiben separat |
| Schulanmeldung | User-PK/Zuständigkeit, MFA; Elternaktivierung/-mailtoken eigenständig |
| Kompetenz-Manager | User.id und UserKlassenzuordnung, Förderplan-/Schülerbeziehungen |
| Leseflux | UUID, classId/GroupMember/Trainingshistorie; QR/LoginCode-Kinderzugang erhalten, qrTokenRaw wie Secret schützen |
| Schuleva | users.id, Befragungsbesitz, ShareGrants; TAN nicht in Mitarbeiteridentität umwandeln |
| Grundschultafel | users.json-ID und data/<id>; konkurrierendes Dateischreiben absichern |
| Schulkasse | benutzer.id, verantwortlich_user_id; Kasse/Admin explizit, IdP-MFA vor Finanzzugriff |
| abgen | Account-ID, Dokumentbesitz, Freigaben/Yjs und Offline-Konflikte |
| Schulhelfer | AdminUser.id; Participant und Linktoken sind getrennte Entitäten |
| Zackboing | user.id und Quizbesitz; Gäste/PIN-Spieler separat, flüchtige Spiele vor Update beenden |
| Losverkauf | Kein individueller Adminbestand: neue Identitätsbindung nötig; vorhandene edit_tokens nicht neu erzeugen |
| gswb | Keine Benutzer-Migration; Proxy/BFF für identitätslose Redaktion ausreichend, alle Schreibwege und CSRF abdecken |
| SL-Journal | account.id=1 bewusst auf genau berechtigte Identität abbilden; Mehrbenutzerbetrieb ist eigener Fachumbau, Mobil-API und Verschlüsselung bewahren |

## Lebenszyklus und messbare Sperrfrist

**Ziel, noch nicht integrationsgetestet:** Onlinezugriff eines gesperrten Mitarbeiters endet innerhalb von 60 Sekunden, einschließlich aktiver WebSockets. Dafür IdP-Adminänderung als versioniertes Sperrereignis in dauerhafter Plattform-Outbox, Übertragung an Appadapter und pro Request höchstens 30 Sekunden alter Aktivitäts-/Freigabecache. Appadapter löscht lokale Sessions/erhöht Sessionversion und schließt WS. Bleibt der Status nach 60 Sekunden unbekannt, geschützte Mitarbeiterzugriffe fail closed. Retries, Deadletter und Alarm bei fehlendem ACK nach 30 s. Fünfminütiges Access-Token allein reicht für das 60-Sekunden-Ziel nicht; lokale Sessions brauchen Revokation oder Onlineprüfung. Freigabeentzug und Kontolöschung sind getrennte Ereignisse.

Mitarbeitersession: 30 min Inaktivität, maximal 8 h; Finanz-/Plattformadministration kürzer nach Bedarf und erneute MFA bei kritischen Änderungen. IdP-Admins MFA verpflichtend, mindestens zwei betreute Adminidentitäten, kein gemeinsames Standardkonto. Einladungen einmalig/kurzlebig, keine Session aus ungeprüfter E-Mail. Änderungen an fachlichen Rechten bleiben im Appaudit.

Logout: lokale Session sofort löschen, RP-Initiated Logout beim IdP, Post-Logout-URI exakt registrieren. Backchannel-Logout pro App implementieren/prüfen, signierten Logouttoken einschließlich Issuer/Audience/Event/JTI/SID prüfen, replayfest und idempotent. Nicht unterstützte Apps verwenden Revokationsvertrag und Ablaufgrenzen. Ein IdP-Logout löscht aktuell lange JWT-/Cookie-Sessions nicht automatisch: Grundschultafel 30 Tage, Leseflux 8/24 h, Zackboing DB-Session ohne Ablaufprüfung sind konkrete Umbaugründe.

IdP-Ausfall: keine Neuanmeldung; vorhandene Mitarbeitersessions dürfen nur innerhalb oben genannter belegbarer Statusfrist weiterlaufen. Öffentliche TAN-/Eltern-/Posten-/Gastzugänge nach lokaler Policy weiterbetreiben. Offline-Clients können keine sofortige Sperre empfangen; lokale Speicherverschlüsselung/-löschung und maximaler Offlinezeitraum sind je App separat festzulegen. Bei Reconnect Online-Sperre vor Upload prüfen, ungesyncte Nutzdaten verlustarm als gesperrte Wiederherstellungsdatei behandeln. Keine Zusage einer 60-Sekunden-Sperre für bereits offline gespeicherte Daten.

Notfallzugang über lokale Konsole/VPN, individuelle Offline-Recoverycodes, Audit und Alarm; kein öffentliches Auth-Bypass-Header. Schlüsselrotation/Cookies erzwingen Reauthentifizierung. Vollständige browserbasierte Mehr-App-SSO-/Logout-/Sperrtests sind offen; Tests mit gemocktem IdP gelten nur als Bibliotheks-/Applogiknachweis.
