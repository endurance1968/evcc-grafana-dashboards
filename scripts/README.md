# Script Tooling

The default aggregation path in this repository is now the VictoriaMetrics rollup CLI in this directory.

Current default files:

- `evcc-vm-rollup.py`
- `evcc-vm-rollup.conf.example`

Legacy Influx aggregation remains separate under `scripts/influx-legacy/`.

## VictoriaMetrics Rollup Tooling

This directory contains the safe first implementation for EVCC rollups on VictoriaMetrics.

The tool keeps the raw EVCC metrics untouched:

- no writes unless `--write` is passed explicitly
- no raw metric changes
- no dashboard rewiring

It answers these questions first:

- which EVCC dimensions exist in the current VM dataset
- which daily rollups should exist
- which rollup metrics can be generated safely
- how should `vmalert` rules look for advanced users
- how fast are representative raw-data queries today
- what would a test backfill into `test_evcc_*` look like

## Commands

### Detect current dimensions

```bash
python3 evcc-vm-rollup.py --config evcc-vm-rollup.conf.example detect
```

This reads the current VictoriaMetrics dataset and prints the discovered:

- loadpoints
- vehicles
- ext titles
- aux titles

### Show the rollup plan

```bash
python3 evcc-vm-rollup.py --config evcc-vm-rollup.conf.example plan
```

This prints:

- implemented daily rollups
- deferred phase-2 rollups
- the metric namespace that would be used

### Render advanced `vmalert` rules

```bash
python3 evcc-vm-rollup.py --config evcc-vm-rollup.conf.example render-vmalert-rules
```

This produces a `vmalert` rule file for the currently implemented daily rollups.

This is the advanced path, not the default end-user path.

### Benchmark representative raw-data queries

```bash
python3 evcc-vm-rollup.py --config evcc-vm-rollup.conf.example benchmark
```

This runs read-only benchmark queries with `nocache=1` over the configured benchmark range.

### Plan or write a safe test backfill

Dry-run summary only:

```bash
python3 evcc-vm-rollup.py   --config evcc-vm-rollup.conf.example   backfill-test   --start-day 2026-02-20   --end-day 2026-03-22   --progress
```

Actual write to the `test_evcc_*` namespace:

```bash
python3 evcc-vm-rollup.py   --config evcc-vm-rollup.conf.example   backfill-test   --start-day 2026-02-20   --end-day 2026-03-22   --progress   --write
```

Monthly chunking is the default behavior for `backfill-test`.

This means:

- long historical runs emit visible shell progress
- writes happen in bounded monthly chunks instead of one giant final flush
- vehicle odometer state is still preserved across chunk boundaries

Force the previous one-shot behavior only if you really need it:

```bash
python3 evcc-vm-rollup.py   --config evcc-vm-rollup.conf.example   backfill-test   --start-day 2025-01-01   --end-day 2026-03-21   --chunk-by all   --progress   --write
```

The tool computes each local day separately, evaluates the raw MetricsQL expression at local day-end and writes the resulting daily samples via `/api/v1/import`.

## Configuration

The example config uses INI format so it works with Python standard library only.

Key settings:

- `base_url`
- `db_label`
- `host_label`
- `timezone`
- `metric_prefix`
- benchmark start and end range

For the full operator-facing workflow, installation steps, and cron examples, see `docs/victoriametrics-aggregation-guide.md`.

## Safety model

The generated metric names should start with a test namespace, for example:

- `test_evcc_pv_energy_daily_wh`
- `test_evcc_vehicle_energy_daily_wh`

Only after a successful dashboard and performance test should these names move to production names such as:

- `evcc_pv_energy_daily_wh`

The first write target should stay on the same VictoriaMetrics server, but under the test namespace. That keeps the raw data untouched and makes rollback trivial.

## Current scope

Implemented in the catalog:

- PV daily energy
- home daily energy
- loadpoint daily energy
- vehicle daily energy
- vehicle daily distance
- ext daily energy
- aux daily energy
- battery min and max SOC per day

Deferred to phase 2:

- grid import and export split
- battery charge and discharge split
- tariff and finance rollups
