# Energy comparison data

Local third-party energy comparison data lives here. The data is intentionally outside `tmp/` because it is reused for migration and rollup validation.

- `tibber/`: local Tibber API exports or comparison snapshots.
- `vrm/`: local Victron VRM daily kWh cache files.

The actual cache/export files are machine-local and ignored by Git. Keep only this documentation and `.gitkeep` files tracked.

## Battery efficiency

The dashboard value `Battery efficiency` is an energy-flow ratio, not a manufacturer statement about cell or inverter efficiency:

```text
Battery efficiency = battery discharge / battery charge * 100
```

In VictoriaMetrics the dashboard uses `evcc_battery_discharge_daily_wh` and `evcc_battery_charge_daily_wh`. The VRM comparison uses the closest matching VRM flows:

```text
VRM battery charge    = pv_to_battery_kwh + grid_to_battery_kwh
VRM battery discharge = battery_to_consumers_kwh + battery_to_grid_kwh
```

Short periods can visibly differ because EVCC/VM and VRM use different accounting boundaries. For release and migration validation, the monthly and total view is therefore the relevant view.

Current local VRM cache check with Ole's data after the default exclusions `2025-04` and `2025-10`: `2025-07..2026-03`, 243 days, 5102.02 kWh battery charge, 4604.82 kWh battery discharge, total efficiency `90.25%`. The monthly value `2025-08` is above 100% at `105.73%`; this is not automatically treated as a rollup error because VRM flow groups and EVCC/VM battery power can use different accounting boundaries. Such differences must be interpreted in the monthly/total view or investigated further against a live VM with `--vm-base-url`.

## Validation workflow

Refresh external snapshots when needed:

```bash
python3 scripts/helper/compare_tibber_vm.py --start-day 2025-04-01 --end-day 2026-03-31 --json > data/energy-comparison/tibber/tibber-vm-cost-2025-04-01_2026-03-31.json
python3 scripts/helper/fetch_vrm_kwh_cache.py --start-day 2025-07-01 --end-day 2026-03-31
```

Validate the cached snapshots without contacting Tibber or VRM again:

```bash
python3 scripts/helper/validate_energy_comparison.py
```

By default the validator excludes `2025-04` and `2025-10`, because those months are documented Tibber/EVCC/import anomalies. Use repeated `--exclude-month YYYY-MM` arguments for additional documented anomalies.

For private validation with an available VRM cache, require the battery-efficiency check explicitly:

```bash
python3 scripts/helper/validate_energy_comparison.py --require-cache vrm-battery
```

If a live VictoriaMetrics instance is available, add `--vm-base-url http://127.0.0.1:8428` to compare cached VRM PV/grid-import totals and battery-flow efficiency against the current VM rollups as well.
