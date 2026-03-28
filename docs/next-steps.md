# Next Steps

This file records the remaining work for the default VictoriaMetrics localization flow.

## Current state

Implemented:

- VM source dashboards under `dashboards/original/en`
- generated dashboards under `dashboards/translation/<language>`
- mapping-based localization for `de`, `fr`, `nl`, `es`, `it`, `zh`, `hi`
- localization audit with zero current missing candidates for the scripted key set
- Grafana import, smoke-check, cleanup, and screenshot automation for the default VM family
- family-separated screenshot output under `tests/artifacts/screenshots/vm`
- initial VM rollup CLI under `scripts/evcc-vm-rollup.py`
- operator guide under `docs/victoriametrics-aggregation-guide.md`
- reviewed grid import/export, battery, price, and cost rollups now exist in both `test_evcc_*` and promoted `evcc_*` namespaces
- historical clamp-based comparison results are documented, but the runtime clamp path and dashboard have been removed
- VM month review dashboard with working energy, battery, metric, price, and cost panels
- monthly Tibber comparison for May 2025 through February 2026 now exists for `Influx`, `sampled`, and `clamp`
- current decision baseline for import-side price and cost rollups is `sampled-old`; the later 60s-prebucketed `sampled-new` experiment was rejected after comparison

## Remaining technical work

### 0. VM rollup baseline for long-range dashboards

Current issue:

- the repository now has a validated VM rollup direction, and a reviewable VM month test dashboard exists; year and all-time still need to be finalized on top of it

Goal:

- use the accepted VM daily-rollup baseline for long-range dashboards
- avoid copying the Influx legacy monthly model unless measured VM performance later requires it

Primary references:

- `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`
- `docs/victoriametrics-rollup-design.md`

Additional current concerns:

- the reviewed daily rollup family now exists both as `test_evcc_*` for comparison/debugging and as promoted `evcc_*` for production dashboard use
- VM-side `host` labels were cleaned up, but ingest hygiene still needs to be watched so those labels do not reappear later
- if relevant historical host-only samples turn out to matter, a targeted reimport strategy may still be needed

### 0a. Finish VM month review pass

Current issue:

- the VM month dashboard is now close to the legacy reference, and the earlier clamp comparison decision is documented for traceability

Goal:

- close the remaining visual and semantic deltas in the month dashboard
- then use the month dashboard as the template for VM year and all-time work

Primary references:

- `dashboards/vm-month-test/original/en/VM_ EVCC_ Monat - Rollup Test.json`
- `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`

### 0b. Validate and tune VM price and cost rollups

Current issue:

- import-side daily price and cost rollups now exist in `test_evcc_*`, but they still need tighter validation against Influx legacy and Tibber reality
- the remaining drift is mainly in imported grid energy, not in the tariff series itself
- export-side credit rollups are implemented on the same validated 15-minute path; in the current history they evaluate to zero because `tariffFeedIn` is historically zero
- the all-time `Monthly costs` panel now hides `Income` series automatically when export-credit values are zero over the selected range; this keeps the chart readable on setups without feed-in compensation
- the `Today` main power plot now includes a PV forecast line again; it uses `avg(tariffSolar_value)` with `interval=1h`, is shown only in the main plot, and intentionally mirrors the smoother `Today - Details` forecast shape
- important maintenance note: the `Today` main power plot is backed by a Grafana library panel, so visual forecast changes must be applied there as well, not only in the dashboard wrapper JSON
- the positive-only 10s -> 60s bucket path has now also been adopted for `pv`, `home`, `loadpoint`, `vehicle`, `ext`, and `aux`; representative month checks improved drift versus Influx for those families
- the VM month dashboard now has an explicit `loadpointBlocklist` and separate `extBlocklist` / `auxBlocklist` controls for counters/meters
- local test default for the meter-side blocklist is currently `.*Car.*|.*Haupt.*`; any publicized dashboard should reset these blocklist defaults to `^none$`
- sampled vs clamp for monthly import costs has now been compared against Tibber for May 2025 through February 2026; excluding the incomplete October 2025 month, `sampled-old` currently has the lowest mean absolute error and remains the accepted baseline
- the later `sampled-new` cost-path experiment, which applied the 10s -> 60s prebucket logic before 15m tariff weighting, did not win overall and should stay rejected unless new evidence appears

Latest raw-data findings to continue from:

