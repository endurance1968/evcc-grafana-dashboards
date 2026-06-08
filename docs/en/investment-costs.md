# Investment Costs For Effective Electricity Price

This document describes a generic way to maintain investment costs for PV arrays, batteries, and shared system components. The goal is a future effective electricity price calculation based on real EVCC/VictoriaMetrics data plus local investment metadata.

## File Locations

The public templates are stored here:

- `data/examples/investments.example.xlsx` for manual editing in Excel, LibreOffice, or OnlyOffice
- `data/examples/investments.example.csv` as a script-friendly text variant with the same columns

Real values should stay local and must not be committed to Git:

- preferred: `data/private/investments.xlsx`
- alternative: `data/private/investments.csv`

`data/private/` is reserved for private installation data and is excluded through `.gitignore`.

## Basic Idea

VictoriaMetrics provides measured values and rollups, for example:

- PV production from `pvPower_value`
- grid import costs from `evcc_grid_import_cost_daily_eur`
- feed-in credit from `evcc_grid_export_credit_daily_eur`
- consumption from `evcc_home_energy_daily_wh` and `evcc_loadpoint_energy_daily_wh`
- battery energy from `evcc_battery_charge_daily_wh` and `evcc_battery_discharge_daily_wh`

The Excel/CSV file adds metadata EVCC cannot know: commissioning date, purchase price, depreciation lifetime, optional operating costs, and for shared PV components the allocation to multiple EVCC PV titles.

## Columns

| Column | Meaning |
| --- | --- |
| `asset_id` | Stable technical name of the investment. Each standalone investment needs an ID. For `pv_shared`, the same ID is intentionally repeated so the helper can validate the allocation. |
| `asset_type` | Asset type: `pv`, `pv_shared`, `battery`, or `system`. |
| `evcc_title` | Exact EVCC/VictoriaMetrics title matching `pvPower_value{title="..."}`. Mandatory for PV and `pv_shared`, because this maps cost to energy. |
| `allocation_percent` | Share as a number from `0` to `1`, mandatory only for `pv_shared`. `1` means 100 %, `0.5` means 50 %. Fractions such as `1/3` are accepted. All included rows with the same `asset_id` should sum to `1.0`; otherwise the helper prints a warning. |
| `commissioning_date` | Commissioning date of this investment row in `YYYY-MM-DD` format. Depreciation starts on this date for this row only. |
| `purchase_price_eur` | Purchase cost in EUR. Subtract grants or rebates beforehand if they should reduce the investment basis. |
| `lifetime_years` | Depreciation lifetime in years. `20` is a reasonable simple assumption for PV and batteries. After this period, this investment row no longer contributes yearly costs. |
| `yearly_opex_eur` | Optional yearly operating costs, such as maintenance, insurance, or portal fees. `0` is allowed. |
| `watt_peak` | Installed PV power in Wp. Mandatory for `asset_type=pv`, not needed for `pv_shared`. |
| `capacity_wh` | Battery capacity in Wh. Relevant for battery assets only. |
| `include_in_effective_price` | `yes` or `no`. Controls whether the row contributes to the calculation. |
| `notes` | Free-text local notes. |

## Asset Types

- `pv`: Separately measured PV source or later additional investment for that source. `evcc_title` must exactly match the EVCC title. Several `pv` rows with the same `evcc_title` are added on the cost side; PV energy is counted only once per title.
- `pv_shared`: Shared PV component, for example an inverter, MPPT, or distributor used by multiple PV sources. Repeat the same `asset_id`, set one target `evcc_title` per row, and use `allocation_percent` to distribute the cost. Example: three rows with `1/3`, `1/3`, `1/3`.
- `battery`: Battery storage. Included in the template for later system-price calculations, but not part of the current PV-only generation-cost helper.
- `system`: General installation cost that is neither clearly PV nor battery. Also intended for a later system-price calculation.

## Current PV-Only Helper

The current implementation is `scripts/helper/import-investment-costs.py`. It intentionally calculates only PV investment costs and ignores battery and grid effects for now.

The helper:

1. reads `data/private/investments.xlsx` or `.csv`,
2. uses included `asset_type=pv` and `asset_type=pv_shared` rows,
3. validates whether `pv_shared` allocations sum to 100 % per `asset_id`,
4. groups multiple investment rows with the same `evcc_title`,
5. reads measured PV energy per `evcc_title` from EVCC `pvPower_value`, from an existing daily metric such as `evcc_pv_energy_by_title_daily_wh`, or from a combination of both sources,
6. writes generated metrics back to VictoriaMetrics.

Generated metrics:

- `evcc_pv_investment_cost_daily_eur`
- `evcc_pv_lcoe_daily_ct_per_kwh`
- `evcc_pv_lcoe_rolling_7d_ct_per_kwh`
- `evcc_pv_lcoe_yearly_ct_per_kwh`
- `evcc_pv_lcoe_cost_monthly_eur`
- `evcc_pv_effective_lcoe_daily_ct_per_kwh`
- `evcc_pv_effective_lcoe_monthly_ct_per_kwh`
- `evcc_pv_effective_lcoe_yearly_ct_per_kwh`
- `evcc_pv_lcoe_energy_monthly_wh`
- `evcc_pv_investment_cost_monthly_eur`
- `evcc_pv_lcoe_monthly_ct_per_kwh`

The `Year` dashboard shows these values in the PV tab with two panels: `PV generation costs` on the left for annual values per PV source plus a weighted total and `PV generation cost/week (ct/kWh)` on the right as rolling 7-day time-series lines per PV source in the selected year. Annual coverage is shown directly after the PV title in the left panel, for example `SMA-Nord (43%)`. The dashboard intentionally reads short helper metrics instead of long MetricQL expressions.

The All-time dashboard also shows PV generation costs in the Finances tab: the left panel dynamically calculates weighted values for the selected Grafana time range per PV source plus a total, while the right panel shows annual values as a time series over the selected time range. The dynamic calculation uses monthly helper metrics for cost and energy so a selected year in the All-time dashboard remains consistent with the Year dashboard. The yearly time-series panel only shows years with at least 95% data coverage so partial years do not appear as real cost outliers.

Annual source values below 1 kWh mapped PV energy and weekly windows below 1 kWh mapped PV energy are suppressed to avoid misleading division-by-near-zero results.

For generation costs, the helper includes investment costs in the LCOE calculation only for days where the corresponding `evcc_title` also has PV energy. This prevents incomplete annual source files from being divided by full-year costs. Active investment costs remain visible through their separate daily/monthly cost metrics.

Incomplete coverage is marked compactly:

- `evcc_pv_lcoe_yearly_ct_per_kwh` also carries a `coverage` label so the dashboard can show coverage directly after the PV title.
- `--partial-warning-threshold` controls the warning threshold, default `0.95`.
- `--min-lcoe-coverage-ratio` can optionally require a minimum coverage before monthly, yearly, and 7-day LCOE values are written. The default `0.0` writes values while still marking partial coverage.

## Calculate Generation Costs

For normal EVCC installations, the standard path through EVCC `pvPower_value` is enough. The helper reads PV energy per `evcc_title` directly from existing EVCC raw data and writes the cost metrics used by the dashboards.

Dry run:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --energy-source pv-power
```

Write or replace the generated metrics only on the target VictoriaMetrics instance:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --energy-source pv-power \
  --write --replace
```

`--replace` replaces only investment/cost metrics generated by the helper. EVCC raw data stays unchanged.

## Regular Updates

The helper is optional and runs separately from the normal EVCC/VictoriaMetrics rollup. If the investment file changes or the current year should stay up to date in the dashboard, run the helper again after the normal rollup, for example daily via cron or a systemd timer. For completed historical years, one run is enough as long as neither the investment file nor the imported PV energy changes.

Important: The helper writes only its own investment and generation-cost metrics. It does not replace EVCC ingest, SMA import, or the standard rollup. In particular, it does not write or delete `evcc_pv_energy_by_title_daily_wh`; that metric belongs to energy imports or rollups.

## Advanced Energy Sources

The options `--energy-source daily-metric` and `--energy-source combined` are special cases. They are relevant when a per-title daily metric such as `evcc_pv_energy_by_title_daily_wh` already exists in VictoriaMetrics and should intentionally be used instead of or in addition to EVCC `pvPower_value`. Normal EVCC setups do not need these variants.

## Planned System Metrics

A future robust effective system electricity price calculation would be:

```text
effective electricity price =
(grid import costs - feed-in credit + PV depreciation + battery depreciation + operating costs)
/
(home consumption + loadpoint consumption)
```

For a separate battery view, an additional metric can be calculated:

```text
battery cost per discharged kWh = battery depreciation / battery discharge
```

The main system metric should still include battery depreciation because the battery is part of the real electricity system cost.

## Notes For EVCC Users

- PV titles must exactly match the EVCC titles. In VictoriaMetrics, this can be checked via `pvPower_value{title="..."}`.
- If EVCC IDs changed over time, `title` is more stable than `id`.
- Shared PV costs can be distributed to multiple EVCC titles through `pv_shared`. The helper warns if one shared asset does not sum to 100 %.
- The file contains financial metadata and should not be committed to a public repository.
