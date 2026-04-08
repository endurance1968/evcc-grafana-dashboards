# VictoriaMetrics Schema Reference

This document describes the VictoriaMetrics schema that is actively used by the EVCC VM dashboards and the current Python rollup pipeline.

It is a reference for:

- raw metric families used directly by dashboards
- daily rollup families written by `scripts/rollup/evcc-vm-rollup.py`
- accepted labels and naming rules
- the practical split between raw-data dashboards and rollup-based dashboards

## Scope

This is the schema in active use now.

It intentionally documents:

- the production rollup namespace `evcc_*`
- the raw `*_value` metrics queried by the dashboards and rollup script

It intentionally does not document:

- historical comparison namespaces have been removed
- removed compare namespaces
- obsolete clamp-vs-sampled experiments

## Core conventions

- Raw EVCC metrics stay untouched in VictoriaMetrics.
- Rollups are written as new metrics in a separate namespace.
- The production rollup namespace is `evcc_*`.
- The repository assumes one VictoriaMetrics instance per EVCC instance.
- If you operate multiple EVCC instances, run multiple VictoriaMetrics instances instead of multiplexing them through a shared `db` label.
- Dashboards and rollups must not depend on a `host` label.
- Units are encoded in metric names.
- Only real business dimensions are kept as labels.

## Logical layers

### Layer 1: raw metrics

Raw metrics are the source of truth for:

- `Today`
- `Today - Details`
- `Today - Mobile`
- debugging and validation
- recomputation of rollups

Typical raw metric naming style:

- `<measurement>_value`

Examples:

- `pvPower_value`
- `homePower_value`
- `gridPower_value`
- `gridEnergy_value`
- `chargePower_value`
- `batteryPower_value`
- `batterySoc_value`
- `vehicleOdometer_value`
- `tariffGrid_value`
- `tariffFeedIn_value`
- `tariffPriceLoadpoints_value`
- `tariffSolar_value`

### Layer 2: daily rollups

Daily rollups are the default input for:

- `Monat`
- `Jahr`
- `All-time`

The rollup script writes one sample per local day and series.

### Layer 3: dashboard-side aggregations

Month, year and all-time dashboards build:

- yearly sums
- monthly sums
- ratios
- balance and amortization values
- top tables

from the daily rollups.

There is currently no required monthly-rollup layer.

## Stable label rules

### Raw metrics

Raw EVCC history should be queried directly by metric name and business labels only:

- example: `pvPower_value{id=""}` or `evcc_pv_energy_daily_wh{local_year="2025",local_month="07"}`

Avoid relying on:

- `host`

Reason:

- imported history can be hostless
- live writes can carry extra infra labels
- host-dependent queries break historical correctness

### Daily rollups

All daily rollups always carry:

- `local_year`
- `local_month`

Additional labels are added only where they are real dimensions:

- `loadpoint`
- `vehicle`
- `title`

Accepted examples:

- `evcc_pv_energy_daily_wh{local_year="2025",local_month="07"}`
- `evcc_vehicle_energy_daily_wh{vehicle="BMW i3",local_year="2025",local_month="07"}`
- `evcc_ext_energy_daily_wh{title="USV",local_year="2025",local_month="07"}`

Not stored on rollups:

- `local_day`
- `local_date`
- `host`

Important note:

- `local_day` and `local_date` exist internally in the script window model
- they are intentionally not written as labels, because they would fragment each daily family into one series per day

## Raw metric families in active use

### Energy and power

These raw metrics feed the long-range rollups:

| Raw metric | Meaning | Main use |
| --- | --- | --- |
| `pvPower_value` | PV power | PV daily energy |
| `homePower_value` | Home power | Home daily energy, no-PV baseline |
| `chargePower_value` | Charging power | Loadpoint energy, vehicle energy, vehicle cost |
| `extPower_value` | External meter power | Meter-side home breakdown |
| `auxPower_value` | Auxiliary meter power | Auxiliary meter breakdown |
| `gridPower_value` | Grid power | Grid export energy, dynamic price weighting |
| `gridEnergy_value` | Grid import counter | Grid import daily energy |
| `batteryPower_value` | Battery power | Charge/discharge energy, battery valuation |
| `batterySoc_value` | Battery SOC | Daily min/max SOC |
| `vehicleOdometer_value` | Vehicle odometer | Daily driven distance |

