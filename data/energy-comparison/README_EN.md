# Energy comparison data

German version: [README.md](./README.md).

This directory is a location for private external energy comparison data. It is not required for normal dashboard operation and regular users do not need it.

The data is intentionally outside `tmp/` because it can be reused for private migration, rollup, and release validation.

- `tibber/`: local Tibber API exports or comparison snapshots.
- `vrm/`: local Victron VRM daily kWh cache files.

The actual cache/export files are machine-local and ignored by Git. Keep only this documentation and `.gitkeep` files tracked. Private snapshots can contain installation IDs, local paths, energy consumption, or cost data and must not be committed to the public repository.

## Battery Efficiency

The dashboard value `Battery efficiency` is an energy-flow ratio, not a manufacturer statement about cell or inverter efficiency:

```text
Battery efficiency = battery discharge / battery charge * 100
```

In VictoriaMetrics the dashboard uses `evcc_battery_discharge_daily_wh` and `evcc_battery_charge_daily_wh`. An optional VRM comparison can use the closest matching VRM flows:

```text
VRM battery charge    = pv_to_battery_kwh + grid_to_battery_kwh
VRM battery discharge = battery_to_consumers_kwh + battery_to_grid_kwh
```

Short periods can visibly differ because EVCC/VM and external portals can use different accounting boundaries. For release and migration validation, the monthly and total view is therefore the relevant view. Concrete local findings and anomalies belong in private notes or local cache files, not in this repository documentation.

## Validation Workflow

Refresh external snapshots locally when needed:

```bash
python3 scripts/helper/compare_tibber_vm.py --start-day YYYY-MM-DD --end-day YYYY-MM-DD --json > data/energy-comparison/tibber/tibber-vm-cost-YYYY-MM-DD_YYYY-MM-DD.json
python3 scripts/helper/fetch_vrm_kwh_cache.py --start-day YYYY-MM-DD --end-day YYYY-MM-DD --site-id <vrm-site-id>
```

Validate the cached snapshots without contacting Tibber or VRM again:

```bash
python3 scripts/helper/validate_energy_comparison.py
```

By default the validator excludes documented anomaly months as maintained in the script. Use repeated `--exclude-month YYYY-MM` arguments for additional documented anomalies.

For private validation with an available VRM cache, require the battery-efficiency check explicitly:

```bash
python3 scripts/helper/validate_energy_comparison.py --require-cache vrm-battery
```

If a disposable or explicitly approved VictoriaMetrics instance is available, add `--vm-base-url http://127.0.0.1:8428` to compare cached external totals against current VM rollups as well. Never write to or delete from a production VictoriaMetrics instance.
