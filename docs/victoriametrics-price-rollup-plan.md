# VictoriaMetrics Price And Cost Rollup Plan

Stand: 2026-03-22

This note defines the intended phase-2 plan for price, tariff, and cost handling on the VictoriaMetrics path.

It is intentionally internal maintainer documentation for the next session.

## Current implementation status

Implemented in the rollup CLI and written to the `test_evcc_*` namespace:

- `test_evcc_grid_import_cost_daily_eur`
- `test_evcc_grid_import_price_avg_daily_ct_per_kwh`
- `test_evcc_grid_import_price_effective_daily_ct_per_kwh`
- `test_evcc_grid_import_price_min_daily_ct_per_kwh`
- `test_evcc_grid_import_price_max_daily_ct_per_kwh`

Current validation result:

- daily price values are already close to Influx legacy and Tibber checks
- daily VM import costs are usually slightly lower than Influx legacy
- the remaining difference is mainly caused by imported grid energy being a bit lower on the VM path, not by obviously wrong tariff values
- this means the next tuning step belongs to the import-energy path, not to the basic tariff formulas

Parallel comparison track now available:

- `test_evcc_*` keeps the current sampled `10s` / `15m` baseline
- `test_evcc_clamp_*` now provides a parallel clamp-based import path for direct comparison
- the separate comparison dashboard lives under `dashboards/vm-month-clamp-test`
- both test namespaces can be deleted independently when one path is rejected

## Why this is phase 2

Energy rollups were safe to implement first because they can be derived directly from power and state metrics with simple daily aggregation.

Price and cost logic is different:

- prices must not be summed like energy
- import and export prices must be treated separately
- average prices must be energy-weighted, not time-weighted
- missing tariff samples can distort the result much more easily than missing power samples

Because of that, the repository currently keeps tariff and cost panels on raw fallback queries where possible and defers production rollups.

## Accepted baseline assumptions

- `tariffGrid_value` is the buy price series
- `tariffFeedIn_value` is the sell price series
- prices are interpreted as dynamic time-based tariffs
- import and export costs must be computed from energy multiplied by the tariff valid in the same interval
- the first production-safe implementation should prefer daily rollups

## What we need to deliver next

The next session should aim for these concrete outputs:

1. Tight validation of the existing import-side test rollups against Influx legacy and Tibber checks.
2. Tuning of the remaining import-energy drift if possible.
3. Completion of export-side credit rollups.
4. Final month dashboard wiring that replaces the remaining raw fallback tariff logic where feasible.

## Required metric families

The first useful phase-2 metric set should be:

- `test_evcc_grid_import_cost_daily_eur`
- `test_evcc_grid_export_credit_daily_eur`
  Current status: not implemented yet.
- `test_evcc_grid_import_price_avg_daily_ct_per_kwh`
- `test_evcc_grid_import_price_effective_daily_ct_per_kwh`
- `test_evcc_grid_import_price_min_daily_ct_per_kwh`
- `test_evcc_grid_import_price_max_daily_ct_per_kwh`
- `test_evcc_grid_export_price_avg_daily_ct_per_kwh`
  Current status: not implemented yet.

Optional later extensions:

- `test_evcc_loadpoint_cost_daily_eur{loadpoint="..."}`
- `test_evcc_vehicle_cost_daily_eur{vehicle="..."}`
- `test_evcc_home_value_daily_eur`

## Correct formulas

## Confirmed import-price requirements

For the grid import price, the next implementation must provide four different daily views:

1. Arithmetic mean import price per day.
2. Minimum import price per day.
3. Maximum import price per day.
4. Effective import price per day.

Meaning:

- arithmetic mean is the plain mean of the tariff samples during the day
- minimum is the lowest tariff sample of the day
- maximum is the highest tariff sample of the day
- effective import price is the energy-weighted mean based on actual grid import during each tariff interval

Important:

- the tariff may change every `15` minutes
- therefore the effective import price must be weighted by import energy in each quarter-hour interval
- this effective price is not the same as the arithmetic daily mean

Suggested metric names:

- `test_evcc_grid_import_price_avg_daily_ct_per_kwh`
- `test_evcc_grid_import_price_min_daily_ct_per_kwh`
- `test_evcc_grid_import_price_max_daily_ct_per_kwh`
- `test_evcc_grid_import_price_effective_daily_ct_per_kwh`

