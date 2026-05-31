# Energy comparison data

Local third-party energy comparison data lives here. The data is intentionally outside `tmp/` because it is reused for migration and rollup validation.

- `tibber/`: local Tibber API exports or comparison snapshots.
- `vrm/`: local Victron VRM daily kWh cache files.

The actual cache/export files are machine-local and ignored by Git. Keep only this documentation and `.gitkeep` files tracked.

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

By default the validator excludes `2025-10`, because the current migration notes document incomplete VM grid import/cost rollups for that month. Use repeated `--exclude-month YYYY-MM` arguments for additional documented anomalies, for example April investigations.

If a live VictoriaMetrics instance is available, add `--vm-base-url http://127.0.0.1:8428` to compare cached VRM PV/grid-import totals against the current VM rollups as well.
