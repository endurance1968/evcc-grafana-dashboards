# EVCC Grafana Dashboards

Deutsch: Dieses Repository stellt EVCC-Dashboards fuer VictoriaMetrics und Grafana bereit. Es richtet sich an neue EVCC-Nutzer mit VictoriaMetrics ebenso wie an Nutzer, die von bestehenden InfluxDB-basierten EVCC-Dashboards auf VictoriaMetrics wechseln moechten, ohne die gewohnten Auswertungen fuer PV, Netz, Hausverbrauch, Batterie, Fahrzeuge, Ladepunkte, Energiefluesse und Kosten zu verlieren.

English: This repository contains VictoriaMetrics-based Grafana dashboards for EVCC. The English version of this README is available here: [README_EN.md](./README_EN.md).

Die Arbeit baut auf den frueheren InfluxDB-basierten EVCC-Dashboards von Carsten auf:
[ha-puzzles/evcc-grafana-dashboards](https://github.com/ha-puzzles/evcc-grafana-dashboards).
Vielen Dank an Carsten fuer die starke Vorarbeit. Dieses Repository liefert den VictoriaMetrics-Pfad mit Migration, Tages-Rollups, lokalisierten Dashboard-Varianten und Deploy-Skripten fuer Grafana.

Beispiel-Dashboard:

![EVCC Dashboard Beispiel](./images/dashboard-example-today.png)

Weitere Beispiele der Dashboards findest du in der [Screenshot-Galerie](./docs/screenshots/README.md).

## Was dieses Repository liefert

- eine vollstaendige EVCC-Dashboard-Sammlung fuer VictoriaMetrics
- generierte Dashboard-Uebersetzungen auf Basis der englischen Quelldashboards
- Grafana-13-TAB-Dashboards als unterstuetztes Navigationsmodell
- Deploy-Skripte fuer Erstimport und Updates
- ein Rollup-Skript fuer taegliche Langzeit-Metriken
- Dokumentation fuer die Migration von InfluxDB nach VictoriaMetrics
- Installations- und Betriebsanleitungen fuer VictoriaMetrics, EVCC/Telegraf-Live-Ingest, Grafana, Migration und Dashboard-Deployment
- Release Notes und Screenshots fuer die empfohlenen Grafana-13-TAB-Dashboards

## Was die Dashboards abdecken

Die Dashboards enthalten Tages-, Monats-, Jahres- und All-Time-Ansichten.

- `Today` zeigt den aktuellen Tag: PV, Netz, Hausverbrauch, Batterie, Ladepunkte, Energiefluss, Forecast, Autarkie, Eigenverbrauch und Kosten.
- `Today - Details` zeigt zusaetzlich Phasen, Lade-Metriken, Rohhistorien und Preisdetails.
- `Today - Mobile` ist eine kompakte Ansicht fuer kleinere Bildschirme.
- `Month`, `Year` und `All-time` zeigen laengere Zeitraeume auf Basis der taeglichen `evcc_*` Rollups.

Typische Anwendungsfaelle:

- PV-Produktion, Eigenverbrauch und Autarkie verfolgen
- Netzbezug und Einspeisung ueber die Zeit vergleichen
- Fahrzeuge und Ladepunkte nach Energie, Kosten und Nutzung auswerten
- Batterie-Ladung, Entladung und SOC-Verhalten analysieren
- Preisentwicklung, Importkosten und Lastverteilung visualisieren
- historische EVCC-Daten von InfluxDB nach VictoriaMetrics migrieren und dort weiterbetreiben

## Einstieg

Der zentrale Einstieg fuer Installation, Migration, Live-Ingest und Dashboard-Deployment ist:

- [docs/README.md](./docs/README.md)
- [Release Notes](./docs/release-notes.md)
