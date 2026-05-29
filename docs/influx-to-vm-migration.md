# Migrate From InfluxDB To VictoriaMetrics

This is the normal end-user path from an existing EVCC + InfluxDB setup to VictoriaMetrics.

This guide intentionally covers only the green path. If a check fails, continue with [migration-troubleshooting.md](./migration-troubleshooting.md). For release and energy-calibration background, see [migration-validation-notes.md](./migration-validation-notes.md).

## Target State

After migration, VictoriaMetrics contains two data layers:

- raw EVCC metrics, used by `Today`, `Today - Mobile`, and `Today - Details`
- daily `evcc_*` rollups, used by `Month`, `Year`, and `All-time`

The rollup engine does not overwrite raw EVCC metrics. It writes additional daily metrics in the `evcc_*` namespace.

## Assumptions

- VictoriaMetrics is installed and reachable.
- `vmctl` is installed.
- You can reach the InfluxDB v1 query API.
- Python 3.11 or newer is available.
- One VictoriaMetrics instance is dedicated to one EVCC instance.

If VictoriaMetrics or Grafana is not installed yet, start at [docs/README.md](./README.md).

## 1. Download The Migration Files

Create a working directory:

```bash
mkdir -p /opt/evcc-vm-migration
cd /opt/evcc-vm-migration
```

Download the scripts:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"

curl -fsSLo evcc-vm-rollup.py "$BASE/scripts/rollup/evcc-vm-rollup.py"
curl -fsSLo evcc-vm-rollup-prod.conf.example "$BASE/scripts/rollup/evcc-vm-rollup-prod.conf.example"
curl -fsSLo check_data.py "$BASE/scripts/helper/check_data.py"
curl -fsSLo compare_import_coverage.py "$BASE/scripts/helper/compare_import_coverage.py"
curl -fsSLo vm-rewrite-drop-label.py "$BASE/scripts/helper/vm-rewrite-drop-label.py"
```

If you intentionally download from the local Forgejo mirror used for this project, use the port-forward address:

```bash
BASE="http://192.168.1.222:3000/olaf-krause/evcc-grafana-dashboards/raw/branch/main"
```

If you run the commands from a repository checkout instead of this working directory, use the repository paths, for example `scripts/helper/check_data.py` and `scripts/rollup/evcc-vm-rollup.py`.

## 2. Verify VictoriaMetrics

```bash
curl -fsSL http://localhost:8428/health
```

Expected result:

```text
OK
```

Replace `localhost` with your VictoriaMetrics host when the command runs from another machine.

## 3. Import Raw Data From InfluxDB

Use `vmctl influx`. This keeps EVCC business labels such as `loadpoint`, `vehicle`, `id`, and `title` intact.

Without InfluxDB authentication:

```bash
vmctl influx \
  -s \
  --disable-progress-bar \
  --influx-addr='http://<influx-host>:8086' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

With InfluxDB authentication:

```bash
vmctl influx \
  -s \
  --disable-progress-bar \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

Important:

- Keep `--influx-skip-database-label` for this repository's default model.
- Do not use a synthetic `db` label to multiplex multiple EVCC instances into one VictoriaMetrics instance.
- During transition, EVCC may still write to InfluxDB in parallel.
- `-s --disable-progress-bar` makes the import non-interactive and also works when `vmctl` runs in Docker or another non-TTY environment.
- If `vmctl` runs in a Docker container on Docker Desktop while InfluxDB or VictoriaMetrics are published on the host, use `host.docker.internal` in `--influx-addr` and `--vm-addr`.

## 4. Validate The Raw Import

Run the VM-only checker:

```bash
python3 check_data.py --base-url http://localhost:8428 --phase raw
```

For a historical migration range, anchor the check near your imported end date:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --phase raw \
  --end-time 2026-03-30T23:59:59Z
```

Then compare Influx source coverage against VictoriaMetrics:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Use a closed comparison window. If EVCC still writes to InfluxDB while you run the import, do not compare against the moving current hour. Use completed days, for example yesterday as `--end`, or the exact import snapshot end. Otherwise the checker can correctly report `TRUNCATED` because InfluxDB has newer samples than the finished VictoriaMetrics import.

Expected result:

- `Repo-relevant problems: 0`
- `Critical energy problems: 0`
- final status `OK FOR REPO`

If the check reports missing or drifting data, stop and use [migration-troubleshooting.md](./migration-troubleshooting.md) before building rollups.

## 5. Clean Up `host` Only If The Checker Recommends It

The raw import may contain infrastructure labels such as `host`. Keep EVCC business labels, but remove `host` when `check_data.py` reports host-tagged series.

Dry-run first:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

On a full real EVCC history this dry-run can take several minutes because it checks the target series for conflicts before writing. Let it finish and follow the recommendation from the tool output.

If the output says `GO FOR IT`, rerun the same command with the recommended write flags printed by the tool, usually:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --reset-cache \
  --write
```

If the recommendation is `REVIEW` or `STOP`, use [migration-troubleshooting.md](./migration-troubleshooting.md).

## 6. Create The Rollup Config

```bash
sudo cp evcc-vm-rollup-prod.conf.example /etc/evcc-vm-rollup.conf
sudo editor /etc/evcc-vm-rollup.conf
```

On Windows, keep the config in your working directory and pass that path with `--config`, for example `--config .\evcc-vm-rollup.conf`.

Recommended production core:

```ini
[victoriametrics]
base_url = http://localhost:8428
host_label =
timezone = Europe/Berlin
metric_prefix = evcc
raw_sample_step = 10s
energy_rollup_step = 60s
price_bucket_minutes = 15
max_fetch_points_per_series = 28000
```

Keep `metric_prefix = evcc`. The dashboards expect production rollups such as `evcc_pv_energy_daily_wh`.

## 7. Inspect The Rollup Plan

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

Expected result:

- `detect` finds your loadpoints, vehicles, and optional EXT/AUX titles.
- `plan` lists the `evcc_*` daily rollups to be created.
- `benchmark` can query representative raw data without timeouts.

## 8. Run The Initial Backfill

Dry-run first:

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress
```

Then write completed days only:

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress \
  --write
```

Use yesterday as `--end-day` for a live system. The write path rejects today and future local days by default.

## 9. Verify Rollups

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Then run the checker again without forcing `--phase raw`:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --end-time 2026-03-30T23:59:59Z
```

Expected result: raw checks and rollup checks are both OK.

## 10. Schedule The Daily Refresh

Create `/usr/local/bin/evcc-vm-rollup-daily.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day "$(date -d 'yesterday' +%Y-%m-01)" \
  --end-day "$(date -d 'yesterday' +%F)" \
  --replace-range \
  --write
```

Then:

```bash
sudo chmod +x /usr/local/bin/evcc-vm-rollup-daily.sh
sudo crontab -e
```

Add:

```cron
5 5 * * * /usr/local/bin/evcc-vm-rollup-daily.sh >> /var/log/evcc-vm-rollup.log 2>&1
```

Run the refresh only once per day after the previous local day is complete.

## 11. Deploy Grafana Dashboards

Continue with [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).

## Quick Completion Check

Use [migration-checklist.md](./migration-checklist.md) before removing InfluxDB from the active dashboard path.