### Tariffs and forecast

These raw metrics are also in active use:

| Raw metric | Meaning | Main use |
| --- | --- | --- |
| `tariffGrid_value` | Grid tariff | Import cost and price rollups |
| `tariffFeedIn_value` | Feed-in tariff | Export credit and battery opportunity cost |
| `tariffPriceLoadpoints_value` | Loadpoint charging tariff | Vehicle charging cost |
| `tariffSolar_value` | Solar forecast | `Today` and `Today - Details` PV forecast panels |

## Production daily rollup families

The production prefix is currently `evcc`.

### Energy and SOC baselines

| Metric | Labels | Meaning |
| --- | --- | --- |
| `evcc_pv_energy_daily_wh` | `local_year`, `local_month` | Daily PV energy |
| `evcc_home_energy_daily_wh` | `local_year`, `local_month` | Daily home energy |
| `evcc_loadpoint_energy_daily_wh` | `local_year`, `local_month`, `loadpoint` | Daily charging energy per loadpoint |
| `evcc_vehicle_energy_daily_wh` | `local_year`, `local_month`, `vehicle` | Daily charging energy per vehicle |
| `evcc_vehicle_distance_daily_km` | `local_year`, `local_month`, `vehicle` | Daily driven distance per vehicle |
| `evcc_ext_energy_daily_wh` | `local_year`, `local_month`, `title` | Daily energy per external meter title |
| `evcc_aux_energy_daily_wh` | `local_year`, `local_month`, `title` | Daily energy per auxiliary meter title |
| `evcc_battery_soc_daily_min_pct` | `local_year`, `local_month` | Minimum daily battery SOC |
| `evcc_battery_soc_daily_max_pct` | `local_year`, `local_month` | Maximum daily battery SOC |
| `evcc_grid_import_daily_wh` | `local_year`, `local_month` | Daily grid import energy |
| `evcc_grid_export_daily_wh` | `local_year`, `local_month` | Daily grid export energy |
| `evcc_battery_charge_daily_wh` | `local_year`, `local_month` | Daily battery charge energy |
| `evcc_battery_discharge_daily_wh` | `local_year`, `local_month` | Daily battery discharge energy |

### Daily finance and price baselines

| Metric | Labels | Meaning |
| --- | --- | --- |
| `evcc_grid_import_cost_daily_eur` | `local_year`, `local_month` | Daily grid import cost |
| `evcc_grid_import_price_avg_daily_ct_per_kwh` | `local_year`, `local_month` | Arithmetic daily mean of import tariff |
| `evcc_grid_import_price_effective_daily_ct_per_kwh` | `local_year`, `local_month` | Effective daily import price weighted by import energy |
| `evcc_grid_import_price_min_daily_ct_per_kwh` | `local_year`, `local_month` | Minimum daily import tariff |
| `evcc_grid_import_price_max_daily_ct_per_kwh` | `local_year`, `local_month` | Maximum daily import tariff |
| `evcc_grid_export_credit_daily_eur` | `local_year`, `local_month` | Daily feed-in compensation |
| `evcc_vehicle_charge_cost_daily_eur` | `local_year`, `local_month`, `vehicle` | Daily charging cost at loadpoint tariff |
| `evcc_potential_vehicle_charge_cost_daily_eur` | `local_year`, `local_month`, `vehicle` | Daily charging cost at grid tariff as no-PV baseline |
| `evcc_potential_home_cost_daily_eur` | `local_year`, `local_month` | Daily home cost at grid tariff as no-PV baseline |
| `evcc_potential_loadpoint_cost_daily_eur` | `local_year`, `local_month` | Daily charging cost at grid tariff as no-PV baseline |
| `evcc_battery_discharge_value_daily_eur` | `local_year`, `local_month` | Daily value of discharged battery energy at grid tariff |
| `evcc_battery_charge_feedin_cost_daily_eur` | `local_year`, `local_month` | Daily opportunity cost of battery charging at feed-in tariff |

### PV health rollups

