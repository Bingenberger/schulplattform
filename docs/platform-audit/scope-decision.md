# Umfangsbeschluss zur Schulplattform

Stand: 1. November 2026. Entscheider: Florian Emrich. Grundlage: [Audit vom 01.11.2026](README.md) und die anschließende Prüfung dieses Audits.

Dieses Dokument ist **der verbindliche Umfang**. Wo es dem Audit widerspricht, gilt dieses Dokument. Das Audit bleibt als datierter Prüfbefund unverändert; Nachträge in den betroffenen Dateien verweisen hierher.

## 1. Zielbild, neu priorisiert

Das Audit hat SSO als Kern behandelt. Das ist nicht die Priorität des Auftraggebers. Verbindliche Reihenfolge:

1. **Installationsskript**, das alle Dienste gebündelt auf einen nackten Linux-Server bringt.
2. **Zentrale Wartung**, insbesondere Domain- und Basis-URL-Verwaltung, Updates, Backup.
3. **Standalone-Betrieb jeder App bleibt erhalten.** Harte Anforderung, nicht Nebenziel.
4. **SSO ist Kür.** Entfällt, wenn der Aufwand nicht gerechtfertigt ist.

## 2. Beschlüsse

### D1 — Standalone hat Vorrang vor Integration

Jede App behält eine eigenständig funktionsfähige `docker-compose.yml`. Die Plattform legt eine Override-Datei darüber:

```
docker compose -f docker-compose.yml                  # standalone
docker compose -f docker-compose.yml -f platform.yml  # in der Plattform
```

Daraus folgen drei nicht verhandelbare Regeln:

- **Die Plattform ergänzt, sie erzwingt nicht.** Jede App behält ihre eigenen Env-Namen (`SW_*`, `SL_OFFICE_*`, …). Der Adapter übersetzt in Richtung App. Kein Umbenennen auf plattformweite Namen.
- **Jede App behält eigene Datenbank und eigenen Datenbankbenutzer.** Ein gemeinsamer Postgres-Server ist erlaubt, ein gemeinsames Schema nicht. Ein `pg_dump` muss die App jederzeit vollständig herauslösen.
- **OIDC bleibt optional**, lokale Anmeldung bleibt daneben bestehen. Schulwissen erfüllt das heute bereits.

### D2 — Keycloak entfällt zunächst

**Beobachtet:** `schulwissen/kern/oidc.py` implementiert generisches OIDC über Discovery-URL mit Issuer-Prüfung, PKCE S256, State und Nonce. `schulwissen/.env.example:73–83` beschreibt als Anbieter ausdrücklich die Nextcloud-App „OIDC Identity Provider" und nennt `SW_NEXTCLOUD_URL=https://cloud.ggs-ndk.de`.

**Beschluss:** Für die Kür-Stufe dient die vorhandene Schul-Nextcloud als Identity Provider. Kein Keycloak in der ersten Ausbaustufe.

Begründung: spart den gesamten IdP-Betrieb (Realm, Clients, MFA-Verwaltung, Schlüsselrotation, eigenes Backup) sowie geschätzt 0,8–1,25 GiB RAM. Preis: Nextcloud ist als IdP schwächer, insbesondere bei Backchannel-Logout und Administration, und ein Nextcloud-Ausfall verhindert die Anmeldung. Für zwei Apps ist das vertretbar. Keycloak bleibt die dokumentierte Option, falls SSO später auf mehr Apps ausgeweitet wird.

### D3 — SSO nur für zwei Apps

| App | Maßnahme | Aufwand |
| --- | --- | ---: |
| schulwissen | vorhandenen OIDC-Flow gegen Nextcloud konfigurieren, Mapping über `issuer`+`subject` | 3–6 PT SSO + 2–4 PT Mapping |
| gswb | Redaktion hinter Proxy/BFF-Auth; kein Benutzerkonto zu migrieren | 3–6 PT + 0–1 PT |

Summe **8–17 PT**. Alle übrigen Apps behalten ihre lokale Anmeldung.

Zurückgestellt, je 8–20 PT: kompetenz-manager, abgen, fahrradausbildung, leseflux, zackboing. Diese laufen ohne SSO unverändert weiter. Entscheidung erst, nachdem die Plattform im Betrieb ist.

### D4 — Grundschultafel behält lokalen Whiteboard-Login

Kein SSO. Entfallen 9–18 PT.

**Designvorgabe:** Notizbücher liegen strikt pro Konto unter `data/<session.id>/` (`src/app/api/notebooks/route.ts:13`). Die Identität am Whiteboard **ist** die Datengrenze. Umzusetzen ist ein **Kurz-PIN pro Lehrkraft**, kein gemeinsames Gerätekonto — sonst landen alle Notizbücher in einem Topf. Die 30-Tage-Session ist am Whiteboard erwünscht, muss aber gerätegebunden sein.