- `2026-02-01` was not a dashboard-only issue; `gridPower_value` in VM was damaged for that day and had to be repaired by deleting and fully reimporting `gridPower`
- after the `gridPower` repair, `test_evcc_*` had to be deleted and rebuilt because stale duplicate daily rollup samples still made the month dashboard show the old wrong value
- `2026-01-01` and `2026-01-02` were a second raw-data issue: VM was missing a continuous `gridPower_value` block from `2025-12-31T23:59:57Z` to `2026-01-02T01:45:27Z`
- that year-change block has now been repaired by targeted `gridPower` reimport plus a full `test_evcc_*` rebuild; the month dashboard now shows the corrected January values again
- separately, the first imported local day of `2025` showed the same first-hour boundary symptom: `2025-01-01` was missing exactly the first local hour in VM (`8280` vs `8640` points)
- `2025-01-01` was also repaired by targeted raw reimport
- likely root cause for that first imported local day: the global reimport window had started at `2025-01-01T00:00:00Z`; for `Europe/Berlin`, the local day `2025-01-01` starts already at `2024-12-31T23:00:00Z`
- future full-history reimports therefore need a deliberate UTC lead-in before the first local midnight, so the first local day is not truncated again
- month queries now use explicit `local_year` and `local_month` rollup labels instead of repeated inline timezone/month guards; this pattern should be reused for year/all-time dashboards
- current year-dashboard vehicle odometer semantics use the highest known odometer value per vehicle, not the last raw point, because raw odometer series can contain later zero resets or split loadpoint-specific paths

Goal:

- keep `evcc_*` as the promoted production namespace and `test_evcc_*` as the parallel debug/review namespace
- continue validating the promoted sampled path against Influx legacy and Tibber as needed
- keep the export-credit rollups on the same validated quarter-hour path; with the current historical data they remain zero because `tariffFeedIn` is zero
- before adding many more rollup metrics, create a concrete runtime profile of the Python rollup CLI on the existing multi-year history
- measure separately:
  - VM query time
  - Python aggregation and bucketing time
  - VM import/write time
  - monthly chunk overhead
- only optimize after those measurements identify the real bottleneck
- profiling output is now built into `scripts/evcc-vm-rollup.py`; the first short dry-run showed VM HTTP/query time dominating, with price aggregation the next largest block
- after a full production rebuild from `2025-01-01` to `2026-03-27`, total runtime was about `562.65s`; the dominant cost was `http_get_json_s ~= 472.56s` over `14883` calls, while VM write/import time stayed negligible at about `0.4s`
- the first optimization priority is therefore query consolidation, not import tuning
- priority 1: merge the tariff/cost paths so `grid`, `tariffGrid`, `tariffFeedIn`, `chargePower`, and related vehicle/grid price inputs are fetched once per chunk and then reused locally for daily and quarter-hour rollups
- priority 2: merge positive-energy paths (`pv`, `home`, `loadpoint`, `vehicle`, `ext`, `aux`) so their raw power samples are fetched once per chunk and split into day/local-label rollups in Python instead of by many day-local queries
- first implementation of that optimization now runs under a separate comparison prefix `evcc_cmp_*` via `scripts/evcc-vm-rollup-compare.conf.example`, so existing production rollups in `evcc_*` stay untouched during profiling and semantic comparison
- first full comparison rebuild on `evcc_cmp_*` reduced total runtime from about `562.65s` to about `248.34s`; `http_get_json_calls` dropped from `14883` to `3708`, and `http_get_json_s` dropped from about `472.56s` to about `152.07s`
- the optimized comparison path is not yet accepted as production-identical: the first year-level check still showed a small residual delta against the current `evcc_*` baseline (about `0.89 kWh` on 2025 grid import and about `5.72 EUR` on 2025 grid-import cost), so semantic verification must continue before promotion
- only after those two larger read-side reductions should smaller candidates such as `batterySoc` step size or catalog fetches be revisited
- in the same review, analyze which derived views are better computed directly in dashboard queries instead of being materialized as extra rollups
- especially check whether simple ranking/aggregation views such as top-5 and top-30 PV health metrics are straightforward enough in MetricsQL to avoid dedicated rollup series

Current classification after the first review:

Keep as rollup:

- `*_energy_daily_wh` families for `pv`, `home`, `loadpoint`, `vehicle`, `ext`, and `aux`; these are the shared long-range baseline and are cheap to reuse from Grafana
- `battery_soc_daily_min_pct` and `battery_soc_daily_max_pct`; they are small, stable, and repeatedly reused in month/year/all-time panels
- `grid_import_daily_wh`; now based on the real `gridEnergy` counter and therefore the cleanest daily import baseline
- `grid_export_daily_wh`, `battery_charge_daily_wh`, and `battery_discharge_daily_wh`; they remain necessary daily long-range inputs even though export still needs separate semantic review
- tariff-weighted daily finance series such as `grid_import_cost_daily_eur`, `grid_import_price_*_daily_ct_per_kwh`, and `grid_export_credit_daily_eur`; they depend on quarter-hour weighting and are too expensive and too ugly to rebuild ad hoc in many dashboard panels
- `vehicle_charge_cost_daily_eur` and `potential_vehicle_charge_cost_daily_eur`; these are reused vehicle baselines and depend on the same quarter-hour weighting path
- `potential_home_cost_daily_eur`, `potential_loadpoint_cost_daily_eur`, `battery_discharge_value_daily_eur`, and `battery_charge_feedin_cost_daily_eur`; these are accepted balance/amortization base series and should stay materialized while the all-time finance block settles
- `pv_top30_mean_yearly_wh` and `pv_top5_mean_monthly_wh` for now; despite the general preference to avoid excess rollups, these two are not elegant to derive from the current daily-series shape in plain MetricsQL; direct VM prototypes such as `topk_avg(5, last_over_time(evcc_pv_energy_daily_wh{...}[400d]))` only rank the single month series and do not reproduce the Influx-style top-N-over-points result

Better kept in dashboard queries or Grafana math:

- yearly and monthly sums over existing daily rollups
- top tables such as `highest yield`, `highest feed-in`, and `highest home consumption`
- power-balance totals and comparisons composed from existing daily rollups
- PV and battery amortization ratios, payback durations, and annualized projections
- vehicle summary panels that combine already materialized daily energy/cost/distance series with lightweight dashboard math

Practical rule going forward:

- materialize only when the result is either reused in many places or hard to express efficiently from the existing daily series
- prefer dashboard-side aggregation when the result is just a sum, average, ratio, ranking table, or other lightweight composition over existing daily rollups

Primary references:

- `docs/victoriametrics-price-rollup-plan.md`
- `docs/victoriametrics-rollup-design.md`

Decision snapshot:

- accepted baseline: `test_evcc_*` with the original `sampled-old` import-cost path
- historical comparison path: `test_evcc_clamp_*` was evaluated and then removed
- rejected experiment for now: `sampled-new`
- decision basis: month-cost comparison against Tibber now favors `sampled` on total deviation, so further tuning should continue only on the sampled path

Algorithm note for the compared month-cost paths:

- `Influx`: legacy path from `evcc_agg`; import energy is derived with the original Influx aggregation semantics, i.e. negative/positive filtering plus `mean(value)` on fixed 60s buckets, followed by daily integration on local Europe/Berlin day windows
- `sampled`: current VM baseline in `test_evcc_*`; import energy for the daily energy rollups follows the corrected raw-sample-based path used in the Python rollup CLI, while import cost is calculated from sampled quarter-hour import energy plus the quarter-hour tariff selection used in the script
- `clamp`: historical VM comparison path; it used the same daily energy baseline as the accepted sampled path for grid and battery energy, but kept a clamp-oriented quarter-hour import-cost path for price/cost rollups
- this means the remaining visible difference between `sampled` and `clamp` is no longer the daily grid energy itself, but mainly how quarter-hour import energy is converted into cost and effective import price

Month-cost comparison against Tibber, without the incomplete October 2025 month:

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

### 1. Reduce mixed-language source internals

Dashboard color palette (fixed where possible):
- PV: #73BF69
- Grid import: #E24D42
- Home: #5794F2
- Feed-in: #2F8F5B
- Other: #9FA7B3


Current issue:

- the imported VM upstream snapshot still contains German source strings in internal wiring and panel metadata

Goal:

- separate internal identifiers from user-visible labels
- keep stable internals language-neutral
- localize only display properties

### 2. Extend the VM source set

Current issue:

- upstream currently provides only three VM dashboards

Goal:

- add more VM-native dashboards once upstream provides them or the repo grows them locally in a maintainable way

### 3. Review screenshots after each mapping pass

Goal:

- inspect the latest screenshot sets under `tests/artifacts/screenshots/vm`
- document visible residual German or English text
- classify each case as:
  - safe display-only fix
  - source dashboard refactor needed
  - data-driven text from tags or measurements

### 4. Keep family separation strict

Goal:

- maintain VM as the short default path
- keep Influx only under `dashboards/influx-legacy`, `docs/influx-legacy`, and `scripts/influx-legacy`
- avoid cross-family assumptions in shared scripts

## Maintainer reading order

If you are new to the current default flow, start with:

1. `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`
2. `docs/victoriametrics-rollup-design.md`
3. `docs/victoriametrics-aggregation-guide.md`
4. `docs/vm-thread-restart-handoff-2026-03-21.md`
5. `docs/localization-maintainer-workflow.md`
6. `docs/grafana-localization-testing.md`
7. `scripts/test/README.md`
8. `docs/localization-review-2026-03-21.md`