These are helper rollups for the all-time plant-health section:

| Metric | Labels | Meaning |
| --- | --- | --- |
| `evcc_pv_top30_mean_yearly_wh` | `local_year` | Mean of the top 30 PV daily values of a year |
| `evcc_pv_top5_mean_monthly_wh` | `local_year`, `local_month` | Mean of the top 5 PV daily values of a month |

## Source-of-truth rules by topic

### Grid import

Current rule:

- `evcc_grid_import_daily_wh` comes from the local-day spread of `gridEnergy_value`

This is intentional, because:

- `gridEnergy_value` behaves like the real cumulative import counter
- it aligns better with the metered import path than integrating `gridPower_value`

### Grid export

Current rule:

- `evcc_grid_export_daily_wh` is still derived from `gridPower_value`

Reason:

- there is no separate export-energy counter path in the current raw data set

### Battery energy

Current rule:

- battery charge/discharge rollups come from sign-aware processing of `batteryPower_value`

### Vehicle distance

Current rule:

- daily vehicle distance is derived from odometer spread
- odometer series can split by other labels and can later emit zero values
- dashboards may therefore use `max known odometer` semantics rather than `last raw point` for display

## Aggregation model used by the rollup script

### Daily windowing

- Local day windows are built in the configured timezone.
- Current timezone default is `Europe/Berlin`.
- A daily sample timestamp is written at the UTC start of the corresponding local day.

### Energy rollups

Positive energy families use:

- raw samples on the configured raw step
- then 60-second rollup buckets
- then day-local aggregation

Grid and battery sign-aware families use dedicated sign handling on top of sampled power series.

### Price and cost rollups

Price and cost rollups use:

- raw tariff series
- 15-minute bucket boundaries
- day-local windows
- import/export or charge energy weighted against the matching tariff

## Dashboard-to-schema mapping

### Raw dashboards

These dashboards query raw metrics directly:

- `VM_ EVCC_ Today.json`
- `VM_ EVCC_ Today - Details.json`
- `VM_ EVCC_ Today - Mobile.json`

Special note:

- the `Today` PV forecast line uses raw `tariffSolar_value`
- the large `Today` power plot is a Grafana library panel, so source changes must also update the library panel

### Rollup dashboards

These dashboards query the `evcc_*` rollups:

- `VM_ EVCC_ Monat.json`
- `VM_ EVCC_ Jahr.json`
- `VM_ EVCC_ All-time.json`

These dashboards rely heavily on:

- `local_year`
- `local_month`

to keep queries readable and to avoid repeated inline timezone guards.

## Practical filtering rules used by dashboards

The schema itself carries business dimensions, and the dashboards apply blocklists on top:

- `loadpointBlocklist`
- `extBlocklist`
- `auxBlocklist`
- `vehicleBlocklist`

These are dashboard-level filters, not part of the database schema design.

Examples:

- hiding non-user-facing loadpoints
- hiding internal or unwanted meter titles
- excluding non-vehicle pseudo vehicles from vehicle panels

## Operational notes

### Host label

- Historical correctness depends on hostless-safe queries.
- If `host` reappears through ingest, dashboards should still remain correct because they query metric names directly and aggregate `without(host)` where required.

### Performance

The current production rollup path uses chunked raw-data fetches and local reuse of fetched samples.

Recent full rebuild profile over `2025-01-01 .. 2026-03-27`:

- total runtime about `252.60s`
- peak RAM about `1266 MB`
- VM write time negligible
- main cost center is still VM read/query time

### Namespace status

Current intended production state:

- only `evcc_*` is relevant
- old test and compare namespaces are no longer part of the active design

## Short checklist for future schema changes

When adding a new raw metric or rollup family, keep these rules:

1. Do not overwrite raw metrics.
2. Keep one VictoriaMetrics instance dedicated to one EVCC instance and query metric names directly.
3. Do not require `host`.
4. Only add labels that represent real business dimensions.
5. Reuse `local_year` and `local_month` only when they materially simplify long-range dashboard queries.
6. Avoid `local_day` or `local_date` on stored daily rollups.
7. Prefer dashboard-side aggregation unless the result is reused often or expensive to compute repeatedly.


