# Verbleibende Entscheidungen und Blocker

Eine Schule, 24 Lehrkräfte und maximal zehn gleichzeitige Nutzer sind bestätigt und keine offene Frage mehr. Alle 14 Repositories sind zugänglich.

| Verbleibender Punkt | Wirkung / verantwortlicher nächster Schritt |
| --- | --- |
| Daten-/Medienbestand je App und jährlicher Zuwachs | Schule erhebt DB-/Upload-/Audio-/Journalgrößen ohne Datenweitergabe; bestimmt SSD-/Offsitebedarf und RTO |
| Vorhandener Zielserver und verfügbare CPU-/RAM-/SSD-/Netzressourcen | Bestimmt realen Benchmark und ob 4 dedizierte bzw. 6 geteilte vCPU/16 GB/250 GB als Startplan passt |
| Verfügbarkeit/RPO/RTO und Veranstaltungsspitzen | Täglicher Unterricht vs. kritische Kassen-/Buchungsphasen; 24h/4h nur Diskussionsziel, bei Bedarf RPO 15 min und HA neu planen |
| Auswahl: alle 14 dauerhaft betreiben oder zunächst Pilot-/Bedarfsapps | Reduziert Fixlast und Einführungsaufwand; Ausblenden/Stoppen/Löschen bleiben getrennt |
| Projektlizenzen und Weitergaberechte für 13 Apps, Vorlagen und Medien | Gemeinsame Distribution blockiert, bis Rechtefreigaben vorliegen; lokale Analyse ist durchgeführt |
| Soll SL-Journal Einzelkonto bleiben, wer darf es verwenden? | Ein Subject oder dedizierte Instanz ist deutlich kleiner als echtes Mehrbenutzer-/Besitzmodell; keine pauschale Lehrkräftefreigabe |
| KI-/YouTube-/Galerie-/Kartendienste erlaubt oder vollständig offline? | gswb-Handschriftanalyse nicht gleichwertig lokal vorhanden; externe Funktionen ersetzen/abschalten oder vertraglich freigeben |
| Mitarbeiter-Appfreigaben und fachliche Verantwortlichkeiten | Appadapter/Revokation und Rechteabnahme; Plattformadmin wird nicht automatisch Kassen-/Journaladmin |
| Domain-/SMTPbetreiber und zulässige Absender | DNS, Zertifikate, SPF/DKIM/DMARC und Upstreamzugang werden außerhalb des Audits eingerichtet; keine Produktivmails/DNSänderungen erfolgt |
| Vollständige Produktions-/ARM64-/Last-/Restoreabnahme | Host ist geteilt und kein Ziel-LTS-System; praktische Teilnachweise sind in tests.md, offene Abnahmen im Roadmapplan |
| TOTP-Zeitabhängigkeit im Schulanmeldungs-Bestandstest | Ein Gesamtlauffehler, Einzeltest bestanden; deterministischer gleicher Zeitschritt vor Release erforderlich, kein nachgewiesener MFA-Bypass aus diesem einen Test |
