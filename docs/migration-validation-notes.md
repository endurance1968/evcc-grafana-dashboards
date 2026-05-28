# Migration Validation Notes

This document keeps release and calibration background out of the main migration runbook.

## Why These Notes Exist

The main migration guide should stay short enough for first-time users. The details here are useful when validating rollup quality, investigating energy drift, or preparing a release.

## 2026-04-06 Baseline Before PV/Home Mean Switch

Before switching the Python rollup path from `max` to `mean` for PV and home daily energy, the observed baseline was:

- `evcc_pv_energy_daily_wh`: the VM rollup matched a raw `max` bucket path, while Influx and usable VRM comparison months tracked the raw `mean` path more closely.
- `evcc_home_energy_daily_wh`: the VM rollup matched a raw `max` bucket path, while Influx tracked the raw `mean` path more closely.
- `evcc_grid_import_daily_wh`: the VM rollup matched the `gridEnergy` counter-spread path and was usually closer to VRM than the legacy Influx aggregate, so it was intentionally left unchanged.

Use this as the before-state when validating full backfills around the PV/home reducer change.

## 2026-04-06 Verified Comparison After PV/Home Mean Switch

The monthly comparison was validated against:

- Influx raw monthly semantics for `PV`, `Home`, and `Grid import`
- the Influx `EVCC_AGGREGATIONS` datasource (`evcc_agg`) for dashboard-level `Home`, `Loadpoints`, and `Battery netto`
- VictoriaMetrics rollups in the `evcc_*` namespace
- locally cached Victron VRM day totals for `PV` and `Grid import`

Influx month dashboard semantics for `Gesamt: Energieverteilung`:

- `Home` comes from `homeDailyEnergy`
- `Loadpoints` come from `loadpointDailyEnergy`
- `Battery netto` is `chargeDailyEnergy - dischargeDailyEnergy`

Comparison months with complete VRM coverage:

- `2025-08`
- `2025-09`
- `2026-02`
- `2026-03`

| Month | Metric | Influx | VM rollup | VM aggregation | VRM |
| --- | --- | ---: | ---: | ---: | ---: |
| 2025-08 | PV | 1825.700 | 1826.580 | 1793.831 | 1829.700 |
| 2025-08 | Home | 1990.773 | 1994.219 | 1986.997 | - |
| 2025-08 | Grid import | 655.300 | 633.260 | 657.920 | 634.000 |
| 2025-08 | Loadpoints | 366.213 | 366.768 | 715.256 | - |
| 2025-08 | Battery netto | 57.051 | 55.911 | 125.630 | - |
| 2025-09 | PV | 996.500 | 997.219 | 1021.473 | 996.200 |
| 2025-09 | Home | 1244.685 | 1245.235 | 1239.921 | - |
| 2025-09 | Grid import | 624.000 | 612.290 | 591.455 | 611.900 |
| 2025-09 | Loadpoints | 367.166 | 367.416 | 750.311 | - |
| 2025-09 | Battery netto | -21.578 | -19.482 | -41.672 | - |
| 2026-02 | PV | 511.800 | 511.763 | 540.248 | 512.200 |
| 2026-02 | Home | 1128.338 | 1129.096 | 1138.051 | - |
| 2026-02 | Grid import | 1176.500 | 1168.690 | 1149.994 | 1165.600 |
| 2026-02 | Loadpoints | 515.632 | 516.647 | 934.805 | - |
| 2026-02 | Battery netto | 28.346 | 29.868 | 157.272 | - |
| 2026-03 | PV | 1252.900 | 1252.948 | 1185.964 | 1249.900 |
| 2026-03 | Home | 1262.666 | 1265.252 | 1218.546 | - |
| 2026-03 | Grid import | 531.500 | 512.810 | 469.013 | 510.800 |
| 2026-03 | Loadpoints | 405.301 | 406.338 | 796.323 | - |
| 2026-03 | Battery netto | 63.557 | 60.979 | 59.970 | - |

Summary:

- `VM rollup` is on Influx/VRM level for `PV`.
- `VM rollup` is on Influx dashboard level for `Home`, `Loadpoints`, and `Battery netto`.
- `VM rollup` is closer to VRM than Influx for `Grid import` in the checked months.
- `VM aggregation` remains visibly less reliable, especially for `PV`, `Loadpoints`, and several `Grid import` months.

## Private Validation Command

On private runners with refreshed Tibber/Influx/VRM caches and optional live VM access:

```bash
npm run test:rollup-path -- --strict-energy --vm-base-url http://127.0.0.1:8428
```

Without private caches, public/default validation intentionally treats missing external comparison files as non-blocking skips.