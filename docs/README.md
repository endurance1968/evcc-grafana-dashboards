# EVCC mit VictoriaMetrics und Grafana: Einstieg

Diese Datei ist der schnellste Einstieg für einen Neueinsteiger, der heute:

- EVCC nutzt
- bisher InfluxDB nutzt
- und auf VictoriaMetrics plus den neuen EVCC-Dashboard-Satz umsteigen will

## Empfohlene Reihenfolge

1. VictoriaMetrics installieren
2. Grafana installieren
3. bestehende InfluxDB-Rohdaten einmalig nach VictoriaMetrics übernehmen
4. tägliche Rollups erzeugen
5. Grafana mit VictoriaMetrics verbinden
6. EVCC-Dashboards deployen
7. stündlichen Rollup-Lauf einrichten

## Je nach Betriebsart

### Klassische Debian-VM oder LXC

- VictoriaMetrics:
  - `victoriametrics-install-debian-13.md`
- Grafana:
  - `grafana-install-debian-13.md`

### Docker

- VictoriaMetrics:
  - `victoriametrics-install-docker.md`
- Grafana:
  - `grafana-install-docker.md`

## Danach: InfluxDB nach VictoriaMetrics migrieren

Wenn du schon EVCC + InfluxDB hast, geht es hier weiter:

- `influx-to-vm-migration.md`

Diese Anleitung enthält:

- einmaligen Rohdatenimport von InfluxDB nach VictoriaMetrics
- initialen Rollup-Backfill
- laufenden stündlichen Rollup-Betrieb

## Danach: Grafana und Dashboards einrichten

Wenn VictoriaMetrics läuft und die Daten vorhanden sind, geht es hier weiter:

- `grafana-vm-dashboard-setup.md`

Diese Anleitung enthält:

- VictoriaMetrics-Datasource in Grafana anlegen
- Service-Account-Token erzeugen
- ersten Dashboard-Deploy
- späteres Dashboard-Update

## Zusätzliche Enduser-Dokus

- kurzer Deploy-Einstieg:
  - `deployment-readme.md`
- technische Deploy-Details:
  - `vm-dashboard-install.md`

## Merksatz

Für den Umstieg von EVCC + InfluxDB auf EVCC + VictoriaMetrics brauchst du praktisch immer genau diese drei Blöcke:

1. VictoriaMetrics zum Laufen bringen
2. InfluxDB-Daten und Rollups nach VictoriaMetrics bringen
3. Grafana mit VictoriaMetrics verbinden und Dashboards deployen