### D5 — Vier Apps werden zunächst nicht migriert

SL-Journal, schulanmeldung, schulkasse und schuleva bleiben vorerst auf ihrem heutigen Deployment. Ohne SSO bliebe als Gegenleistung für 23–49,5 PT nur Betriebsvereinheitlichung. Sie enthalten zudem die sensibelsten Daten und werden zuletzt angefasst.

schulhelfer und losverkauf werden dagegen migriert (13–28 PT): beide versenden viel Elternpost und haben laut Audit noch keine persistente Outbox, nur einen Hintergrundthread. Das zentrale Relay mit Queue und Retry löst dort ein echtes Problem.

**Folge für den Betrieb:** SL-Journal, schulanmeldung und schulkasse behalten jeweils eigenes TOTP. Es gibt für diese Apps **keine zentrale Sperrung**; die 60-Sekunden-Sperrfrist aus dem Audit greift dort nicht. Erforderlich ist eine schriftliche Austritts-Checkliste pro App, sonst bleiben Konten in genau den Apps mit Finanz- und Diagnostikdaten offen.

### D6 — Backup generisch nach Speichertyp

Statt eines Backup-Adapters pro App deklariert das Manifest nur Engine, Datenbankname und Pfade. Ein zentraler Dienst bedient drei Muster: Postgres über `pg_dump -Fc`, SQLite über die `.backup`-API (**keine Dateikopie**) und Verzeichnis-Snapshot für Uploads. Das deckt 12 der 14 Apps.

Echte Sonderfälle bleiben zwei:
- **SL-Journal:** SQLCipher-Schlüssel müssen mitgesichert werden, sonst ist das Backup wertlos.
- **abgen:** PostgreSQL 18 plus Yjs-Zustand.

## 3. Korrekturen am Audit

### C1 — Sizing unterschätzt die Worker-Zahl

**Beobachtet:** Keine der 14 Apps hat eine Job-Queue (kein Celery, RQ, dramatiq oder huey in `requirements.txt`/`pyproject.toml`). WeasyPrint wird deklariert von schulwissen, schulkasse, schuleva und fahrradausbildung; LibreOffice wird genutzt von kompetenz-manager (`odt_export.py`) und SL-Journal (`pdf_preview.py`). Dokumenterzeugung läuft damit **synchron im Request**.

Die Budgettabelle in `server-sizing.md` rechnet mit einem Worker pro App. Ein Zeugnis- oder Berichtsexport blockiert dann die betroffene App für alle anderen Nutzer. Das ist kein Kapazitäts-, sondern ein Benutzbarkeitsproblem und wird nicht durch mehr vCPU gelöst.

**Korrektur, geschätzt:** mindestens zwei Worker für diese sechs Apps, rund +0,8 GiB Idle und +1,5 GiB Last. abgen ist nicht betroffen, dort ist der PDF-Dienst bereits ein eigener Container und als solcher budgetiert.

### C2 — CPU-Spalte und CPU-Empfehlung widersprechen sich

Die Komponententabelle summiert **5,65 vCPU**, empfohlen werden 4 dedizierte. Beim RAM wurde additiv mit 30 % Reserve gerechnet, bei der CPU nicht. Inhaltlich ist 4 richtig — 5,65 vCPU bei 2,5–7,5 rps ist unplausibel hoch. Die Spalte ist faktisch ein Limit, kein Bedarf, und muss so benannt werden.

### C3 — Lizenzpunkt ist zu hoch gewichtet

**Beobachtet:** In allen 14 Repositories gibt es über die gesamte Historie genau einen Autor (`florian@emrich.in` bzw. `florian@foerster.rocks`, dieselbe Person und zugleich der Auftraggeber).

Für den Anwendungscode ist das keine Freigabe durch Dritte, sondern eine Deklaration von etwa einem halben Tag. Das Audit führt den Punkt als P0-Blocker neben echten Hindernissen; das verzerrt die Entscheidung. Bestehen bleibt die Prüfung von Fremdmaterial, die `licenses.md` korrekt auflistet: igerman98 mit GPL-Text in abgen, OFL-Schriften, Grundschrift CC BY 3.0, Leaflet/OSM sowie Logos, Unterschriften und Briefvorlagen in schulanmeldung und schulkasse.

### C4 — Grundschultafel-Startzugang ist weniger kritisch als dargestellt

