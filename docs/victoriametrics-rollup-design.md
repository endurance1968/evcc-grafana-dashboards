# VictoriaMetrics Rollup Design

This document captures the accepted VictoriaMetrics rollup design for EVCC long-range dashboards.

## Goals

- Keep raw EVCC data in VictoriaMetrics untouched.
- Keep month, year and all-time dashboards fast on a single-node setup.
- Keep the 50-year storage target far below `1 TB`.
- Keep the operational model simple enough for end users.

## Current platform state

Validated on `192.168.1.160:8428` on `2026-03-22`:

- `retentionPeriod=50y`
- EVCC raw history reimported from Influx for `2025-01-01` until `2026-03-21T08:00:00Z`
- current TSDB status:
  - `totalSeries=184`
  - `totalLabelValuePairs=659`
- storage counters:
  - `vm_rows{type="storage/small"}=243359305`
  - `vm_data_size_bytes{type="storage/small"}=160087571`
  - `vm_data_size_bytes{type="indexdb/file"}=1332294`

Important historical detail:

- imported Influx history is available in VictoriaMetrics without a stable `host` label
- live Telegraf writes may include `host`
- therefore VM history queries and dashboards must prefer `db="evcc"` and must not rely on `host`

## Accepted decision

Use one VictoriaMetrics server for both raw data and rollups.

Do not create a separate VM instance for rollups.

Do not create a separate Grafana datasource for rollups by default.

Do not overwrite raw metrics.

Write rollups as new metrics in a separate namespace:

- test namespace first: `test_evcc_*`
- production namespace later: `evcc_*`

## Why not duplicate the Influx setup 1:1

The legacy Influx path materializes both daily and monthly measurements because raw dashboard queries became too expensive on InfluxDB and the deployment hardware was constrained. See:

- [README.md](/D:/AI-Workspaces/evcc-grafana-dashboards/scripts/influx-legacy/README.md)
- [evcc-influx-aggregate.sh](/D:/AI-Workspaces/evcc-grafana-dashboards/scripts/influx-legacy/evcc-influx-aggregate.sh)

VictoriaMetrics changes the tradeoff:

- raw-data queries are already reasonably fast
- daily rollups are dramatically faster than raw recomputation
- daily rollups keep the data volume tiny even over 50 years

Because of this, the accepted default design is:

- raw metrics for `Today*`
- daily rollups for `Monat`, `Jahr`, `All-time`
- monthly rollups optional later, not required up front

## Benchmark summary

Measured over the real EVCC history window `2025-01-01` to `2026-03-21T08:00:00Z`:

| Query family | Raw query | Time | Daily rollup query | Time |
| --- | --- | ---: | --- | ---: |
| PV daily | recomputed from `pvPower_value` | `168 ms` | `test_evcc_pv_energy_daily_wh` | `4 ms` |
| Home daily | recomputed from `homePower_value` | `171 ms` | `test_evcc_home_energy_daily_wh` | `2 ms` |
| Loadpoints daily | recomputed from `chargePower_value` | `137 ms` | `test_evcc_loadpoint_energy_daily_wh` | `1 ms` |
| Vehicles daily | recomputed from `chargePower_value` | `187 ms` | `test_evcc_vehicle_energy_daily_wh` | `0 ms` |
| Ext daily | recomputed from `extPower_value` | `167 ms` | `test_evcc_ext_energy_daily_wh` | `1 ms` |
| Battery min SOC | recomputed from `batterySoc_value` | `132 ms` | `test_evcc_battery_soc_daily_min_pct` | `1 ms` |
| Battery max SOC | recomputed from `batterySoc_value` | `34 ms` | `test_evcc_battery_soc_daily_max_pct` | `1 ms` |

Interpretation:

- raw long-range queries are not catastrophic on current data
- daily rollups are consistently one to two orders of magnitude faster
- daily rollups are already strong enough for the default implementation

## Storage estimate

Linear projection based on the current EVCC VM storage footprint:

- current raw footprint over about `445` days:
  - about `160.1 MB` data blocks
  - about `1.3 MB` index blocks
- projected raw footprint for `50` years:
  - about `6.62 GB`
- projected additional daily-rollup footprint for `50` years with the currently tested rollup families:
  - about `0.011 GB`
- projected total:
  - about `6.64 GB`

This is only a linear EVCC projection. It does not include future non-EVCC imports such as SMA history. Still, it shows that EVCC raw data plus daily rollups is nowhere near the `1 TB` target.

## Recommended architecture

### Layer 1: raw metrics

Keep all incoming EVCC metrics as-is.

These remain the source of truth for:

- `Today`
- `Today - Details`
- `Today - Mobile`
- debugging
- future recomputation of rollups

Examples:

- `pvPower_value`
- `homePower_value`
- `chargePower_value`
- `batterySoc_value`

### Layer 2: daily rollups

Create daily rollup metrics for long-range dashboards.

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

### Layer 3: optional monthly rollups

Only add monthly rollups if one of these becomes true:

- an all-time dashboard on daily rollups is measurably too slow
- monthly visualizations become too complex to implement from daily series
- finance panels need simpler low-cardinality source series

Monthly rollups are currently not part of the required baseline.

## Naming and labeling rules

- Use Prometheus-style metric names.
- Prefer filtering on `db="evcc"` only for VM history queries.
- Do not rely on a `host` label for EVCC history.
- Encode units in metric names.
- Keep only real dimensions as labels.
- Use `local_year` and `local_month` on daily rollups when local calendar filtering materially simplifies Grafana queries.
- Do not add `local_day` or `local_date`; those labels would explode each daily family into one series per day.

Good examples:

- `evcc_pv_energy_daily_wh`
- `evcc_vehicle_energy_daily_wh{vehicle="BMW i3",local_year="2026",local_month="03"}`

Bad examples:

- `pvDailyEnergy,year=2026,month=03,day=22`
- `evcc_daily_energy{day="22"}`
- `evcc_pv_energy_daily_wh{local_date="2026-03-22"}`

## Grafana model

Use one VM datasource in Grafana by default.

Do not split raw and rollups into separate datasources unless dashboard authors later prove this improves maintenance.

The intended separation is purely logical:

- raw data via raw metric names
- rollups via the `evcc_*` namespace

Dashboard usage:

- `Today*` dashboards query raw metrics
- `Monat`, `Jahr`, `All-time` dashboards query daily rollups

## Tooling choice

### Default path for end users

Provide a small Python CLI directly in `scripts/`.

Why:

- simple to install on any Linux host with Python
- easier to reason about than a permanent `vmalert` service
- easier to document
- easier to run remotely if VictoriaMetrics is not on the same host
- easier to backfill in visible monthly chunks with shell progress for long one-shot runs

Container note:

- this Python tool does not need to run inside the same runtime as VictoriaMetrics
- it only needs HTTP access to the VictoriaMetrics API
- therefore it works equally well when VictoriaMetrics runs directly on the host or inside Docker
- the recommended default is to run the Python rollup tool outside the VM container, for example on the Docker host or on another Linux machine with network access to VM

### Advanced path for power users

Support generated `vmalert` rules for users who want native VM recording rules and replay-based backfill.

Why it is not the default:

- another service to run
- more moving parts
- harder to debug for casual users

## Safety rules

The first implementation phase must follow these rules:

1. Never delete or modify raw EVCC metrics.
2. Never write rollups into existing raw metric names.
3. Start in the `test_evcc_*` namespace.
4. Keep all tests read-only unless the user explicitly approves writing test metrics.
5. Benchmark candidate queries before productizing rollups.

## Implementation guidance for the dashboard project

### Required baseline

The dashboard project should assume this baseline:

- production VM dashboards target one datasource: `VM-EVCC`
- history queries filter on `db="evcc"`
- no production dashboard should depend on `host`
- long-range dashboards should be implemented against daily rollups

### Migration strategy for dashboards

1. Keep `Today*` dashboards on raw metrics.
2. Build VM versions of `Monat`, `Jahr` and `All-time` against daily rollups.
3. Only introduce monthly rollups after a measured dashboard regression, not preemptively.

### Legacy compatibility note

The Influx legacy `All-time` dashboard uses both daily and monthly measurements. VM dashboards should not copy this structure blindly. Instead, they should be redesigned around daily rollups unless a measured need for monthly rollups appears later.

## Rollout plan

### Phase 1

- detect dimensions from the current VM data
- build a rollup catalog
- generate test metric names
- benchmark representative raw-data queries

### Phase 2

- write test rollups into `test_evcc_*`
- adapt a test version of the all-time dashboard to those test metrics
- compare load times and dashboard correctness

### Phase 3

- finalize the production metric namespace
- backfill production rollups
- move month, year and all-time dashboards from raw queries to rollups

### Phase 4

- decide whether monthly rollups are still unnecessary
- only then add `evcc_*_monthly_*` if a measured dashboard case requires it

## Known open items

These items are intentionally deferred from the first safe rollout:

- sign-aware energy split for grid import vs. export
- sign-aware energy split for battery charge vs. discharge
- tariff and price rollups
- return-on-investment and finance rollups
- optional monthly rollup layer

These need more careful query design than the first daily energy rollups.
