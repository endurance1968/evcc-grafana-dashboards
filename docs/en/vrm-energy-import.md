# Optional VRM Battery Flow Import

This optional extension imports daily battery energy-flow values from the Victron VRM portal into VictoriaMetrics. It is useful when EVCC battery charge/discharge values are not accurate enough, or when you want to cross-check battery efficiency with VRM daily values.

The import does not replace EVCC raw data or the normal `evcc_*` rollups. It only adds optional daily metrics for the Month dashboard.

## Imported Metrics

The helper reads VRM daily kWh statistics and writes these daily metrics:

- `evcc_vrm_pv_to_battery_daily_wh`
- `evcc_vrm_grid_to_battery_daily_wh`
- `evcc_vrm_battery_to_consumers_daily_wh`
- `evcc_vrm_battery_to_grid_daily_wh`
- `evcc_vrm_battery_charge_daily_wh`
- `evcc_vrm_battery_discharge_daily_wh`

No separate loss metric is written. Losses are simply `battery_charge - battery_discharge`.

## Installation

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Alternative Forgejo example:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

sudo mkdir -p /opt/evcc-vm-tools
curl -fsSLo /tmp/import-vrm-energy-flows.py "$BASE/scripts/helper/import-vrm-energy-flows.py"
curl -fsSLo /tmp/validate-vrm-import.py "$BASE/scripts/helper/validate-vrm-import.py"
sudo install -m 0755 /tmp/import-vrm-energy-flows.py /opt/evcc-vm-tools/import-vrm-energy-flows.py
sudo install -m 0755 /tmp/validate-vrm-import.py /opt/evcc-vm-tools/validate-vrm-import.py
```

## Historical Backfill

For the first run, import values from 2025-01-01. The end day is inclusive; yesterday is usually the right completed day.

```bash
sudo /usr/bin/python3 /opt/evcc-vm-tools/import-vrm-energy-flows.py \
  --site-id "<VRM_SITE_ID>" \
  --token "<VRM_API_TOKEN>" \
  --vm-base-url "http://127.0.0.1:8428" \
  --start-day 2025-01-01 \
  --end-day "$(date -d 'yesterday' +%F)" \
  --output-json /tmp/vrm-import-source.json \
  --write --replace-range
```

## Daily Refresh

A daily run is enough because VRM provides daily energy values. A seven-day lookback also refreshes late VRM corrections.

```cron
25 6 * * * /usr/bin/python3 /opt/evcc-vm-tools/import-vrm-energy-flows.py --site-id "<VRM_SITE_ID>" --token "<VRM_API_TOKEN>" --vm-base-url "http://127.0.0.1:8428" --lookback-days 7 --write --replace-range >> /var/log/evcc-vm-vrm-energy.log 2>&1
```

## Dashboard

When the metrics exist, the Month dashboard shows two additional panels in the `Battery` tab:

- `VRM battery efficiency`: charge, discharge, and efficiency from VRM flow data.
- `VRM battery flows`: PV to battery, grid to battery, battery to consumers, and battery to grid.

## Validate The Import

The importer can save normalized VRM source rows from the same run through `--output-json`. Then compare all six imported metrics day by day with VictoriaMetrics:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-tools/validate-vrm-import.py \
  --vm-base-url "http://127.0.0.1:8428" \
  --vrm-json /tmp/vrm-import-source.json \
  --start-day 2025-01-01 \
  --end-day "$(date -d 'yesterday' +%F)"
```

The validator must report `missing=0`, `extra=0`, and `duplicates=0` for every metric. For a known reference month, add `--expected-efficiency-pct` and `--efficiency-tolerance-pp`. A second import with identical boundaries and `--replace-range` must produce the same sample count and daily values.