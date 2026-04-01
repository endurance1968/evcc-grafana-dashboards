# Consumer Energy Attribution Design

This document defines a proposed extension to the EVCC VictoriaMetrics rollup model for attributing consumer energy to supply sources.

The goal is to answer questions such as:

- how much yearly energy did the heat pump consume
- how much yearly energy did the charging stations consume
- how much of that energy came from PV, battery discharge, and grid import

## Goal

Provide a technically consistent basis for dashboard panels like:

- `Heat pump energy mix`
- `Charging energy mix`

Each panel should be able to show:

- total energy in `kWh`
- share from `PV`
- share from `Battery`
- share from `Grid`

The design should be reusable for:

- `Today`
- `Monat`
- `Jahr`
- `All-time`

## Why this needs both a shared model and a new rollup layer

The current rollup model already contains:

- total daily consumer energy per loadpoint
- total daily consumer energy per `EXT` title
- total daily consumer energy per `AUX` title
- total daily PV energy
- total daily grid import/export energy
- total daily battery charge/discharge energy

What it does not contain is a source attribution per consumer.

That means the current schema can already answer:

- `How much did the heat pump consume this year?`
- `How much did charging consume this year?`

But it cannot yet answer in a defensible way:

- `How much of the heat pump energy came from PV?`
- `How much of the charging energy came from battery discharge?`

Without extra rollups, those percentages would only be rough dashboard heuristics for long-range dashboards.

At the same time, the same attribution logic should also be usable for `Today` directly on raw data.

## Accepted modeling approach

Use per-bucket proportional attribution in the Python rollup pipeline.

The attribution should be computed on the same raw time buckets already used for daily energy rollups.

This design therefore defines:

- one shared attribution algorithm
- one raw-data execution path for `Today`
- one daily-rollup execution path for `Monat`, `Jahr`, and `All-time`

Recommended bucket:

- `60s`

For every bucket:

1. determine active tracked consumers
2. determine available supply sources
3. distribute source power proportionally across tracked consumers
4. convert bucket power attribution to energy
5. aggregate by consumer and source for the local day

## Tracked consumer groups

The first implementation should cover:

- `loadpoint`
- `ext title`
- `aux title`

That allows:

- charging stations
- heat pump if it appears as `EXT` or `AUX`
- additional external and auxiliary consumers

## Supply sources

For attribution, the model should use:

- `PV`
- `Battery`
- `Grid`

Derived from raw metrics:

- `pvPower_value`
- `batteryPower_value`
- `gridPower_value`

Operational interpretation:

- `PV` means direct PV-supported consumption
- `Battery` means supplied by battery discharge
- `Grid` means imported from the grid

## Shared execution model by dashboard range

### Today

For `Today`, attribution should be computed directly from raw metrics in Grafana queries or in a dedicated helper panel/library model.

That means:

- no additional daily rollups are required for `Today`
- the source split is computed over the currently selected day range
- the underlying attribution logic stays the same as for the rollup path

### Month, year and all-time

For `Monat`, `Jahr`, and `All-time`, attribution should be based on daily rollups.

That means:

- the source split is computed once in the Python rollup pipeline
- Grafana only sums the already attributed daily metrics
- all long-range dashboards reuse the same stored attribution model

## Proposed daily rollup metrics

### Loadpoints

- `evcc_loadpoint_energy_from_pv_daily_wh{db="evcc",local_year="...",local_month="...",loadpoint="..."}`
- `evcc_loadpoint_energy_from_battery_daily_wh{db="evcc",local_year="...",local_month="...",loadpoint="..."}`
- `evcc_loadpoint_energy_from_grid_daily_wh{db="evcc",local_year="...",local_month="...",loadpoint="..."}`

### External meters

- `evcc_ext_energy_from_pv_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`
- `evcc_ext_energy_from_battery_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`
- `evcc_ext_energy_from_grid_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`

### Auxiliary meters

- `evcc_aux_energy_from_pv_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`
- `evcc_aux_energy_from_battery_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`
- `evcc_aux_energy_from_grid_daily_wh{db="evcc",local_year="...",local_month="...",title="..."}`

## Optional aggregate helper metrics

These are not required for the first implementation, but they can simplify dashboards later:

- `evcc_tracked_consumer_energy_daily_wh`
- `evcc_other_energy_daily_wh`

They are useful if a later panel should explain how much of the full house load is not part of the tracked consumer set.

## Attribution logic

### 1. Build tracked consumer demand per bucket

For each bucket, use positive demand only:

- `chargePower_value` per `loadpoint`
- `extPower_value` per `title`
- `auxPower_value` per `title`

Negative values should not create attributed supply.

Tracked consumer demand:

- `tracked_total_w = sum(all positive tracked consumer powers)`

### 2. Build source availability per bucket

Use:

- `pv_supply_w = max(pvPower_value, 0)`
- `battery_supply_w = max(batteryPower_value, 0)` interpreted as discharge

Grid import should be the residual source needed to satisfy tracked consumption:

- `grid_supply_w = max(tracked_total_w - pv_allocatable_w - battery_allocatable_w, 0)`

The attribution model should never create negative source allocations.

### 3. Source allocation order

Recommended order:

1. allocate `PV`
2. allocate `Battery`
3. allocate remaining demand to `Grid`

Reason:

- direct PV should be consumed before imported energy
- battery discharge is an explicit second supply source
- grid import is the residual fallback

### 4. Per-consumer proportional split

For each tracked consumer:

- `consumer_share = consumer_power_w / tracked_total_w`

Then:

- `consumer_pv_w = pv_allocatable_w * consumer_share`
- `consumer_battery_w = battery_allocatable_w * consumer_share`
- `consumer_grid_w = residual_w * consumer_share`

Where:

- `pv_allocatable_w = min(pv_supply_w, tracked_total_w)`
- `remaining_after_pv_w = tracked_total_w - pv_allocatable_w`
- `battery_allocatable_w = min(battery_supply_w, remaining_after_pv_w)`
- `residual_w = max(tracked_total_w - pv_allocatable_w - battery_allocatable_w, 0)`

### 5. Convert to energy

Per bucket:

- `energy_wh = power_w * bucket_seconds / 3600`

Then sum by:

- local day
- business dimension
- source

## Important limits of the model

This attribution is a model, not a directly measured truth.

### Why

The raw data set does not contain explicit source markers per consumer.

It contains:

- consumer powers
- global source powers

So the source split per consumer must be reconstructed.

### Consequences

The resulting percentages should be treated as:

- operationally useful
- internally consistent
- but still modeled

They should not be described as meter-certified values.

## Recommended handling of untracked load

A key decision is whether the attribution should ignore untracked load or explicitly model it.

### Recommended default

Compute attribution only across the tracked consumer set for the first version.

That means:

- the percentages answer: `Within this tracked consumer group, how was the energy supplied?`

This is the simplest and most stable first implementation.

### Optional later refinement

Add an internal residual group:

- `other/home`

That would support a fuller energy-flow picture, but it is not necessary for the first dashboard feature.

## Dashboard design recommendation

The dashboards should not copy the exact visual style of the attached appliance list.

Recommended panel design:

### One row per consumer group

- `Heat pump`
- `Charging stations`

### Each row shows

- total yearly energy in `kWh`
- `PV %`
- `Battery %`
- `Grid %`

Optional:

- a thin stacked source bar in the existing semantic colors

### Reuse by dashboard range

#### Today

Use the same row concept, but source the values from raw-day attribution.

Recommended first scope:

- one compact panel for `Heat pump`
- one compact panel for `Charging stations`

#### Monat

Use monthly sums of the daily attribution rollups.

The visual structure can stay the same as in `Jahr`.

#### Jahr

Use yearly sums of the daily attribution rollups.

This is the first recommended implementation target.

#### All-time

Use all-time sums of the daily attribution rollups.

For `All-time`, the panel should likely stay compact and focus on:

- total `kWh`
- source percentages

without overloading the dashboard with too many per-consumer rows.

### Group definitions

#### Charging stations

Use:

- all visible loadpoints after dashboard blocklists

#### Heat pump

Use one selected `EXT` or `AUX` title depending on the installation.

This likely needs either:

- a naming convention
- or a small dashboard variable such as `heatPumpTitle`

## Suggested implementation phases

### Phase 1

Add new attribution daily rollups to the Python pipeline.

### Phase 2

Run a short backfill over a known date range and validate:

- totals match consumer daily energy
- source shares sum to `100%`
- no negative attributed energy

### Phase 3

Add the first `Jahr` dashboard panel pair:

- `Heat pump energy mix`
- `Charging energy mix`

### Phase 4

Reuse the same attributed daily rollups in:

- `Monat`
- `All-time`

### Phase 5

Add a raw-data version of the same concept to:

- `Today`

## Validation rules

Every local day and dimension should satisfy:

- `from_pv + from_battery + from_grid ~= total_energy`
- no source component below zero
- no source percentage above `100%`
- percentages sum to `100%` within rounding tolerance

## Open design choices

These still need an explicit implementation decision:

- whether heat pump should be sourced from `EXT`, `AUX`, or a configurable combined selector
- whether untracked home load should remain outside the attribution model
- whether the first dashboard should show absolute source `kWh` in addition to percentages

## Recommendation

Proceed with a first implementation based on:

- daily attribution rollups
- proportional 60-second source allocation
- `Jahr` dashboard panels for heat pump and charging stations

Then reuse the same attribution model for:

- `Monat`
- `All-time`
- optionally `Today` on raw data

That gives a stable and reusable base without hard-coding separate heuristics per dashboard range.
