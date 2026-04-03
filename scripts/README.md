# Script Tooling

The `scripts` directory is split into these areas:

- root: installer entry points
- `rollup/`: VictoriaMetrics rollup tooling used for regular operation
- `localization/`: translation generation and audit helpers
- `helper/`: migration and helper scripts that are not part of the normal end-user path
- `test/`: Grafana import, smoke-check, and screenshot tooling

## Rollup tooling

Current rollup files:

- `rollup/evcc-vm-rollup.py`
- `rollup/evcc-vm-rollup.conf.example`
- `rollup/evcc-vm-rollup-prod.conf.example`
- `helper/check_data.py`
- `helper/compare_labelsets.py`
- `helper/vm-rewrite-drop-label.py`

The tool keeps the raw EVCC metrics untouched:

- no writes unless `--write` is passed explicitly
- no raw metric changes from the rollup engine
- no dashboard rewiring

## Main commands

Detect dimensions:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example detect
```

Show the rollup plan:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example plan
```

Benchmark representative raw-data queries:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example benchmark
```

Dry-run backfill:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress
```

Write `evcc_*` rollups:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example backfill --start-day 2025-01-01 --end-day 2026-03-27 --progress --write
```

## VM cleanup and validation helpers

Rewrite host-tagged VM-only series:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://192.168.1.160:8428 --matcher '{db="evcc",host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Recommended write mode after a successful dry-run:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://192.168.1.160:8428 --matcher '{db="evcc",host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl --merge-target --reset-cache --write
```

Check whether raw EVCC metrics and expected daily rollups exist after import/backfill:

```bash
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --db evcc

# historical import or benchmark VM
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --db evcc --end-time 2026-03-31T23:59:59Z
```

Compare labelsets between two import states or benchmark exports:

```bash
python3 scripts/helper/compare_labelsets.py --left-json /tmp/before-cleanup/target-stats.json --left-name before --right-json /tmp/after-cleanup/target-stats.json --right-name after

# only one metric
python3 scripts/helper/compare_labelsets.py --left-json /tmp/before-cleanup/target-stats.json --left-name before --right-json /tmp/after-cleanup/target-stats.json --right-name after --metric-regex '^pvPower_value$'
```

## Configuration

The example config uses INI format so it works with Python standard library only.

Key settings:

- `base_url`
- `db_label`
- `host_label`
- `timezone`
- `metric_prefix`
- benchmark start and end range

For the operator-facing workflow, installation steps, and cron examples, see `docs/design/victoriametrics-aggregation-guide.md`.

## Safety model

Rollups are written to the `evcc_*` namespace. Raw EVCC metrics remain untouched.

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
- grid import and export split
- battery charge and discharge split
- import price and cost rollups
- export credit rollups

Daily rollups carry `local_year` and `local_month` labels so month/year dashboards can filter on local calendar periods without repeating large timezone guard expressions in every query.

Still deferred beyond the current baseline:

- any optional monthly rollup layer

## End-user install

For end users, prefer:

- `scripts/deploy.ps1`
- `scripts/deploy-python.sh`
- `docs/vm-dashboard-install.md`

