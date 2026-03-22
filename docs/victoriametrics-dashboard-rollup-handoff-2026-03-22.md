# VictoriaMetrics Dashboard Rollup Handoff

Stand: 2026-03-22

This note is the handoff for the parallel dashboard project that will build the VictoriaMetrics month, year and all-time dashboards together with the first VM rollup layer.

## Accepted architecture

The following decisions are accepted and should be treated as project baseline:

- use one VictoriaMetrics server for both raw data and rollups
- use one Grafana datasource by default
- do not create a separate datasource for rollups unless later maintenance proves it is helpful
- keep raw EVCC metrics untouched
- write rollups as separate metrics in a dedicated namespace
- use `test_evcc_*` for test rollups
- use `evcc_*` for production rollups later

## Querying rules

- use `db="evcc"` as the stable history matcher
- do not rely on `host`
- do not assume imported EVCC history contains the same label set as current live writes

Reason:

- historical Influx import into VM is available without a stable `host` label
- live data may contain extra infrastructure labels such as `host`
- dashboards must therefore not depend on `host` for historical correctness

## Raw vs rollup responsibility

Raw metrics remain the source of truth for:

- `Today`
- `Today - Details`
- `Today - Mobile`
- debugging
- future recomputation

Daily rollups are the default source for:

- `Monat`
- `Jahr`
- `All-time`

Monthly rollups are explicitly not required for the first VM implementation.

## Current VM data state

Current VictoriaMetrics state for `db="evcc"`:

- raw EVCC metrics are present
- test rollups in the `test_evcc_*` namespace are present
- production rollups in the `evcc_*` namespace do not exist yet

This means:

- review dashboards may currently depend on `test_evcc_*`
- production dashboards must not yet assume productivized rollup names

Current test rollup families include:

- `test_evcc_pv_energy_daily_wh`
- `test_evcc_home_energy_daily_wh`
- `test_evcc_loadpoint_energy_daily_wh`
- `test_evcc_vehicle_energy_daily_wh`
- `test_evcc_vehicle_distance_daily_km`
- `test_evcc_ext_energy_daily_wh`
- `test_evcc_aux_energy_daily_wh`
- `test_evcc_battery_soc_daily_min_pct`
- `test_evcc_battery_soc_daily_max_pct`
- `test_evcc_grid_import_cost_daily_eur`
- `test_evcc_grid_import_price_avg_daily_ct_per_kwh`
- `test_evcc_grid_import_price_effective_daily_ct_per_kwh`
- `test_evcc_grid_import_price_min_daily_ct_per_kwh`
- `test_evcc_grid_import_price_max_daily_ct_per_kwh`

## Why daily rollups are enough for the first implementation

Measured on the real EVCC history window `2025-01-01` to `2026-03-21T08:00:00Z`:

| Query family | Raw query time | Daily rollup time |
| --- | ---: | ---: |
| PV daily | `168 ms` | `4 ms` |
| Home daily | `171 ms` | `2 ms` |
| Loadpoints daily | `137 ms` | `1 ms` |
| Vehicles daily | `187 ms` | `0 ms` |
| Ext daily | `167 ms` | `1 ms` |
| Battery min SOC | `132 ms` | `1 ms` |
| Battery max SOC | `34 ms` | `1 ms` |

Interpretation:

- raw queries are already acceptable
- daily rollups are much faster
- daily rollups are sufficient baseline input for long-range dashboards

## Storage expectation

Linear projection from the current EVCC VM footprint:

- raw EVCC data for `50` years: about `6.62 GB`
- additional tested daily rollups for `50` years: about `0.011 GB`
- combined EVCC total: about `6.64 GB`

This projection does not include future non-EVCC imports such as SMA history. It is still enough to show that EVCC raw plus daily rollups is far below the `1 TB` target.

## Naming rules for production rollups

Use Prometheus-style metric names with explicit units.

Examples:

- `evcc_pv_energy_daily_wh`
- `evcc_home_energy_daily_wh`
- `evcc_grid_import_daily_wh`
- `evcc_grid_export_daily_wh`
- `evcc_loadpoint_energy_daily_wh{loadpoint="..."}`
- `evcc_vehicle_energy_daily_wh{vehicle="..."}`
- `evcc_vehicle_distance_daily_km{vehicle="..."}`
- `evcc_ext_energy_daily_wh{title="..."}`
- `evcc_aux_energy_daily_wh{title="..."}`
- `evcc_battery_soc_daily_min_pct`
- `evcc_battery_soc_daily_max_pct`

Rules:

- keep only real business dimensions as labels
- do not add `year`, `month`, or `day` labels
- do not encode infrastructure labels such as `host` into the rollup design

## Dashboard implementation guidance

### For VM month, year and all-time dashboards

- do not copy the Influx legacy structure blindly
- redesign those dashboards around daily rollups
- only add monthly rollups if a measured dashboard performance problem appears later

### For Grafana datasource usage

- keep using `VM-EVCC`
- keep using the native VictoriaMetrics plugin datasource type

### For migration from the Influx legacy dashboards

The old Influx `All-time` dashboard uses both daily and monthly measurements. This was a performance workaround for Influx and constrained hardware. The VM design should not inherit this complexity unless real VM measurements later require it.

## Maintainer compatibility status

### Raw-data migration

The raw-data migration path is close to the current maintainer expectations:

- VictoriaMetrics datasource uses the native VM plugin type
- Influx history was imported via `vmctl`
- the problematic `batteryControllable` measurement was removed before import
- imported raw metrics follow the expected VM naming style such as:
  - `pvPower_value`
  - `homePower_value`
  - `gridPower_value`
  - `chargePower_value`
  - `batterySoc_value`

