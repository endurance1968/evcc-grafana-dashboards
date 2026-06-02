# EVCC Grafana Dashboards

This repository provides VictoriaMetrics-based dashboards for [EVCC](https://evcc.io/). It is intended both for new EVCC users starting with VictoriaMetrics and for users who want to move away from an InfluxDB-based EVCC dashboard setup without losing the familiar views for PV, grid, home consumption, battery, vehicles, charging points, energy flows, and costs.

It builds on the earlier InfluxDB-based EVCC dashboard work by Carsten:
[ha-puzzles/evcc-grafana-dashboards](https://github.com/ha-puzzles/evcc-grafana-dashboards).
Many thanks to Carsten for the excellent groundwork. This repository provides the VictoriaMetrics implementation path with migration tooling, daily rollups, localized dashboard variants, and Grafana deploy scripts.

Example dashboard:

![EVCC dashboard example](./images/dashboard-example-today.png)

More dashboard examples are available in the [screenshot gallery](./docs/screenshots/README_EN.md).

## What this repository adds

- a complete VictoriaMetrics-based EVCC dashboard collection
- generated dashboard translations based on the English source dashboards
- Grafana 13 TAB dashboards as the supported navigation model
- deploy scripts for first-time imports and later updates
- a rollup script for daily long-range dashboard metrics
- documentation for InfluxDB to VictoriaMetrics migration
- end-user guides for VictoriaMetrics, EVCC/Telegraf live ingest, Grafana, migration, and dashboard deployment
- curated release notes and screenshots for the recommended Grafana 13 TAB dashboards

## What the dashboards cover

The dashboards include day, month, year, and all-time views.

- `Today` focuses on the current day: PV, grid, home, battery, charging points, energy flow, forecast, autarky, self-consumption, and costs.
- `Today - Details` goes deeper into phases, charging metrics, raw histories, and pricing details.
- `Today - Mobile` is a compact layout for smaller screens.
- `Month`, `Year`, and `All-time` provide longer-range energy, cost, battery, and vehicle analysis based on daily rollups.

Typical use cases:

- track PV production, self-consumption, and autarky
- compare grid import and feed-in over time
- analyze vehicles and charging points by energy, cost, and usage
- inspect battery charge, discharge, and SOC behavior
- visualize pricing trends, import cost, and load distribution
- migrate historic EVCC data from InfluxDB to VictoriaMetrics and continue operating there

## Getting started

For the full end-to-end path from EVCC + InfluxDB to EVCC + VictoriaMetrics + Grafana, continue here:

- [docs/en/README.md](./docs/README_EN.md)
- [release notes](./docs/en/release-notes.md)
