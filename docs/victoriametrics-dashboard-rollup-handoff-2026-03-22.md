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

Known remaining review items:

- `Monthly energy totals` is still a `bar gauge`; it is acceptable for now, but a true legend row is not available in that panel type
- vehicle distance rollups remain the most sensitive family and should stay under observation when more dashboard panels start depending on them
- pricing and tariff rollups remain intentionally deferred; month dashboard still uses raw fallback there

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
3. Keep finance and tariff rollups in a later phase.
4. Revisit monthly rollups only after a measured dashboard bottleneck.

## Reading order for the dashboard thread

1. [victoriametrics-dashboard-rollup-handoff-2026-03-22.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md)
2. [victoriametrics-rollup-design.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-rollup-design.md)
3. [victoriametrics-handoff-2026-03-21.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-handoff-2026-03-21.md)
4. [vm-thread-restart-handoff-2026-03-21.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/vm-thread-restart-handoff-2026-03-21.md)
