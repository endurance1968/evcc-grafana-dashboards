# VM Rollup Test Dashboards

This dashboard family is intentionally diagnostic.

It is not a polished end-user replacement for the full legacy all-time dashboard. Instead, it acts as a validation and benchmark suite for the VictoriaMetrics rollup migration.

## Purpose

Use the dashboard to compare:

- raw-data queries
- test rollup metrics under `test_evcc_*`

The dashboard is useful for checking:

- correctness of daily rollups
- missing labels or dimensions
- all-time query performance
- whether monthly rollups are still necessary

## Current dashboard

- `original/en/VM_ EVCC_ All-time - Rollup Test.json`

## Expected metric names

The first test version expects these metrics once test rollups are written:

- `test_evcc_pv_energy_daily_wh`
- `test_evcc_home_energy_daily_wh`
- `test_evcc_loadpoint_energy_daily_wh`
- `test_evcc_vehicle_energy_daily_wh`
- `test_evcc_battery_soc_daily_min_pct`
- `test_evcc_battery_soc_daily_max_pct`

## Current test data window

The dashboard only reflects the raw EVCC history that already exists in VictoriaMetrics.

If VictoriaMetrics currently contains just a small imported history window, then the `test_evcc_*` rollups will cover only that same window. After a wider Influx-to-VM history import, rerun the rollup backfill and the dashboard becomes a more realistic all-time benchmark.

## Safety model

The dashboard reads only.

It does not require productivized rollup names. It is designed to work with the temporary `test_evcc_*` namespace first.