### Daily import cost

Use interval energy multiplied by the matching import tariff.

Conceptually:

`daily import cost = sum(import_energy_interval_kwh * grid_tariff_interval_ct_per_kwh) / 100`

Important:

- integrate only positive `gridPower_value`
- align the tariff sample interval with the energy interval
- do not use a plain arithmetic mean tariff for cost
- for the current EVCC tariff model, the intended baseline interval is `15` minutes
- therefore daily import cost must be computed as the sum of all quarter-hour import energies multiplied by the tariff valid in the same quarter-hour

Operational formulation:

- `grid import in one quarter-hour * grid price in the same quarter-hour`
- summed over the full day

### Daily export credit

Use interval export energy multiplied by the matching feed-in tariff.

Conceptually:

`daily export credit = sum(export_energy_interval_kwh * feed_in_tariff_interval_ct_per_kwh) / 100`

Important:

- integrate only negative `gridPower_value`
- use the export tariff series, not the import tariff

### Daily average import price

Two different daily import-price concepts are needed.

#### Arithmetic daily average import price

Conceptually:

`avg import price arithmetic = mean(grid_tariff_interval_ct_per_kwh)`

This is only the simple daily tariff average.

#### Effective daily average import price

This must be energy-weighted and is the more important operational number.

Conceptually:

`avg import price effective = total_import_cost_daily_eur / total_import_energy_daily_kwh`

and then convert to `ct/kWh` if needed.

#### Daily minimum and maximum import price

Conceptually:

- `min import price = min(grid_tariff_interval_ct_per_kwh)`
- `max import price = max(grid_tariff_interval_ct_per_kwh)`

### Daily average export price

Same rule:

`avg export price = total_export_credit_daily_eur / total_export_energy_daily_kwh`

## Technical implementation plan

### Step 1. Benchmark raw candidate queries

Before adding new rollups:

- benchmark current raw Grafana queries for daily costs and daily average tariffs
- verify the real time window and step that Grafana uses
- verify that the cost baseline really uses a `15` minute tariff grid
- keep screenshots or query notes for comparison

### Step 2. Implement test-only cost builders in the Python CLI

Add a second safe family in `scripts/evcc-vm-rollup.py` for:

- import cost
- export credit
- weighted import price
- weighted export price

Rules:

- write only to `test_evcc_*` first
- keep `db="evcc"` as the stable history matcher
- continue ignoring non-business labels such as `host`

### Step 3. Validate against raw recomputation

For several representative days:

- compare rollup costs against raw interval recomputation
- compare weighted average price against manual raw calculation
- check days with:
  - high PV export
  - little or no export
  - dynamic tariff changes
  - missing or sparse tariff data

### Step 4. Wire the month dashboard

Replace the current raw fallback price panels only after:

- the daily rollups match raw checks
- the month dashboard renders without 422 errors
- the values look plausible against the legacy dashboard

### Step 5. Decide whether year/all-time need only daily rollups

If month works well:

- reuse daily cost rollups for year and all-time
- only add monthly financial rollups if the daily series prove too slow or too noisy

## Edge cases to verify

These are the failure modes most likely to break correctness:

- tariff values missing for parts of a day
- tariff interval different from energy integration interval
- quarter-hour alignment between import energy and tariff samples
- negative/positive sign handling on `gridPower_value`
- daylight saving transitions in local-day boundaries
- open current day producing incomplete costs
- duplicate infrastructure labels such as `host`

## Recommended validation checklist

For the next implementation session, validate at least:

1. One winter day with grid import and export.
2. One day with clearly changing dynamic prices.
3. One day with almost no grid import.
4. One month view against the Influx legacy dashboard.
5. One explicit manual sample calculation from raw points.

## Decision guardrails

These rules should remain fixed unless disproven:

- never sum prices directly
- never use time-weighted mean tariff as a cost substitute
- keep raw tariff panels available until rollup-backed costs are validated
- do not move price/cost logic into production namespace before the test dashboard pass is accepted

## Recommended first implementation order

1. `grid_import_cost_daily_eur`
2. `grid_export_credit_daily_eur`
3. weighted import/export average prices
4. month dashboard price panels
5. year and all-time price panels
