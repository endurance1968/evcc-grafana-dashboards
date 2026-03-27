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
- test-only grid import price and cost rollups in `test_evcc_*`
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

- the repository currently uses `test_evcc_*` for the reviewed daily rollup family; production `evcc_*` rollups are still outstanding
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
- export credit rollups are still not finalized
- next session check: evaluate whether the successful 10s -> 60s energy integration path should also replace direct daily integrate(...[1d]) rollups for pv, home, and loadpoint metrics
- next weekend task: review and add a blocklist for loadpoints, aligned with the Influx dashboard behavior
- next weekend task: review and add a blocklist for meters/counters, aligned with the Influx dashboard behavior
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

Goal:

- keep the current test-only import price/cost rollups as the baseline
- tune and validate them before any promotion to `evcc_*`
- then add export credit rollups on the same validated quarter-hour path

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

