# Migrate From InfluxDB To VictoriaMetrics

Before running commands, review the central requirements overview: [system-requirements.md](./system-requirements.md).

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

If VictoriaMetrics or Grafana is not installed yet, start at [docs/en/README.md](../README_EN.md).

## Recommended Order To Minimize Data Gaps

The simple and safe sequence is:

1. Install VictoriaMetrics.
2. Prepare EVCC/Telegraf according to [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md), but keep the VictoriaMetrics output disabled.
3. During the migration, EVCC continues to write to InfluxDB as before.
4. Import history from InfluxDB to VictoriaMetrics.
5. Build rollups for the imported history.
6. Shortly before cutover, run a final delta import for the last InfluxDB data.
7. If the delta import contains newly completed days, refresh those rollups with `--replace-range --write`.
8. Then enable the VictoriaMetrics output in Telegraf and verify current data.

This avoids two common problems: a long data gap between import and live operation, or duplicate data because the same time range was imported and written live at the same time.

## 1. Download The Migration Files

Create a working directory:

```bash
mkdir -p /opt/evcc-vm-tools
cd /opt/evcc-vm-tools
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

If you intentionally download from a self-hosted raw endpoint, use the repository root raw URL pattern:

```bash
BASE="http://<server:port>/<reponame>/raw/branch/main"
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
- During transition, EVCC should continue to write to InfluxDB. If Telegraf is already prepared, keep the VictoriaMetrics output disabled until cutover.
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

If the output says `GO FOR IT`, rerun the same command only with the recommended write flags printed by the tool. A normal clean run should not need `--merge-target`:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --reset-cache \
  --write
```

Do not add `--merge-target` manually. The tool now stops if a target delete would also match existing hostless sibling series, for example PV string or battery detail series with `id` and `title` labels that are used by the detail dashboards.

After the cleanup, rerun the raw import validation from step 4 against the same closed window. Continue only if `compare_import_coverage.py` still reports `OK FOR REPO` and `check_data.py --phase raw` no longer reports host-tagged series.

If the recommendation is `REVIEW` or `STOP`, use [migration-troubleshooting.md](./migration-troubleshooting.md). Do not build rollups on top of a partially cleaned raw import.

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
# Former EXT titles continued under the same Consumer title. Default `^$`: no mapping.
consumer_legacy_ext_regex = ^$
# Optional JSON aliases for renamed Consumer titles. Default `{}`: no aliases.
consumer_title_aliases_json = {}
max_fetch_points_per_series = 28000
```

Keep `metric_prefix = evcc`. The dashboards expect production rollups such as `evcc_pv_energy_daily_wh`.

### Continue Historical EXT Consumers As Consumer

When an end consumer previously ran as `ext` and is now configured as `consumer` with the same EVCC `title`, list only those titles in `consumer_legacy_ext_regex`:

```ini
consumer_legacy_ext_regex = ^(Dishwasher|Washing Machine)$
```

The rollup then continues legacy EXT power and current Consumer power under `evcc_consumer_energy_daily_wh`. Consumer wins per sampling interval during overlap, and the mapped title is excluded from `evcc_ext_energy_daily_wh` at the same time. Never include distribution or sum meters in this regex.

When a Consumer title was corrected or renamed, `consumer_title_aliases_json` can merge old and current spellings before daily integration. Example: `{"Dryr":"Dryer"}`. The current target title wins during temporal overlap. Recalculate the complete affected range after a title rename as well.

After a role change, recalculate the complete affected period. Use `--replace-range --write` only when the target VM contains complete raw history for every affected day and every metric family being rebuilt. The option deletes existing rollup series in the range before recalculation; missing historical raw data would therefore destroy rollups that cannot be reconstructed.

If a disposable copy or partial migration contains historical rollups but only recent raw data, run neither `--replace-range` nor a full additive backfill across the complete history. A full additive backfill can write the same logical day at a second timestamp and therefore double monthly or yearly totals. In this special case, generate only the missing Consumer series in an isolated disposable VM, or transform the specifically mapped legacy EXT rollup series with an unambiguous day-level cutover. Import only those Consumer series into the target copy. Finally, run `check_data.py --phase full` and require at most one sample per label set and local day. A scheduler run for yesterday alone cannot reclassify older EXT history.

## 7. Inspect The Rollup Plan

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

Expected result:

- `detect` finds your loadpoints, vehicles, Consumer, EXT, and AUX titles plus EXT titles mapped as historical Consumers.
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

/usr/bin/python3 /opt/evcc-vm-tools/evcc-vm-rollup.py \
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

## 11. Run The Final Delta Import And Enable Live Ingest

After import, cleanup, rollups, and scheduling, switch over the current data path.

If EVCC/Telegraf has not been prepared yet, do that now:

- [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md)

Then run a final delta import. Use the time directly after your first import end as the start time and a deliberate cutover time as the end time.

Example without InfluxDB authentication:

```bash
vmctl influx \
  -s \
  --disable-progress-bar \
  --influx-addr='http://<influx-host>:8086' \
  --influx-database='evcc' \
  --influx-filter-time-start='2026-03-31T00:00:00Z' \
  --influx-filter-time-end='2026-06-01T12:00:00Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

If the final delta import contains completed local days that were not covered by the initial backfill, refresh those rollups before dashboard deployment:

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2026-03-31 \
  --end-day 2026-05-31 \
  --replace-range \
  --write
```

Use only a completed local day as `--end-day`, normally yesterday. Today is handled later by the daily scheduler once the day is complete.

If you do not want to risk even a few seconds of missing data, use a short maintenance window: stop EVCC briefly, run the final delta import, refresh rollups for completed days if needed, enable the VictoriaMetrics output in Telegraf, start Telegraf, and start EVCC again.

After that, enable the prepared VictoriaMetrics write path in [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md) and verify that current raw data arrives in VictoriaMetrics. Continue with Grafana and dashboard deployment only after that.

## Quick Completion Check

Use [migration-checklist.md](./migration-checklist.md) before removing InfluxDB from the active dashboard path.
