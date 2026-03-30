# EVCC Grafana Dashboards

Dieses Repository bündelt einen aktuellen Dashboard-Satz für [EVCC](https://evcc.io/) auf Basis von VictoriaMetrics statt InfluxDB. Es richtet sich an Nutzer, die ihre bestehende EVCC-Visualisierung modernisieren oder neu aufbauen wollen, ohne die gewohnte fachliche Sicht auf PV, Netz, Hausverbrauch, Batterie, Fahrzeuge und Kosten zu verlieren.

Ausgangspunkt war der frühere EVCC-Grafana-Dashboard-Satz für InfluxDB von Carsten:
[ha-puzzles/evcc-grafana-dashboards](https://github.com/ha-puzzles/evcc-grafana-dashboards).
Dieser alte Stand bleibt hier nur noch als statische Referenz erhalten. Dieses Repository ergänzt ihn um einen produktiv nutzbaren VictoriaMetrics-Pfad mit Migration, Rollups, mehrsprachigen Dashboard-Varianten und einfachen Deploy-Skripten für Grafana.

Speziell bietet dieses Repository:

- einen vollständigen VictoriaMetrics-basierten Dashboard-Satz für EVCC
- Übersetzungen für mehrere Sprachen auf Basis eines englischen Originals
- Skripte für das initiale Dashboard-Deployment und spätere Updates
- ein Rollup-Skript für tägliche Aggregationen auf VictoriaMetrics
- Migrationsdokumentation für den Umstieg von InfluxDB auf VictoriaMetrics
- Enduser-Dokumentation für Installation, Migration, Grafana-Anbindung und Betrieb

## Was die Dashboards bieten

Die Dashboards decken die wichtigsten EVCC-Sichten für Tages-, Monats-, Jahres- und Gesamtauswertungen ab.

- `Today` zeigt die aktuelle Leistungs- und Zustandslage über den Tag:
  PV, Netz, Haus, Batterie, Ladepunkte, Leistungsfluss, Forecast, Autarkie, Eigenverbrauch und laufende Kosten.
- `Today - Details` geht tiefer in Einzelverläufe, Phasen, Ladepunkte, Metriken und Preise.
- `Today - Mobile` liefert eine kompaktere Ansicht für kleinere Displays.
- `Monat`, `Jahr` und `All-time` zeigen Energie-, Kosten-, Batterie- und Fahrzeugauswertungen über längere Zeiträume.

Damit kann man unter anderem:

- PV-Erzeugung, Eigenverbrauch und Autarkie nachvollziehen
- Netzbezug und Einspeisung über verschiedene Zeiträume vergleichen
- Ladepunkte und Fahrzeuge hinsichtlich Energie, Kosten und Nutzung auswerten
- Batterieverhalten inklusive Lade-/Entladeenergie und SOC betrachten
- Preisentwicklungen, Importkosten und Lastverteilungen sichtbar machen
- historische EVCC-Daten aus InfluxDB nach VictoriaMetrics übernehmen und dort weiterbetreiben

## Einstieg

Für einen kompletten Neueinstieg oder Umstieg von EVCC + InfluxDB auf EVCC + VictoriaMetrics geht es hier weiter:

- [docs/README.md](./docs/README.md)

Dort ist der End-to-End-Weg beschrieben:

1. VictoriaMetrics installieren
2. Grafana installieren
3. InfluxDB-Daten nach VictoriaMetrics migrieren
4. Rollups erzeugen
5. Grafana anbinden
6. Dashboards deployen
