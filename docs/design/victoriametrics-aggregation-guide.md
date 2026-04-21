# VictoriaMetrics Aggregation Guide

This guide describes the default rollup workflow for long-range EVCC dashboards on VictoriaMetrics.

It assumes the current repository layout:

- VM is the default path
- the old Influx dashboards are retained only as static German reference JSON under `dashboards/influx-legacy/original/de`

## Purpose

Use the rollup CLI to prepare daily rollup metrics for:

- `Monat`
- `Jahr`
- `All-time`

Do not use it for the `Today*` dashboards. Those continue to read raw VM metrics.

## Files

- script: `scripts/rollup/evcc-vm-rollup.py`
- example config: `scripts/rollup/evcc-vm-rollup.conf.example`
- design baseline: `docs/design/victoriametrics-rollup-design.md`

## Current rollout scope

Implemented:

- PV daily energy
- home daily energy
- loadpoint daily energy
- vehicle daily energy
- vehicle daily distance
- ext daily energy
- aux daily energy
- battery min and max SOC per day
- grid import/export split
- battery charge/discharge split
- tariff and finance rollups required by the current dashboards

Still optional later:

- monthly rollups

## Installation

Run the tool on any Linux host with:

- Python 3.11 or newer
- HTTP access to VictoriaMetrics

The tool does not need to run on the VictoriaMetrics host itself.

## Configuration

Start from:

```bash
cp scripts/rollup/evcc-vm-rollup.conf.example /etc/evcc-vm-rollup.conf
```

Important settings:

- `base_url`
- one VictoriaMetrics instance is dedicated to one EVCC instance
- `timezone`
- `metric_prefix`: use `evcc`
- `max_fetch_points_per_series`

Important rule:

- do not build the workflow around `host`
- history and live data may differ on infrastructure labels
- this repository assumes no synthetic `db` label
- if you operate multiple EVCC instances, run multiple VictoriaMetrics instances

## First run

### 1. Detect dimensions

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

### 2. Inspect the rollup plan

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

### 3. Benchmark the raw baseline

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

## Backfill

### Dry run

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress
```

### Actual write

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress --write
```

### Default long-range behavior

`backfill` flushes by month by default.

That means:

- long runs show visible progress in the shell
- memory usage stays bounded
- partial reruns are easier to reason about
- the vehicle odometer state is carried across month boundaries

### Chunking

The current implementation processes and flushes backfills month by month.

Use the normal backfill command:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2025-01-01 --end-day 2026-03-21 --progress --write
```

### Safety rules

- write only `evcc_*` rollups
- never overwrite raw metrics
- `backfill --write` writes completed local days only; today and future days are rejected unless the current day is explicitly allowed for diagnostics
- validate dashboards after major rollup changes

## Production rollout

1. Backfill the required production range.
2. Move `Monat`, `Jahr`, and `All-time` dashboards to the production rollup metrics.
3. Keep `Today*` dashboards on raw metrics.

## Recommended scheduler setup

Rollups are daily values. Schedule the refresh once per day after `yesterday` is complete. For production, prefer `--replace-range`: delete the monthly rollup scope that contains `yesterday`, then rebuild that month up to `yesterday`. This makes the refresh idempotent and avoids duplicate samples with the same series labels and timestamp in VictoriaMetrics.

Example cron:

```cron
5 5 * * * /usr/bin/python3 /opt/evcc-grafana-dashboards/scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day $(date -d 'yesterday' +\%Y-\%m-01) --end-day $(date -d 'yesterday' +\%F) --replace-range --write >> /var/log/evcc-vm-rollup.log 2>&1
```

Manual delete dry-run for a monthly rollup scope:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf delete --start-day 2026-04-01 --end-day 2026-04-30
```

Add `--write` only after the matcher and series counts look correct.

## Validation

After each write phase:

1. Query the new `evcc_*` metrics directly in VictoriaMetrics.
2. Open the corresponding Grafana dashboards.
3. Compare representative periods against the legacy Influx reference dashboards.
4. Capture screenshots if the dashboard set changed visibly.

## Troubleshooting

If dashboards show duplicate series:

- check for unstable infrastructure labels such as `host`
- verify that the rollup design keeps only business labels
- confirm that dashboard queries aggregate away non-business labels where needed

If a long-range dashboard still feels slow:

- verify it actually reads rollup metrics
- benchmark the candidate raw and rollup queries again
- do not add monthly rollups until a real measured bottleneck exists

## Legacy note

The old Influx dashboard set is retained only as static German reference JSON under `dashboards/influx-legacy/original/de`.

