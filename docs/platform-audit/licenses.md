# Lizenz-/Distributionsbefund

> **Nachtrag vom 01.11.2026 — Gewichtung korrigiert.** Siehe
> [scope-decision.md](scope-decision.md), C3. In allen 14 Repositories gibt es über die
> gesamte Historie **genau einen Autor** (`florian@emrich.in` bzw.
> `florian@foerster.rocks` — dieselbe Person und zugleich der Auftraggeber). Für den
> Anwendungscode ist das keine Freigabe durch Dritte, sondern eine Deklaration von etwa
> einem halben Tag, kein P0-Blocker. Unverändert gültig bleibt die Prüfung des
> Fremdmaterials in der Tabelle unten: igerman98 mit GPL-Text in abgen, OFL-Schriften,
> Grundschrift CC BY 3.0, Leaflet/OSM sowie Logos, Unterschriften und Briefvorlagen.

**Beobachtet am geprüften Commit:** Nur SL-Journal enthält eine projektweite LICENSE (MIT, Copyright Florian Förster). In den übrigen 13 Appbäumen wurde keine projektweite Lizenzdatei gefunden. package.json ohne Lizenzangabe erteilt ebenfalls keine Freigabe. Private Zugriffserlaubnis ist nicht gleich Distributionsrecht. Für ein öffentlich oder an weitere Schulen verteiltes Bundle ist die Freigabe daher offen/blockiert. Für die rein lokale technische Prüfung wurde nichts veröffentlicht.

[GitHub erklärt die fehlende Lizenzfreigabe bei nicht lizenzierten Repositories](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository). Dies ist keine verbindliche rechtliche Gesamtprüfung; bestehende zusätzliche Vereinbarungen mit Rechteinhabern wurden nicht vorgelegt. Ein Orchestrierungsrepository mit getrennten Images vermeidet die Lizenzprüfung der Apps/Assets nicht.

| App | Projektlizenz beobachtet | Assets/Abhängigkeiten und offener Punkt |
| --- | --- | --- |
| schulwissen | keine Datei | Lehrplan-PDF/XLSX, Texte, Bilder/Fonts und Frontendeditor getrennt prüfen; UV/npm-SBOM und Rechtefreigabe |
| fahrradausbildung | keine Datei | idb ISC, Phosphor MIT, Leaflet BSD-2-Dateien; Kartenkacheln und schulische Vorlagen separat |
| schulanmeldung | keine Datei; privat | Logos, Unterschrift, Brief-/Diagnostikvorlagen und PDF/ODT nicht pauschal weitergeben; Python-Abhängigkeiten |
| SL-Journal | MIT | Editor-/Icon-/Excalidraw-Lizenzhinweise vorhanden; Python/SQLCipher-/LibreOffice-/Popplerbestand im Image zusätzlich erfassen |
| kompetenz-manager | keine Datei | Bootstrap MIT und Sora/Nunito OFL-Dateien vorhanden; Diagnosematerial/ODT/Logos separat |
| leseflux | keine Datei | Lesetexte, Fonts, QR-/Frontend-/Prisma-/Argon2abhängigkeiten und native Engine erfassen |
| schuleva | keine Datei | Fragebögen, Schriftarten, Grafiken, WeasyPrint/Matplotlib inkl. transitiver Ressourcen |
| gswb | keine Datei | erzeugte Wörter/Audio/Bilder nicht aus Dateinamen lizenzieren; KI-Vertrags-/Herkunftsfragen offen |
| grundschultafel | keine Lizenzdatei; README: „Nicht zur Weitergabe bestimmt“ | public/assets und Symbole/Schriften; externe Galerie/YouTube gestatten keine pauschale Assetweitergabe |
| schulkasse | keine Datei | Briefvorlagen, schulische Logos/Schriften und native PDFabhängigkeiten |
| abgen | keine Datei | Wörterbuchdateien igerman98 mit beigefügter Lizenz (GPL-Text), mehrere OFL-Fonts, Grundschrift CC BY 3.0; Attribution/Reserved Font Names und Originaltexte erhalten |
| losverkauf | keine Datei | Leaflet/OSM, Karten-/Bezirksdaten und Bezirke.pdf; ReportLab und sonstige Laufzeitpakete |
| schulhelfer | keine Datei | ReportLab/Frontendassets und personenbezogene Vorlagen getrennt; vollständige Python-SBOM offen |
| zackboing | keine Datei | bessere-sqlite/native SQLite, Socket.IO und Medien aus externer Galerie; Gallery-/Quizmedienrechte separat |

Dateilisten je Repo in [Quellinventar](evidence/source-inventory.json), commitgebundene Einstiegsbelege in den Appberichten. Positive Einzellizenzfunde sind keine Behauptung, dass alle Assets frei lizenziert sind.

**Offen:** vollständige transitive Lizenz-/Assetprüfung aller tatsächlich gebauten Produktionsimages. Deklarierte Paketnamen genügen nicht; OS-Pakete, native Bibliotheken, Browserbundle, generierte und nachgeladene Assets müssen einbezogen werden. Es wurde keine uneingeschränkte gemeinsame Distribution als zulässig zertifiziert.

Freigabeverfahren: Rechteinhaber benennt Projektlizenz/zusätzliche Vereinbarungen je App → aus Lockfiles und installierten Images SPDX/CycloneDX-SBOM samt Hash/Version/Quelle erzeugen → Assetmanifest mit Herkunft, Lizenz, Attribution und Ausnahmen → Notice-/Lizenztexte in Images/Bündel → Copyleft-/Quellcode-/Änderungshinweise und Fontbedingungen je tatsächlichem Paket klären → ungeklärte Assets entfernen/ersetzen oder separat bereitstellen → dokumentierte Releasefreigabe. [SPDX](https://spdx.dev/learn/areas-of-interest/software-licensing/) unterstützt standardisierte Lizenzinventare; [OFL](https://openfontlicense.org/) beschreibt Schriftbedingungen. Reine Bündelung und Codeableitung nicht gleichsetzen, Rechte aber für jede ausgelieferte Komponente prüfen.
