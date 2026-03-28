# VictoriaMetrics Aggregation Guide

This guide describes the default rollup workflow for long-range EVCC dashboards on VictoriaMetrics.

It assumes the current repository layout:

- VM is the default path
- only legacy Influx tooling remains under `influx-legacy`

## Purpose

Use the rollup CLI to prepare daily rollup metrics for:

- `Monat`
- `Jahr`
- `All-time`

Do not use it for the `Today*` dashboards. Those continue to read raw VM metrics.

## Files

- script: `scripts/evcc-vm-rollup.py`
- example config: `scripts/evcc-vm-rollup.conf.example`
- design baseline: `docs/victoriametrics-rollup-design.md`

## Current rollout scope

Implemented in the safe first phase:

- PV daily energy
- home daily energy
- loadpoint daily energy
- vehicle daily energy
- vehicle daily distance
- ext daily energy
- aux daily energy
- battery min and max SOC per day

Deferred to a later phase:

- grid import/export split
- battery charge/discharge split
- tariff and finance rollups
- optional monthly rollups

## Installation

Run the tool on any Linux host with:

- Python 3.11 or newer
- HTTP access to VictoriaMetrics

The tool does not need to run on the VictoriaMetrics host itself and it does not need container access. Network access to the VM HTTP API is enough.

## Configuration

Start from:

```bash
cp scripts/evcc-vm-rollup.conf.example /etc/evcc-vm-rollup.conf
```

Important settings:

- `base_url`: VictoriaMetrics base URL
- `db_label`: stable EVCC history label, currently `evcc`
- `timezone`: local day boundary, currently `Europe/Berlin`
- `metric_prefix`: use `test_evcc` first, switch to `evcc` only after validation

Important rule:

- do not build the workflow around `host`
- history and live data may differ on infrastructure labels

## First run

### 1. Detect dimensions

```bash
python3 scripts/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

This shows the currently detected:

- loadpoints
- vehicles
- ext titles
- aux titles

### 2. Inspect the rollup plan

```bash
python3 scripts/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

Use this to verify:

- generated metric names
- implemented phase-1 rollups
- deferred rollups that are still intentionally out of scope

### 3. Benchmark the raw baseline

```bash
python3 scripts/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

This gives the comparison baseline before any dashboard is moved to rollups.

## Safe test backfill

### Dry run

```bash
python3 scripts/evcc-vm-rollup.py   --config /etc/evcc-vm-rollup.conf   backfill-test   --start-day 2026-02-20   --end-day 2026-03-22   --progress
```

### Actual write into the test namespace

```bash
python3 scripts/evcc-vm-rollup.py   --config /etc/evcc-vm-rollup.conf   backfill-test   --start-day 2026-02-20   --end-day 2026-03-22   --progress   --write
```

### Default long-range behavior

`backfill-test` now flushes by month by default.

That means:

- long runs show visible progress in the shell
- memory usage stays bounded
- partial reruns are easier to reason about
- the vehicle odometer state is still carried across month boundaries

Progress output is written to `stderr`, while the final machine-readable summary remains JSON on `stdout`.

Example progress lines:

```text
[chunk 1/15] start 2025-01 days=31
[chunk 1/15] done 2025-01 days=31/445 samples=... series=... skipped=... batches=...
```

### Optional chunk control

Default:

```bash
python3 scripts/evcc-vm-rollup.py   --config /etc/evcc-vm-rollup.conf   backfill-test   --start-day 2025-01-01   --end-day 2026-03-21   --progress   --write
```

Force one single flush at the end:

```bash
python3 scripts/evcc-vm-rollup.py   --config /etc/evcc-vm-rollup.conf   backfill-test   --start-day 2025-01-01   --end-day 2026-03-21   --chunk-by all   --progress   --write
```

Use monthly chunking unless you have a measured reason not to.

### Safety rules

- start with `test_evcc_*`
- never overwrite raw metrics
- do not switch dashboards to production rollups before Grafana validation
- clear only the `test_evcc_*` namespace when rebuilding test rollups

## Production rollout

Only after the test dashboards are accepted:

1. Change `metric_prefix` from `test_evcc` to `evcc`.
2. Backfill the required production range.
3. Move `Monat`, `Jahr`, and `All-time` dashboards to the production rollup metrics.
4. Keep `Today*` dashboards on raw metrics.

## Recommended scheduler setup

Daily rollups are the accepted baseline, so the regular job should aggregate complete local days.

Example cron:

```cron
10 0 * * * /usr/bin/python3 /opt/evcc-grafana-dashboards/scripts/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill-test --start-day $(date -d 'yesterday' +\%F) --end-day $(date -d 'yesterday' +\%F) --write >> /var/log/evcc-vm-rollup.log 2>&1
```

For long one-shot historical runs, add `--progress` so the shell shows chunk progress while the final JSON summary is still available for logging.

## Validation

After each write phase:

1. Query the new `test_evcc_*` or `evcc_*` metrics directly in VictoriaMetrics.
2. Open the corresponding Grafana test dashboards.
3. Compare representative periods against the legacy Influx dashboards.
4. Capture screenshots if the dashboard family changed visibly.

For large historical backfills, validate at least:

- one month near the beginning of the range
- one month near the end of the range
- vehicle distance panels for all active vehicles
- battery min/max panels

## Troubleshooting

If dashboards show duplicate series:

- check for unstable infrastructure labels such as `host`
- verify that the rollup design keeps only business labels
- confirm that dashboard queries aggregate away non-business labels where needed

If a long-range dashboard still feels slow:

- verify it actually reads rollup metrics
- benchmark the candidate raw and rollup queries again
- do not add monthly rollups until a real measured bottleneck exists

If a metric is missing:

- rerun `detect`
- confirm the raw metric exists for the requested window
- check whether that metric family is still intentionally deferred

If a long run looks stuck:

- rerun with `--progress`
- keep monthly chunking enabled
- check the last reported chunk name to narrow the affected period

## Legacy note

The old Influx aggregation script remains available under `scripts/influx-legacy/`.

Do not model the VM path as a 1:1 clone of that layout unless measured VM behavior later proves the need.
