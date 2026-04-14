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
- `helper/compare_import_coverage.py`
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

Run the disposable rollup end-to-end test before changing the rollup write/delete path:

```bash
python3 scripts/test/rollup-e2e.py --docker
```

The test imports a tiny raw fixture into an isolated VictoriaMetrics, runs `backfill --replace-range --write` twice, and verifies that repeated replacement does not leave duplicate daily rollup samples. If Docker is not available, use a local disposable VM only:

```bash
python3 scripts/test/rollup-e2e.py --base-url http://127.0.0.1:8428 --confirm-disposable
```

Replace a monthly rollup scope before writing it again:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example backfill --start-day 2026-04-01 --end-day 2026-04-10 --replace-range --progress --write
```

Delete a monthly rollup scope without rebuilding it:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example delete --start-day 2026-04-01 --end-day 2026-04-30
```

## VM cleanup and validation helpers

Check whether raw EVCC metrics and expected daily rollups exist after import/backfill. In the default `auto` phase the script checks raw data first, then automatically includes rollups once they exist. It also reports whether `host` cleanup is recommended:

```bash
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428

# explicit raw-import phase
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --phase raw

# historical import or benchmark VM
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --phase raw --end-time 2026-03-31T23:59:59Z
```

Compare Influx source coverage against the imported VM raw metrics right after `vmctl`. The default run now checks the full Influx measurement set, but splits the result into `repo-relevant` and `additional` groups so the conclusion clearly shows whether the active dashboard schema is blocked or only extra EVCC metadata families are affected:

```bash
python3 scripts/helper/compare_import_coverage.py --influx-url http://127.0.0.1:8086 --influx-db evcc --vm-base-url http://127.0.0.1:8428 --start 2026-03-21T00:00:00Z --end 2026-04-03T23:59:59Z --only-problems

# optional: limit the check to repo-relevant measurements only
python3 scripts/helper/compare_import_coverage.py --influx-url http://127.0.0.1:8086 --influx-db evcc --vm-base-url http://127.0.0.1:8428 --start 2026-03-21T00:00:00Z --end 2026-04-03T23:59:59Z --only-problems --repo-relevant-only
```

Additional findings now include a short `Hint` so you can see whether they are likely string/boolean metadata or a real extra import gap.

Only if the coverage check and the data check look good, rewrite host-tagged VM-only series:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://192.168.1.160:8428 --matcher '{host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

The dry-run now prints a `Recommendation` section with a clear status (`GO FOR IT`, `REVIEW`, or `STOP`) and the exact write flags to append next. A clean run looks like this:

```text
GO FOR IT: Dry-run is clean. You can continue with the write step.
Recommended write flags:
  --merge-target \
  --reset-cache \
  --write
```

In that clean case, rerun the same command with those flags appended:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://192.168.1.160:8428 --matcher '{host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl --merge-target --reset-cache --write
```

If the recommendation mentions conflicts, follow the printed conflict-safe flag set instead, for example `--keep-target-values-on-conflict`.

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
- `host_label`
- `timezone`
- `metric_prefix`
- benchmark start and end range

The repo assumes one VictoriaMetrics instance per EVCC instance. If you run multiple EVCC instances, run multiple VictoriaMetrics instances as well instead of multiplexing them via a shared `db` label.

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
