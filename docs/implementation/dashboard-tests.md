# Hinweise zu den Dashboardprüfungen

Die ersten Unit-/Protokolltests und der erste Containerbuild bestanden.
Der erste Ende-zu-Ende-Lauf brach beim tatsächlichen Appstart ab, weil das
Prüfskript das kurze Socket-Verbindungs-Timeout auch beim anschließenden Lesen
verwendete. Die Bereinigung traf dadurch auf eine noch laufende Verwaltungsaktion.

Das Prüfskript setzt nun nach der TLS-Verbindung das längere Aktions-Timeout und
beendet laufende Socketanfragen, bevor es den Pilot stoppt.
[Kommandos des ersten Versuchs](evidence/dashboard-container-attempt1.json)
bleiben erhalten. Anschließende vollständige Läufe bestanden; das
[aktuelle Ergebnis](evidence/dashboard-container.json) und die
[aktuellen Kommandos](evidence/dashboard-container-operations.json) beziehen sich
auf den korrigierten Ablauf.

Beim Zusammenspiel mit dem allgemeinen Pilot-Start wurde außerdem sichergestellt,
dass zuvor gesetzte Wartungsrouten nach erfolgreicher Readiness wieder freigegeben
werden. Der Lebenszyklustest wurde mit dieser gemeinsamen Routenerzeugung erneut
erfolgreich ausgeführt. Domainänderungen und App-Lebenszyklus teilen eine Sperre.

Es wurden keine echten Administrationskonten angelegt. Die Containerprofile und
Zugangsdaten dieser Prüfungen sind synthetisch; Testvolumes bleiben erhalten.
