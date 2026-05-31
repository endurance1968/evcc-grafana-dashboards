# Screenshots

German version: [German README](./README.md).

This directory contains the curated screenshot set for the current EVCC/VictoriaMetrics dashboard release. PNG files live directly in this directory; the former `tabs/` subdirectory is no longer used.

Test runs, render-smoke screenshots, temporary dashboard imports, performance traces, and debugging captures belong under `tests/artifacts/` and are intentionally ignored by Git.

## Rules

- Delete old screenshot files before regenerating a set.
- Do not silently replace screenshots in place.
- Screenshots should show the relevant navigation, especially the active tabs for dashboards that use tabs.
- Prefer the Grafana 13 TAB dashboards for release documentation.
- Keep filenames stable, lowercase, and descriptive.

## Today

| Screenshot | Description |
| --- | --- |
| <img src="./today.png" alt="Today Dashboard" width="420"> | `VM: EVCC: Today` overview for the current day. |
| <img src="./today-mobile.png" alt="Today Mobile Dashboard" width="420"> | Compact mobile Today view. |

## Today - Details Tabs

| Screenshot | Description |
| --- | --- |
| <img src="./today-pv.png" alt="Today Details PV Tab" width="420"> | PV tab with PV energy, PV power, battery, and forecast. |
| <img src="./today-grid.png" alt="Today Details Grid Tab" width="420"> | Grid tab with import/feed-in visibility and grid history. |
| <img src="./today-consumption.png" alt="Today Details Consumption Tab" width="420"> | Consumption tab with home consumption and relevant consumers. |
| <img src="./today-tariffs.png" alt="Today Details Tariffs Tab" width="420"> | Tariffs tab with price and cost views. |
| <img src="./today-loadpoints.png" alt="Today Details Loadpoints Tab" width="420"> | Loadpoints tab with charging point and vehicle data. |

## Month Tabs

| Screenshot | Description |
| --- | --- |
| <img src="./month-pv.png" alt="Month PV Tab" width="420"> | Monthly PV generation and PV analysis. |
| <img src="./month-home.png" alt="Month Home Tab" width="420"> | Monthly home, grid import, and self-consumption view. |
| <img src="./month-battery.png" alt="Month Battery Tab" width="420"> | Monthly battery, SOC, and storage flow view. |
| <img src="./month-consumers.png" alt="Month Consumers Tab" width="420"> | Monthly consumers and load distribution. |

## Year Tabs

| Screenshot | Description |
| --- | --- |
| <img src="./year-pv.png" alt="Year PV Tab" width="420"> | Yearly PV generation and PV comparison. |
| <img src="./year-home.png" alt="Year Home Tab" width="420"> | Yearly home, grid, and autarky view. |
| <img src="./year-battery.png" alt="Year Battery Tab" width="420"> | Yearly battery and storage metrics. |
| <img src="./year-consumers.png" alt="Year Consumers Tab" width="420"> | Yearly consumer view. |
| <img src="./year-vehicles.png" alt="Year Vehicles Tab" width="420"> | Yearly vehicle and charging energy view. |

## All-Time Tabs

| Screenshot | Description |
| --- | --- |
| <img src="./alltime-energy.png" alt="All-Time Energy Tab" width="420"> | All-time energy overview across the full history. |
| <img src="./alltime-finances.png" alt="All-Time Finances Tab" width="420"> | All-time finance view with cost and savings metrics. |
| <img src="./alltime-planthealth.png" alt="All-Time Plant Health Tab" width="420"> | All-time plant-health view with long-range indicators. |
