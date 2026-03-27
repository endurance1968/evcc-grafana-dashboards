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
- the former clamp-rollup namespace `test_evcc_clamp_*` has been removed after the sampled decision
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
- historically, a parallel clamp namespace mirrored the same metric family under `test_evcc_clamp_*`; this comparison path has since been removed

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

- keep only real business dimensions plus the accepted local-period helpers `local_year` and `local_month` on daily rollups
- do not add `local_day` or `local_date`, because they would fragment each daily series into one series per day
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

Historical note: a dedicated clamp month comparison dashboard existed during evaluation, but it was removed after the sampled path won the month-cost decision.

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
- export-side credit rollups are implemented on the same 15-minute path; in the current history they remain zero because `tariffFeedIn` is historically zero
- the corrected 10s -> 60s positive-energy aggregation path has now also been adopted for `pv`, `home`, `loadpoint`, `vehicle`, `ext`, and `aux`; representative month checks improved drift versus Influx
- the month dashboard now has an explicit `loadpointBlocklist` and separate `extBlocklist` / `auxBlocklist` controls for counters/meters
- local test default for the meter-side blocklist is `.*Car.*|.*Haupt.*`; publicized dashboards should reset those defaults to `^none$`
- sampled vs clamp monthly cost comparisons were extended against Tibber for May 2025 through February 2026
- excluding the incomplete October 2025 data gap month, the original `sampled-old` import-cost path currently has the lowest error and remains the baseline
- the later `sampled-new` experiment that reused the 10s -> 60s energy prebucket path for 15m cost weighting did not win overall and has been discarded
- the comparison set was then extended with the current March 2026 month and a total row; this still favors `sampled` over `clamp` on aggregate deviation to Tibber
- `2026-02-01` was traced to damaged VM raw history for `gridPower_value`; repairing the raw measurement and then fully rebuilding `test_evcc_*` fixed the day
- `2026-01-01` and `2026-01-02` were traced to a missing continuous VM raw block for `gridPower_value` from `2025-12-31T23:59:57Z` to `2026-01-02T01:45:27Z`; a targeted raw reimport plus full `test_evcc_*` rebuild fixed the visible January dashboard issue
- the first imported local day of `2025` showed the same first-hour boundary symptom (`2025-01-01` was short by exactly one local hour); this was also repaired by targeted raw reimport
- confirmed root-cause rule for future history rebuilds: when a full reimport starts at `2025-01-01T00:00:00Z`, the first Europe/Berlin local day loses the UTC hour from `2024-12-31T23:00:00Z` to `2025-01-01T00:00:00Z`
- future full-history reimports should therefore start before the first local midnight in UTC, or explicitly patch the first local day afterward
- the month dashboard now uses `local_year` and `local_month` rollup labels instead of repeated inline timezone/month guards; year and all-time should follow the same pattern

## Next session focus: price and cost tuning

The next major work item after the current month review is not first implementation anymore, but validation and tuning of the new tariff and cost rollups.

Planning note:

- [victoriametrics-price-rollup-plan.md](/D:/AI-Workspaces/evcc-grafana-dashboards/docs/victoriametrics-price-rollup-plan.md)

Current direction:

- keep the implemented import-side daily test rollups in `test_evcc_*` as the working baseline
- compare them against Influx legacy and Tibber billing reality
- focus on the remaining import-energy drift before promoting anything to `evcc_*`
- export-side credit rollups are part of the accepted sampled baseline; with the current historical `tariffFeedIn` data they evaluate to zero
- keep `sampled-old` as the working import-cost baseline until a future comparison clearly beats it
- from this point on, continue tuning only on the sampled path; clamp is no longer the preferred comparison branch for further cost work

Short algorithm distinction behind the comparison:

- `Influx`: legacy `evcc_agg` result built with InfluxQL semantics, especially fixed 60s `mean(value)` buckets and daily integration on local day windows
- `sampled`: VM test rollup baseline in `test_evcc_*`; quarter-hour import costs are built from the sampled raw-data path implemented in the Python rollup CLI
- `clamp`: historical VM comparison path; it shared the corrected daily grid/battery energy baseline, but kept the clamp-based quarter-hour cost path
- practical consequence: current month-panel differences between `sampled` and `clamp` are mainly cost/effective-price differences, not large daily grid-energy differences

Decision table used for this call:

| Month | Influx EUR | Clamp EUR | Sampled EUR | Tibber EUR | Influx delta % | Clamp delta % | Sampled delta % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-05 | 116.15 | 111.60 | 117.75 | 120.38 | -3.5% | -7.3% | -2.2% |
| 2025-06 | 112.51 | 105.31 | 108.50 | 119.49 | -5.8% | -11.9% | -9.2% |
| 2025-07 | 117.23 | 107.39 | 113.77 | 123.51 | -5.1% | -13.1% | -7.9% |
| 2025-08 | 136.04 | 131.04 | 137.91 | 130.35 | +4.4% | +0.5% | +5.8% |
| 2025-09 | 137.52 | 132.28 | 138.55 | 136.57 | +0.7% | -3.1% | +1.5% |
| 2025-11 | 339.71 | 354.14 | 350.40 | 349.43 | -2.8% | +1.3% | +0.3% |
| 2025-12 | 412.34 | 437.81 | 434.15 | 422.03 | -2.3% | +3.7% | +2.9% |
| 2026-01 | 469.70 | 474.63 | 469.88 | 480.35 | -2.2% | -1.2% | -2.2% |
| 2026-02 | 315.47 | 305.33 | 309.13 | 317.82 | -0.7% | -3.9% | -2.7% |
| 2026-03 | 76.62 | 75.09 | 72.00 | 74.86 | +2.3% | +0.3% | -3.8% |
| **Total** | **2233.29** | **2234.62** | **2252.04** | **2274.79** | **-1.8%** | **-1.8%** | **-1.0%** |

Cleanup note:

- the clamp experiment has already been rejected and removed
- sampled remains the only active VM price/cost rollup path

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

