# Energy comparison data

Local third-party energy comparison data lives here. The data is intentionally outside `tmp/` because it is reused for migration and rollup validation.

- `tibber/`: local Tibber API exports or comparison snapshots.
- `vrm/`: local Victron VRM daily kWh cache files.

The actual cache/export files are machine-local and ignored by Git. Keep only this documentation and `.gitkeep` files tracked.
