# EVCC Grafana Dashboards

Deutsch: Dieses Repository stellt EVCC-Dashboards fuer VictoriaMetrics und Grafana bereit. Es richtet sich an neue EVCC-Nutzer mit VictoriaMetrics ebenso wie an Nutzer, die von bestehenden InfluxDB-basierten EVCC-Dashboards auf VictoriaMetrics wechseln moechten, ohne die gewohnten Auswertungen fuer PV, Netz, Hausverbrauch, Speicher, Fahrzeuge, Ladepunkte, Energiefluesse und Kosten zu verlieren.

English: This repository contains VictoriaMetrics-based Grafana dashboards for EVCC. The English version of this README is available here: [README_EN.md](./README_EN.md).

Die Arbeit baut auf den frueheren InfluxDB-basierten EVCC-Dashboards von Carsten auf:
[ha-puzzles/evcc-grafana-dashboards](https://github.com/ha-puzzles/evcc-grafana-dashboards).
Vielen Dank an Carsten fuer die starke Vorarbeit. Dieses Repository liefert den VictoriaMetrics-Pfad mit Migration, Tages-Rollups, lokalisierten Dashboard-Varianten, optionalen Zusatz-Auswertungen und Deploy-Skripten fuer Grafana.
Ich versuche, den Stand mit Carstens Projekt synchron zu halten. Gerade bei neuen Funktionen kann es deshalb gelegentlich zu Breaking Changes kommen. Wenn du frisch migrierst, ist es sinnvoll, InfluxDB ueber Telegraf zunaechst weiter parallel zu befuellen, bis die VictoriaMetrics-Installation vollstaendig validiert ist.

Beispiel-Dashboard, automatisch aus der aktuellen Screenshot-Galerie:

<a href="./docs/screenshots/README.md">
  <img src="./docs/screenshots/today.png" alt="EVCC Today Dashboard Beispiel" width="900">
</a>

Weitere Beispiele der Dashboards findest du in der [Screenshot-Galerie](./docs/screenshots/README.md).

## Was dieses Repository liefert

- eine vollstaendige EVCC-Dashboard-Sammlung fuer VictoriaMetrics
- generierte Dashboard-Uebersetzungen auf Basis der englischen Quelldashboards
- Grafana-13-TAB-Dashboards als unterstuetztes Navigationsmodell
- Deploy-Skripte fuer Erstimport und Updates
- ein Rollup-Skript fuer taegliche Langzeit-Metriken
- optionale PV-Gestehungskosten/LCOE-Auswertung mit Investment-Datei und Wochen-Helper
- PV-Anlagenvergleiche fuer Jahresertrag und spezifischen Ertrag (`kWh/kWp`)
- EVCC-Gruenanteil als KPI in Tages- und Langzeitansichten
- optionale historische Energieimporte, z. B. SMA-PV-Ertraege und SMA-Energiebilanzen als EVCC-kompatible Tageswerte
- optionaler VRM-Batteriefluss-Import fuer zusaetzliche Speicherwirkungsgrad-Auswertungen
- einen optionalen [Netzsteuerungs-Audit-Collector](./docs/de/grid-control-audit.md) fuer den Daily-Details-Tab
- Dokumentation fuer die Migration von InfluxDB nach VictoriaMetrics
- Installations- und Betriebsanleitungen fuer VictoriaMetrics, EVCC/Telegraf-Live-Ingest, Grafana, Migration und Dashboard-Deployment
- Release Notes und Screenshots fuer die empfohlenen Grafana-13-TAB-Dashboards

## Was die Dashboards abdecken

Die Dashboards enthalten Tages-, Monats-, Jahres- und All-Time-Ansichten.

- `Today` zeigt den aktuellen Tag: PV, Netz, Hausverbrauch, Speicher, Ladepunkte, Energiefluss, Forecast, Autarkie, Eigenverbrauch, Gruenanteil und Kosten.
- `Today - Details` zeigt zusaetzlich Phasen, Lade-Metriken, Rohhistorien, Preisdetails und optional Netzsteuerungs-/14a-Auditdaten.
- `Today - Mobile` ist eine kompakte Ansicht fuer kleinere Bildschirme.
- `Month`, `Year` und `All-time` zeigen laengere Zeitraeume auf Basis der taeglichen `evcc_*` Rollups, inklusive Finanz-, PV-Anlagen- und Anlagenvergleichsansichten, wenn die optionalen Daten vorhanden sind.

Typische Anwendungsfaelle:

- PV-Produktion, Eigenverbrauch und Autarkie verfolgen
- Bezug und Einspeisung ueber die Zeit vergleichen
- Fahrzeuge und Ladepunkte nach Energie, Kosten und Nutzung auswerten
- Speicherladung, Entladung und SOC-Verhalten analysieren
- Preisentwicklung, Importkosten und Lastverteilung visualisieren
- PV-Anlagen ueber Jahresertrag, spezifischen Ertrag und optional Gestehungskosten vergleichen
- Gruenanteil, Autarkie und Eigenverbrauch als getrennte KPIs beobachten
- optionale Netzsteuerungs-/14a-Eingriffe auditieren, wenn EVCC und der Collector entsprechende Daten liefern
- historische EVCC-Daten von InfluxDB nach VictoriaMetrics migrieren und dort weiterbetreiben
- fehlende historische EVCC-Jahre optional mit kompatiblen Tagesimporten aus externen Quellen ergaenzen

## Einstieg

Der zentrale Einstieg fuer Installation, Migration, Live-Ingest und Dashboard-Deployment ist:

- [docs/README.md](./docs/README.md)
- [Release Notes](./docs/de/release-notes.md)
