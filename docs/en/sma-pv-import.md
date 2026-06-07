# Import SMA PV Data Into VictoriaMetrics

This page describes the optional import of per-source SMA Portal or Sunny Portal PV yield data into VictoriaMetrics. The importer is intended for comparison, plausibility checks, and historic generation-cost analysis. It does not replace EVCC live raw data and deliberately does not write to `pvPower_value`. System-wide SMA energy-balance data for old years without EVCC is documented separately: [sma-energy-balance-import.md](./sma-energy-balance-import.md).

## Purpose

EVCC provides the live power data used by the dashboards today. SMA exports usually provide daily yields from the inverter or portal side. These data can help with:

- checking EVCC PV yield against SMA Portal yield,
- importing historic daily yields over multiple years,
- finding mapping issues between EVCC titles and SMA Portal names,
- calculating historic PV generation costs when EVCC itself has no PV daily history for those years.

By default, the SMA importer writes into the EVCC-compatible daily metric:

```text
evcc_pv_energy_by_title_daily_wh{title="...", local_year="YYYY", local_month="MM"}
```

`title` is the EVCC/VictoriaMetrics title. SMA components are mapped to this title first and then summed per day/title. The import summary still shows which SMA names contributed to each title.

## Supported Input Formats

### SMA Portal Classic Monthly Analysis Files

The validated format is the classic SMA Portal analysis export with files named `Analyse_YYYY_MM.csv`. Columns contain portal components such as `Norddach 10000TL-20 / Gesamtertrag / Mittelwerte [kWh]`, rows contain local daily kWh values.

Example import for a full directory:

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --vm-base-url http://localhost:8428 \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^backnang_home$' \
  --write --replace
```

`--exclude-name-regex` matters when the export contains both individual components and a portal total. The total must not be imported together with the components for generation-cost analysis, otherwise PV yield is counted twice.

### Long Format

Template: `data/examples/sma-pv-energy-long.example.csv`

```csv
date,sma_name,energy_kwh
2026-06-01,SMA Portal Nord,12.4
2026-06-01,SMA Portal Sued,9.8
```

### Wide Format

Template: `data/examples/sma-pv-energy-wide.example.csv`

```csv
date,SMA Portal Nord,SMA Portal Sued,SMA Portal West
2026-06-01,12.4,9.8,1.6
2026-06-02,13.1,10.2,1.4
```

The importer detects comma, semicolon, and tab delimiters. Decimal comma is supported.

## Mapping File

Template: `data/examples/sma-pv-name-map.example.csv`

```csv
sma_name,evcc_title
norddach_10000tl-20,SMA-Nord
suddach_5000tl-20,SMA-Sued
carport_4000tl-21,SMA-Carport
```

`evcc_title` must match the titles used in the investment file. For SMA Portal Classic, portal component names are normalized: umlauts are converted to ASCII, spaces become `_`, and casing is ignored.

Multiple SMA components may map to the same `evcc_title`, for example when an inverter was replaced and both portal names belong to the same PV source. The import sums such daily values per EVCC title.

## Dry Run

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^portal_total$'
```

The dry run prints series, samples, range, mapped titles, and energy per title. Nothing is written to VictoriaMetrics.

## Calculate Generation Costs From SMA Daily Yields

After the SMA import, the investment helper can generate the cost metrics directly from this standard daily metric. `--pv-energy-metric` is not needed because `evcc_pv_energy_by_title_daily_wh` is the default:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2024-07-01 \
  --energy-source daily-metric \
  --skip-titles-without-energy \
  --write-pv-energy-rollup \
  --write --replace
```

`--skip-titles-without-energy` prevents investment costs from EVCC sources without matching SMA history from entering the totals. This is important when the current EVCC source structure is more granular than the old SMA Portal structure.

The helper still writes the normal dashboard metrics such as `evcc_pv_lcoe_yearly_ct_per_kwh` and `evcc_pv_effective_lcoe_yearly_ct_per_kwh`. Dashboards do not need long SMA-specific queries for this.

With `--write-pv-energy-rollup`, the helper also writes an EVCC-compatible daily PV yield:

```text
evcc_pv_energy_daily_wh{source="sma", local_year="YYYY", local_month="MM"}
```

This lets the normal PV year and month panels show historic SMA yields when no EVCC PV daily rollups exist for those years. Use this option only for intentional historic imports or test systems. If real EVCC rollups for `evcc_pv_energy_daily_wh` already exist in the same period, SMA and EVCC yield would be counted together.

## Combining With EVCC Live PVs

The SMA PV importer stays a pure importer. It writes `evcc_pv_energy_by_title_daily_wh` and does not calculate generation costs. To evaluate SMA history together with current EVCC PV data, first import SMA and then run the investment helper with `--energy-source combined`.

Dry run for cost calculation after SMA has already been imported:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2026-01-01 \
  --energy-source combined \
  --combined-energy-conflict prefer-evcc \
  --skip-titles-without-energy \
  --write-pv-energy-rollup
```

Write to the target VM only after the dry run looks correct:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2026-01-01 \
  --energy-source combined \
  --combined-energy-conflict prefer-evcc \
  --skip-titles-without-energy \
  --write-pv-energy-rollup \
  --write --replace
```

With `--energy-source combined`, EVCC `pvPower_value` and the daily metric `evcc_pv_energy_by_title_daily_wh` are merged per `evcc_title`. The default is `--combined-energy-conflict prefer-evcc`: when both sources have values for the same day, EVCC wins and the SMA value is ignored for that day. This avoids double-counting PV yield during overlap periods. The summary prints `evcc_days`, `metric_days`, `overlap_days`, and `merged_days` per title.

## Safety

Write only to a target or test VM, never to the production read-only instance. For the SMA importer, `--replace` deletes the target metric selected through `--metric`; the default is `evcc_pv_energy_by_title_daily_wh`. This is intended for controlled refresh imports. For the investment helper, `--replace` rewrites the generated `evcc_pv_*` generation-cost metrics. When `--write-pv-energy-rollup` is enabled, the helper deletes only `evcc_pv_energy_daily_wh{source="sma"}` or `evcc_pv_energy_daily_wh{source="combined"}` before reimporting and leaves real EVCC PV rollups untouched.




