# VictoriaMetrics Rollup Design

This document captures the accepted VictoriaMetrics rollup design for EVCC long-range dashboards.

## Goals

- Keep raw EVCC data in VictoriaMetrics untouched.
- Keep month, year and all-time dashboards fast on a single-node setup.
- Keep the operational model simple enough for end users.

## Current platform state

Important historical detail:

- imported Influx history is available in VictoriaMetrics without a stable `host` label
- live Telegraf writes may include `host`
- therefore VM history queries and dashboards must prefer `db="evcc"` and must not rely on `host`

## Accepted decision

Use one VictoriaMetrics server for both raw data and rollups.

Do not create a separate VM instance for rollups.

Do not create a separate Grafana datasource for rollups by default.

Do not overwrite raw metrics.

Write rollups as new metrics in the production namespace:

- `evcc_*`

## Why not duplicate the Influx setup 1:1

The legacy Influx path materialized both daily and monthly measurements because raw dashboard queries became too expensive on InfluxDB and the deployment hardware was constrained. The remaining reference is the original German dashboard set under `dashboards/influx-legacy/original/de`.

VictoriaMetrics changes the tradeoff:

- raw-data queries are already reasonably fast
- daily rollups are dramatically faster than raw recomputation
- daily rollups keep the data volume tiny even over long retention periods

Because of this, the accepted default design is:

- raw metrics for `Today*`
- daily rollups for `Monat`, `Jahr`, `All-time`
- monthly rollups optional later, not required up front

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

Only add monthly rollups if a measured dashboard bottleneck requires them.

## Naming and labeling rules

- Use Prometheus-style metric names.
- Prefer filtering on `db="evcc"` only for VM history queries.
- Do not rely on a `host` label for EVCC history.
- Encode units in metric names.
- Keep only real dimensions as labels.
- Use `local_year` and `local_month` on daily rollups when local calendar filtering materially simplifies Grafana queries.
- Do not add `local_day` or `local_date` labels.

## Grafana model

Use one VM datasource in Grafana by default.

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

### Advanced path for power users

Support generated `vmalert` rules for users who want native VM recording rules.

## Safety rules

1. Never delete or modify raw EVCC metrics.
2. Never write rollups into existing raw metric names.
3. Keep all tests read-only unless the user explicitly approves writing rollups.
4. Benchmark candidate queries before major dashboard rewiring.

## Implementation guidance for the dashboard project

### Required baseline

- production VM dashboards target one datasource: `VM-EVCC`
- history queries filter on `db="evcc"`
- no production dashboard should depend on `host`
- long-range dashboards should be implemented against daily rollups

### Migration strategy for dashboards

1. Keep `Today*` dashboards on raw metrics.
2. Build VM versions of `Monat`, `Jahr` and `All-time` against daily rollups.
3. Only introduce monthly rollups after a measured dashboard regression.

### Legacy compatibility note

The Influx legacy dashboards are kept only as static German reference JSON. VM dashboards should not copy their structure blindly.

## Known open items

These items are intentionally deferred from the first safe rollout:

- optional monthly rollup layer
- any further measured performance tuning beyond the current chunked fetch path
