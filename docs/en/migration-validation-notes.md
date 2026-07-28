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

## 2026-07-26 Read-Only Live-Source Validation For Consumers

The Consumer release candidate was validated against the production VictoriaMetrics source in strict read-only mode in addition to deterministic fixtures. Grafana ran only as a disposable test instance.

Results:

- `check_data.py --phase full` reported overall `OK`, no `host` or `db` labels, and available core raw data and rollups.
- All 385 MetricsQL targets from the six source dashboards executed successfully against the live VM.
- All six dashboards with 58 critical panels rendered against the live VM without panel errors.
- The live source did not yet contain `consumersPower_value` or `evcc_consumer_*` series. The new Consumer feature is therefore not functionally live-validated yet and remains deterministic-fixture-tested only.
- Existing real consumers were still represented by 16 EXT series. The production EXT blocklist removed carport and main distribution meters, but remaining parent/child combinations such as the ground-floor distribution meter, UPS, and downstream meters could temporarily consume or exceed total home consumption. The dashboard correctly clamped `Other` to zero, but the underlying meter topology remains semantically ambiguous without explicit hierarchy.

Release conclusion:

- Fixture E2E remains mandatory for reproducible expected values and failure scenarios.
- A read-only live render with actual deploy overrides is an additional mandatory release gate.
- Consumer must not be called live-validated until EVCC provides real Consumer metrics.
- Before release, the EXT-to-Consumer migration or blocklist must prevent parent and child meters from being summed twice.

## 2026-07-27 Live Copy And Complete Consumer Rollup

The previous day's validation was repeated after real Consumer metrics became available. Production Grafana and production VictoriaMetrics remained strictly read-only; import, cleanup, and rollup ran only in a newly created disposable VM.

Results:

- The live source provided six Consumer titles: `KWL`, `Rack Kühler`, `Rack Lüfter`, `Spüle`, `Waschmaschine`, and `Waschmaschine II`.
- The rollup processed 572 days from 2025-01-01 through 2026-07-26 and wrote 41 metrics, 288 series, and 7,840 samples.
- The 2025 rollups contained 356 PV and home daily values plus 365 daily grid-import and feed-in values. Totals were about 14.42 MWh PV, 22.43 MWh home consumption, 14.06 MWh grid import, and 0.83 MWh feed-in.
- All six titles continued as Consumers were absent from `evcc_ext_energy*_daily_wh` afterward. Ten actual diagnostic or distribution meters remained as EXT.
- Production Grafana settings were copied into the disposable instance. `Today` remained the range for Today dashboards, and the `.*Car.*|.*Haupt.*` blocklist filtered the known sum meters.
- End-user visual checks confirmed separate Consumer and additional-meter views in Today Details, Month, Year, and All-time. Year 2025 showed all twelve months, All-time showed 2025 and 2026, and annual matrices used an actual year axis.
- The Today finance view showed purchase cost as negative, feed-in credit as positive, and balance as the sum of both values.

Safety finding:

- `--replace-range` deletes existing rollups in the target range before rebuilding them. A full-range run is safe only when complete raw history exists for every affected family.
- A full additive backfill over imported rollups is unsafe as well: different daily timestamps produce multiple samples per local day and double monthly totals. The corrected live copy transformed only the six mapped EXT rollup series, preferred Consumer per day during overlap, and imported only those Consumer series.
- `check_data.py --phase full` now checks every `evcc_*_daily_*` series for at most one sample per label set and local day. The corrected copy reported 0 duplicate days; July PV, home, grid-import, and feed-in totals matched the read-only live VM exactly.
