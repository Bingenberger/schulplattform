# Tatsächlich erfasste Messdaten

**Keine neue Last- oder Kapazitätsmessung des Plattformstacks.** Die früheren
Auditmessungen werden nicht auf die jetzige Umsetzung übertragen.

Lokaler amd64-gswb-Build: Docker meldet **190.572.022 Byte** Imagegröße
(rund 181,74 MiB). Das ist die Docker-Imagemetadaten-Größe, kein tatsächlich belegter
zusätzlicher Plattenplatz und kein RAM-Verbrauch. Basisimage Python 3.12.12
slim-bookworm mit fixiertem Digest, pip-Installation aus Hash-Lockfile, zwei
Gunicorn-Worker. [Rohdaten](../implementation/evidence/gswb-image.json),
[Buildprotokoll](../implementation/evidence/gswb-build.log).

Keine Leerlauf-/Spitzen-RAM-, CPU-, p50/p95/p99-, I/O- oder Queue-Messung vorgenommen.
Kein 60-Minuten-Dauerlauf. Playwright-Imagegröße von abgen nicht gemessen.
Die geschätzten 16 GB RAM/4 vCPU werden dadurch weder bestätigt noch widerlegt.
