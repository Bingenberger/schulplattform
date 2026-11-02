# Tatsächlich erfasste Messdaten

**Keine neue Last- oder Kapazitätsmessung des Plattformstacks.** Frühere
Auditmessungen werden nicht auf die aktuelle Umsetzung übertragen.

Docker meldet für die lokal gebauten amd64-Images:

| App | Imagegröße laut Docker |
| --- | ---: |
| gswb | 190.572.022 Byte |
| schulwissen | 424.460.181 Byte |
| Dashboard | 148.103.491 Byte |

[gswb-Rohdaten](../implementation/evidence/gswb-image.json),
[schulwissen-Rohdaten](../implementation/evidence/schulwissen-image.json),
[Dashboard-Rohdaten](../implementation/evidence/dashboard-image.json).
Die drei Images verwenden das fixierte Python-3.12.12-Basisimage. gswb installiert aus einem
Hash-Lockfile, schulwissen aus uv.lock. schulwissen enthält zusätzlich Pango und
Schriften sowie komprimierte Produktions-Static-Dateien.

Die Werte sind Docker-Imagemetadaten, kein zusätzlicher physischer Plattenverbrauch
und kein RAM-Verbrauch. Gemeinsame Layer dürfen nicht mehrfach als belegte SSD-
Kapazität addiert werden.

Keine Leerlauf-/Spitzen-RAM-, CPU-, p50/p95/p99-, I/O- oder Queue-Messung vorgenommen.
Kein 60-Minuten-Dauerlauf. Playwright-Imagegröße von abgen nicht gemessen.
Die geschätzten 16 GB RAM/4 vCPU werden dadurch weder bestätigt noch widerlegt.
