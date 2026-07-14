# EVCC Grafana Dashboards

This repository provides VictoriaMetrics-based dashboards for [EVCC](https://evcc.io/). It is intended both for new EVCC users starting with VictoriaMetrics and for users who want to move away from an InfluxDB-based EVCC dashboard setup without losing the familiar views for PV, grid, home consumption, battery, vehicles, charging points, energy flows, and costs.

It builds on the earlier InfluxDB-based EVCC dashboard work by Carsten:
[ha-puzzles/evcc-grafana-dashboards](https://github.com/ha-puzzles/evcc-grafana-dashboards).
Many thanks to Carsten for the excellent groundwork. This repository provides the VictoriaMetrics implementation path with migration tooling, daily rollups, localized dashboard variants, optional add-on analytics, and Grafana deploy scripts.

Example dashboard, automatically sourced from the current screenshot gallery:

<a href="./docs/screenshots/README_EN.md">
  <img src="./docs/screenshots/today.png" alt="EVCC Today dashboard example" width="900">
</a>

More dashboard examples are available in the [screenshot gallery](./docs/screenshots/README_EN.md).

## What this repository adds

Baseline scope for a plain EVCC/VM setup:

- Complete VictoriaMetrics-based EVCC dashboard collection
- Generated dashboard translations based on the English source dashboards
- Grafana 13 TAB dashboards as the supported navigation model
- Deploy scripts for first-time imports and later updates
- Rollup script for daily long-range metrics from EVCC raw data in VictoriaMetrics
- PV source comparisons for yearly energy and specific yield (`kWh/kWp`) when EVCC or imported PV daily values provide the data
- EVCC green share as a KPI in daily and long-range views
- Documentation for InfluxDB to VictoriaMetrics migration
- End-user guides for VictoriaMetrics, EVCC/Telegraf live ingest, Grafana, migration, and dashboard deployment
- Curated release notes and screenshots for the recommended Grafana 13 TAB dashboards

Optional add-on features with their own collectors, importers, or helper scripts:

- PV generation cost/LCOE analytics require an investment file and the investment/PV cost helper
- Historic SMA PV yield and SMA energy balance data require separate import runs that write EVCC-compatible daily values to VictoriaMetrics
- VRM battery efficiency requires the optional VRM battery-flow import and writes additional `evcc_vrm_*` metrics
- Grid-control/14a audit data requires the optional [grid-control audit collector](./docs/en/grid-control-audit.md) and then appears in the Daily Details tab
- Missing historic EVCC years can optionally be filled with compatible daily imports from external sources

## What the dashboards cover

The dashboards include day, month, year, and all-time views.

- Dashboard `Today` focuses on the current day: PV, grid, home, battery, charging points, energy flow, forecast, autarky, self-consumption, green share, and costs.
- Dashboard `Today - Details` goes deeper into phases, charging metrics, raw histories, pricing details, and optional grid-control/14a audit data.
- Dashboard `Today - Mobile` is a compact layout for smaller screens.
- Dashboards `Month`, `Year`, and `All-time` provide longer-range energy, cost, battery, vehicle, finance, and PV-source analysis based on daily rollups when the optional data is available.

Typical use cases:

- Track PV production, self-consumption, and autarky
- Compare grid import and feed-in over time
- Analyze vehicles and charging points by energy, cost, and usage
- Inspect battery charge, discharge, and SOC behavior
- Visualize pricing trends, import cost, and load distribution
- Compare PV sources by yearly energy, specific yield, and optional generation cost
- Track green share, autarky, and self-consumption as separate KPIs
- Audit optional grid-control/14a events when EVCC and the collector provide the required data
- Migrate historic EVCC data from InfluxDB to VictoriaMetrics and continue operating there
- Optionally fill historic years without EVCC data from compatible external daily imports

## Getting started

For installation, migration, live ingest, and dashboard deployment, continue here:

- [docs/en/README.md](./docs/README_EN.md)
- [Release notes](./docs/en/release-notes.md)
