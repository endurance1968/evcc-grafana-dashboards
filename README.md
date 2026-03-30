# EVCC Grafana Dashboards

Dieses Repository enthält den aktuellen VictoriaMetrics-basierten Dashboard-Satz für EVCC.

Aktive Bereiche:

- `dashboards/original/en`
- `dashboards/translation/<language>`
- `scripts/`
- `docs/`

Wichtige Einstiege:

- Installation für Endnutzer:
  - [`docs/deployment-readme.md`](./docs/deployment-readme.md)
- Grafana auf Debian 13 installieren:
  - [`docs/grafana-install-debian-13.md`](./docs/grafana-install-debian-13.md)
- Grafana mit VictoriaMetrics und EVCC-Dashboards:
  - [`docs/grafana-vm-dashboard-setup.md`](./docs/grafana-vm-dashboard-setup.md)
- Migration von InfluxDB zu VictoriaMetrics:
  - [`docs/influx-to-vm-migration.md`](./docs/influx-to-vm-migration.md)
- VictoriaMetrics auf Debian 13 installieren:
  - [`docs/victoriametrics-install-debian-13.md`](./docs/victoriametrics-install-debian-13.md)
- technische Installationsdetails:
  - [`docs/vm-dashboard-install.md`](./docs/vm-dashboard-install.md)
- Rollup- und Datenmodell:
  - [`docs/design/victoriametrics-aggregation-guide.md`](./docs/design/victoriametrics-aggregation-guide.md)
  - [`docs/design/victoriametrics-rollup-design.md`](./docs/design/victoriametrics-rollup-design.md)
  - [`docs/design/victoriametrics-schema-reference.md`](./docs/design/victoriametrics-schema-reference.md)
- Test- und Deploy-Skripte:
  - [`scripts/README.md`](./scripts/README.md)
  - [`scripts/test/README.md`](./scripts/test/README.md)
  - [`scripts/localization`](./scripts/localization)

Legacy-Referenz:

- Der alte Influx-Dashboard-Satz bleibt nur noch als statische Referenz unter
  [`dashboards/influx-legacy/original/de`](./dashboards/influx-legacy/original/de).

