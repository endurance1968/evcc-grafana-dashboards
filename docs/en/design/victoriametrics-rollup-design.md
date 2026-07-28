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
- this repository assumes one VictoriaMetrics instance is dedicated to exactly one EVCC instance
- therefore VM history queries and dashboards must not rely on either `host` or a synthetic shared `db` label

## Accepted decision

Use one VictoriaMetrics server for both raw data and rollups.

The repository assumes that this VictoriaMetrics server is dedicated to exactly one EVCC instance. If you operate multiple EVCC instances, run multiple VictoriaMetrics instances.

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
- `evcc_consumer_energy_daily_wh{title="..."}`
- `evcc_ext_energy_daily_wh{title="..."}`
- `evcc_aux_energy_daily_wh{title="..."}`
- `evcc_battery_soc_daily_min_pct`
- `evcc_battery_soc_daily_max_pct`

### Layer 3: optional monthly rollups

Only add monthly rollups if a measured dashboard bottleneck requires them.

## Naming and labeling rules

- Use Prometheus-style metric names.
- Query VM history directly by metric name and business labels only; no synthetic `db` label is assumed.
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
- easier to document
- easier to run remotely if VictoriaMetrics is not on the same host
- easier to backfill in visible monthly chunks with shell progress for long one-shot runs


## Safety rules

1. Never delete or modify raw EVCC metrics.
2. Never write rollups into existing raw metric names.
3. Keep all tests read-only unless the user explicitly approves writing rollups.
4. Benchmark candidate queries before major dashboard rewiring.

## Implementation guidance for the dashboard project

### Required baseline

- production VM dashboards target one datasource: `VM-EVCC`
- history queries use direct metric selectors and business labels only
- no production dashboard should depend on `host`
- long-range dashboards should be implemented against daily rollups

### Migration strategy for dashboards

1. Keep `Today*` dashboards on raw metrics.
2. Build VM versions of `Monat`, `Jahr` and `All-time` against daily rollups.
3. Only introduce monthly rollups after a measured dashboard regression.

### Legacy compatibility note

The Influx legacy dashboards are kept only as static German reference JSON. VM dashboards should not copy their structure blindly.

## Performance And Scheduler Validation

The release candidate was validated on 2026-07-28 in an isolated VictoriaMetrics copy with complete read-only live raw data from 2025-01-01 through 2026-07-27:

- The full backfill processed 573 days, 36,625 samples, and 1,388 series in 210.606 seconds with 1,264 MB peak Python memory.
- Consumer source attribution was the slowest family at 90.737 seconds or 43.08%; vehicle cost rollups followed at 68.47 seconds.
- A correct Python matrix canonicalization was rejected because it required 258.392 seconds and 1,751 MB. The final query canonicalization saves about 18% runtime and 28% memory compared with that intermediate implementation.
- A 27-day July replacement completed in about 13 seconds. This monthly range is substantially closer to the normal scheduler path than the one-time full backfill.
- Further parallelism or caches are not a release gate: the daily run remains short, while extra concurrency would add unnecessary locking, ordering, and reproducibility risk.

The scheduler remains on `--replace-range --write` and may process completed days only by default. A concurrently started second write run was rejected by the lock file during livecopy testing. The full backfill reported two ignored counter resets, zero power spikes, and 9,910 missing energy buckets. The subsequent data check found no duplicate label/day combinations.

## Known Open Items

- Add an optional monthly rollup layer only after another measured dashboard bottleneck appears.
- Start further performance work only from a reproducible profile that represents the normal scheduler range and target hardware.

## Consumer Source Attribution

Source attribution for Consumers, AUX, EXT, and loadpoints is implemented. It splits modeled daily energy into `PV`, `Battery`, and `Grid` with 60-second buckets. Historical EXT consumers can continue through `consumer_legacy_ext_regex`; `consumer_title_aliases_json` canonicalizes renamed Consumer titles before daily integration.

The domain boundaries and balance rules are documented in:

- [Consumer Energy Attribution Design](./consumer-energy-attribution-design.md)