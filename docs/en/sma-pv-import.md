# Import SMA PV Data Into VictoriaMetrics

This page describes the optional import of per-source SMA Portal or Sunny Portal PV yield data into VictoriaMetrics. The importer is intended for comparison, plausibility checks, and historic daily PV yields. It does not replace EVCC live raw data and deliberately does not write to `pvPower_value`. System-wide SMA energy-balance data for old years without EVCC is documented separately: [sma-energy-balance-import.md](./sma-energy-balance-import.md).

## Purpose

EVCC provides the live power data used by the dashboards today. SMA exports usually provide daily yields from the inverter or portal side. These data can help with:

- checking EVCC PV yield against SMA Portal yield,
- importing historic daily yields over multiple years,
- finding mapping issues between EVCC titles and SMA Portal names,
- showing historic daily PV yields when EVCC itself has no PV daily history for those years.

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

`--exclude-name-regex` matters when the export contains both individual components and a portal total. The total must not be imported together with the components, otherwise PV yield is counted twice.

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

`evcc_title` is mandatory and must match the title under which the source should be evaluated in the dashboards. For SMA Portal Classic, portal component names are normalized: umlauts are converted to ASCII, spaces become `_`, and casing is ignored.

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

## Write to VictoriaMetrics

When the dry run looks plausible, write the import to the target VM:

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --vm-base-url http://localhost:8428 \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^portal_total$' \
  --write --replace
```

For the SMA PV importer, `--replace` deletes only the target metric selected through `--metric`. The default is `evcc_pv_energy_by_title_daily_wh`. This is intended for controlled refresh imports and does not change EVCC raw data such as `pvPower_value`.

## Verify the Result

After the import, the expected titles and ranges should be visible in VictoriaMetrics:

```bash
curl "http://localhost:8428/api/v1/series?match[]=evcc_pv_energy_by_title_daily_wh"
```

For a quick plausibility check, sum the imported energy per title:

```bash
curl --get "http://localhost:8428/api/v1/query" \
  --data-urlencode 'query=sum(evcc_pv_energy_by_title_daily_wh) by (title) / 1000'
```

## Combining With EVCC Live PVs

The SMA PV importer stays a pure importer. It writes daily yields per `title` and does not calculate further metrics. If real EVCC rollups and imported SMA daily values exist in the same period, downstream evaluations must intentionally decide which source to use so PV yield is not counted twice.

## Safety

Write only to a target or test VM, never uncontrolled to a production instance. Always review the dry run before `--write --replace`. For the SMA PV importer, `--replace` is intended for repeatable refresh imports and affects only the SMA PV import target metric.