**Beobachtet:** `mustChangePassword: true` wird in `src/middleware.ts:37` erzwungen; der erste Login landet zwingend auf `/change-password`. Das Audit nennt es „bekannte Initialkombination" und setzt es auf P0. Zutreffend ist: ein Rotationszwang existiert. Das reale Restrisiko ist nur das Zeitfenster zwischen erstem Start und erstem Login — wer die App zuerst erreicht, wird Administrator. Ein einmaliges Bootstrap-Token bleibt die saubere Lösung, der Punkt ist aber kein P0.

## 4. Aufwand für den beschlossenen Umfang

Geschätzt, eine erfahrene entwickelnde Person, keine neuen Fachfunktionen. Bandbreiten sind keine Termine.

| Paket | Aufwand | Anmerkung |
| --- | ---: | --- |
| Containerisierung aller zu migrierenden Apps | 30–58 PT | Rückgrat; Werte gelten für alle 14, bei zehn Apps entsprechend weniger |
| Zentrale Domain-/Basis-URL-Verwaltung | 16–37 PT | zweiter Hauptwunsch |
| Backup/Restore | 28–59 PT laut Audit, durch D6 realistisch etwa halbiert | generisch nach Speichertyp |
| Zentraler Mailversand | 5,5–16,5 PT | nur fünf Apps versenden überhaupt |
| Installer, Release-/Manifestbasis, Dashboard | ca. 31–57 PT | ohne Keycloak günstiger als im Audit |
| Lizenzdeklaration | 1–3 PT | statt 3–7 PT, siehe C3 |
| SSO-Kür (schulwissen, gswb) | 8–17 PT | streichbar |

**Gesamt ohne SSO etwa 112–231 PT, mit der Kür etwa 120–248 PT.** Zum Vergleich: der im Audit beschriebene Vollumfang mit SSO für alle Apps lag bei 187,5–382,5 PT App-Arbeit plus 36–68 PT Infrastruktur.

Nicht enthalten: die vier zurückgestellten Apps aus D5 (23–49,5 PT) und die fünf zurückgestellten SSO-Umbauten aus D3 (je 8–20 PT).

## 5. Serverdimensionierung, korrigiert

Geschätzt auf Basis der Budgettabelle in `server-sizing.md`, korrigiert um C1 und D2. **Keine Messung.**

| | mit Keycloak | **ohne Keycloak (beschlossen)** |
| --- | ---: | ---: |
| Idle, alle 14 Apps | 3,69 GiB | 2,89 GiB |
| Idle mit Worker-Korrektur | 4,49 GiB | 3,69 GiB |
| Last mit Worker-Korrektur | 10,6 GiB | 9,35 GiB |
| RAM = (Last + 1 GiB OS) × 1,30 | 15,1 GiB | **13,5 GiB** |
| Empfehlung | 16 GB randvoll | **16 GB mit Reserve** |

**Ergebnis: 16 GB RAM und 4 dedizierte vCPU tragen alle 14 Apps**, wenn Keycloak entfällt. 32 GB sind nicht erforderlich. 250 GB SSD bleiben, weil der Plattenbedarf von Medien und Images kommt, nicht vom Login; für einen reduzierten Umfang von zehn Apps genügen etwa 160–200 GB.

Vor der Bestellung zu klären, beides billig: Leerlaufmessung aller vorgesehenen Apps auf dem Zielserver, und die Größe des Playwright-Basisimages für abgen (`mcr.microsoft.com/playwright:v1.64.1-noble`) — der größte einzelne Plattenposten, im Audit nicht gemessen.

Upgrade-Auslöser aus `server-sizing.md` bleiben unverändert gültig.

## 6. Unabhängig vom Umfang zu erledigen

Diese Punkte fallen auch dann an, wenn nur eine einzige App migriert wird:

1. **gswb-Redaktion schließen.** `grundschul_woerterbuch/routes.py:102–139`: `/review`, `review_approve`, `review_toggle_regeneration` und `review_save` haben keine Authentifizierung; CORS steht auf `*`. Im Audit durch anonymen POST bestätigt.
2. **Bekannter Dev-SECRET_KEY** in `gswb/grundschul_woerterbuch/__init__.py:26`.
3. **Gemeinsames `ADMIN_PASSWORD`** in losverkauf, ohne Admin-Benutzertabelle.
4. **Zackboing-Session ohne Ablaufprüfung** in `userForToken`, Cookie 90 Tage.
5. **Bootstrap-Token für Grundschultafel** statt des Erstzugangs, siehe C4.

## 7. Offen

- Daten- und Medienbestand je App sowie jährlicher Zuwachs. Bestimmt SSD und Offsite-Bedarf.
- Zielserver und dessen tatsächliche Ressourcen.
- RPO/RTO. 24 h / 4 h sind weiterhin nur Diskussionsgrundlage.
- Fremdmaterial-Freigaben nach C3.
- Ob die fünf zurückgestellten SSO-Umbauten je erfolgen.