This means the existing upstream-style VM `Today*` dashboards should remain compatible with the current raw VM data shape.

### Rollup layer

The rollup layer is currently our local design, not a confirmed upstream standard.

This means:

- the raw-data side is the compatible part
- the long-range rollup side should still be treated as a local beta track until upstream settles on a VM-native aggregation model

## Current test assets

Relevant existing assets in the repo:

- rollup design: [victoriametrics-rollup-design.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-rollup-design.md)
- rollup CLI: [evcc-vm-rollup.py](/D:/AI-Workspaces/evcc-grafana-dashboards/scripts/evcc-vm-rollup.py)
- rollup CLI docs: [README.md](/D:/AI-Workspaces/evcc-grafana-dashboards/scripts/README.md)
- user guide: [victoriametrics-aggregation-guide.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-aggregation-guide.md)
- all-time VM rollup test dashboard:
  [VM_ EVCC_ All-time - Rollup Test.json](/D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/vm-rollup-test/original/en/VM_%20EVCC_%20All-time%20-%20Rollup%20Test.json)

Current test dashboard URL:

- [VM: EVCC: All-time - Rollup Test](http://192.168.1.189:3000/d/vm-rollup-test-en-orig-vm-rollup-alltime/5aef2cd)

## Current month dashboard status

Current VM month review dashboard:

- source: [VM_ EVCC_ Monat - Rollup Test.json](/D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/vm-month-test/original/en/VM_%20EVCC_%20Monat%20-%20Rollup%20Test.json)
- live URL: [VM: EVCC: Monat - Rollup Test](http://192.168.1.189:3000/d/vm-month-test-en-orig-vm-rollup-month-te/21f8417)

Current status after interactive review:

- month dashboard is now close to the Influx legacy layout for the most important panels
- `Monthly energy totals`, `Energy`, `Metrics`, `Home: Energy consumption`, `Total: Energy distribution`, `Battery summary`, `Home battery levels`, and `Metric gauges` are implemented and rendering in Grafana
- `Metric gauges` now uses stable monthly inputs via hidden daily series plus `reduce(sum)` rather than long-range direct integrate queries
- `Battery summary` now uses average daily max/min SOC values and corrected battery discharge math
- `battery_soc_daily_min_pct` and `battery_soc_daily_max_pct` were rebuilt after a detected start-of-day rollup bug; March values now match raw data except for the still-open current day
- the month dashboard currently works on test rollups, not on production `evcc_*` rollups

Known remaining review items:

- `Monthly energy totals` is still a `bar gauge`; it is acceptable for now, but a true legend row is not available in that panel type
- vehicle distance rollups remain the most sensitive family and should stay under observation when more dashboard panels start depending on them
- import-side pricing and tariff rollups are now implemented in `test_evcc_*` and partially wired into the month dashboard
- the remaining validation gap is a small but consistent undercount in VM import energy compared with Influx legacy, which makes VM daily costs slightly lower on many days
- export-side credit rollups are still deferred

## Next session focus: price and cost tuning

The next major work item after the current month review is not first implementation anymore, but validation and tuning of the new tariff and cost rollups.

Planning note:

- [victoriametrics-price-rollup-plan.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-price-rollup-plan.md)

Current direction:

- keep the implemented import-side daily test rollups in `test_evcc_*` as the working baseline
- compare them against Influx legacy and Tibber billing reality
- focus on the remaining import-energy drift before promoting anything to `evcc_*`
- add export-side credit rollups only after the import path is accepted

## Current host-label state

Current VM state after the latest cleanup:

- EVCC series with `host` were removed from VictoriaMetrics
- current EVCC queries should now resolve without `host`
- `label/host/values` for `db="evcc"` is empty at the time of writing

Important operational note:

- this cleanup happened only inside VictoriaMetrics
- if the ingest path writes `host` again later, the label can reappear
- this should be treated as an ingest hygiene topic, not as a dashboard-only concern

## Open follow-up items

- confirm whether the ingest path will stay hostless over time
- verify whether any historically relevant host-only samples need a targeted reimport from Influx
- productivize the tested daily rollup families from `test_evcc_*` to `evcc_*`
- complete the still-open tariff and cost rollup phase

## Runtime hint

The intended default runtime for rollups is a Python CLI plus operating-system scheduler.

Important deployment note:

- the Python rollup tool does not need to run inside the VictoriaMetrics runtime
- it only needs HTTP access to VictoriaMetrics
- therefore it remains valid even when VictoriaMetrics runs in Docker
- preferred default: run the Python rollup tool outside the VM container, for example on the Docker host or on another Linux machine with network access

## Recommended next implementation steps

1. Finalize the production rollup metric catalog based on the tested daily families.
2. Build VM `Monat`, `Jahr`, and `All-time` dashboards against daily rollups.
3. Execute the phase-2 tariff and cost plan in `docs/victoriametrics-price-rollup-plan.md`.
4. Revisit monthly rollups only after a measured dashboard bottleneck.

## Reading order for the dashboard thread

1. [victoriametrics-dashboard-rollup-handoff-2026-03-22.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md)
2. [victoriametrics-rollup-design.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-rollup-design.md)
3. [victoriametrics-handoff-2026-03-21.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-handoff-2026-03-21.md)
4. [vm-thread-restart-handoff-2026-03-21.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/vm-thread-restart-handoff-2026-03-21.md)
