# Migrate from InfluxDB to VictoriaMetrics

This guide describes the recommended end-user path from an existing EVCC + InfluxDB setup to VictoriaMetrics.

Assumptions:

- VictoriaMetrics is already installed and reachable
- `vmctl` is installed
- EVCC already writes to VictoriaMetrics, or will do so after the migration

Not covered here:

- installing VictoriaMetrics itself
- installing Grafana itself
- deploying the Grafana dashboards

## Target state

After migration, there are two data layers:

- raw data in VictoriaMetrics
  - used by `Today`, `Today - Mobile`, and `Today - Details`
- daily rollups in the `evcc_*` namespace
  - used by `Month`, `Year`, and `All-time`

Important:

- raw data is not overwritten by the rollup engine
- rollups are added on top
- the `Today*` dashboards continue to use raw data

## What you need

- Python 3.11 or newer
- HTTP access to the InfluxDB v1 query API
- HTTP access to VictoriaMetrics
- `vmctl`

Practical minimum on Linux:

```bash
sudo apt update
sudo apt install -y python3 curl
```

For Debian 13, see also:

- [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)

## Download the required files

Create a working directory:

```bash
mkdir -p /opt/evcc-vm-migration
cd /opt/evcc-vm-migration
```

Download the required files:

```bash
curl -fsSLo evcc-vm-rollup.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.py
curl -fsSLo evcc-vm-rollup-prod.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup-prod.conf.example
curl -fsSLo evcc-vm-rollup.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.conf.example
curl -fsSLo check_data.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/check_data.py
curl -fsSLo vm-rewrite-drop-label.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/vm-rewrite-drop-label.py
```

Optional analysis helper:

```bash
curl -fsSLo compare_labelsets.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/compare_labelsets.py
```

## Files used in this migration

- raw-data import:
  - `vmctl`
- health and presence checks:
  - `check_data.py`
- safe first cleanup step:
  - `vm-rewrite-drop-label.py`
- rollup engine:
  - `evcc-vm-rollup.py`
- production rollup config:
  - `evcc-vm-rollup-prod.conf.example`

## 1. Check VictoriaMetrics and EVCC first

Before moving data, verify:

- VictoriaMetrics responds:

```bash
curl -fsSL http://<vm-host>:8428/health
```

- Grafana will later point to VictoriaMetrics
- EVCC should ultimately write to VictoriaMetrics as well

If EVCC still writes to InfluxDB in parallel during the transition, that is fine for a temporary migration window.

## 2. Import raw data from InfluxDB into VictoriaMetrics

For raw-data migration, use `vmctl influx`.

Why this is the preferred path in this repository now:

- it preserves the InfluxDB tag structure much more faithfully than the older normalized import path
- it keeps business dimensions such as `loadpoint`, `vehicle`, `id`, and `title`
- this gives you the best raw-data fidelity before any cleanup or normalization step

### 2.1 Run the import

Example:

```bash
yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --vm-addr='http://<vm-host>:8428'
```

If your InfluxDB requires auth:

```bash
yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --vm-addr='http://<vm-host>:8428'
```

Notes:

- `vmctl` adds `db="evcc"` from the selected Influx database
- the imported raw model can include labels such as `loadpoint`, `vehicle`, `id`, `title`, and sometimes `host`
- that richer label model is expected and is the basis for the cleanup step below

### 2.2 Verify the raw data directly

Query VictoriaMetrics directly:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

You should also inspect a few labelsets:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

### 2.3 Run the repository data check

Use the VM-only checker after the import. In the default `auto` phase it validates raw data first and only checks rollups once they exist. It also reports whether `host`-tagged series are present and should be normalized away.

For a current production VM:

```bash
python3 check_data.py --base-url http://<vm-host>:8428 --db evcc

# explicit raw-import phase
python3 check_data.py --base-url http://<vm-host>:8428 --db evcc --phase raw
```

For a historical benchmark or migration VM, anchor the logical check point to the imported range:

```bash
python3 check_data.py \
  --base-url http://<vm-host>:8428 \
  --db evcc \
  --end-time 2026-03-30T23:59:59Z
```

## 3. First cleanup step: remove `host`

The first cleanup step should focus on `host` only.

Why `host` is the safest first target:

- it is an infrastructure label, not a business dimension
- it can create duplicate-looking raw series without adding dashboard value
- removing it does not throw away EVCC domain information such as `loadpoint`, `vehicle`, `id`, or `title`

Do **not** blindly drop these labels:

- `loadpoint`
- `vehicle`
- `id`
- `title`

Those labels carry the EVCC semantics that we want to preserve.

### 3.1 Dry-run the rewrite first

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://<vm-host>:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

The dry-run exports the host-tagged source series, removes `host` in memory, and reports:

- how many source series were exported
- whether transformed timestamps overlap existing hostless target series
- whether there are value conflicts

### 3.2 Recommended write mode

If the dry-run looks clean, use merge mode so existing hostless targets are preserved and merged safely:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://<vm-host>:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --reset-cache \
  --write
```

Important:

- start with the dry-run first
- keep the backup JSONL
- only use `--allow-value-conflicts` if you have reviewed the differences and want source values to win explicitly

### 3.3 What to analyze later

After `host` is removed, the remaining candidates for later analysis are labelset subsets, for example:

- `{db,id}` vs. `{db,id,title}`
- `{db,loadpoint}` vs. `{db,loadpoint,vehicle}`

Do not delete those automatically. Compare them first.

Optional helper:

```bash
python3 compare_labelsets.py \
  --left-json /tmp/before-cleanup/target-stats.json \
  --left-name before \
  --right-json /tmp/after-cleanup/target-stats.json \
  --right-name after
```

## 4. Create the rollup configuration

Create the production config from the example:

```bash
sudo cp evcc-vm-rollup-prod.conf.example /etc/evcc-vm-rollup.conf
sudo editor /etc/evcc-vm-rollup.conf
```

Important fields:

- `base_url`
  - URL of your VictoriaMetrics instance
- `db_label`
  - normally `evcc`
- `timezone`
  - for example `Europe/Berlin`
- `metric_prefix`
  - production value `evcc`
- `price_bucket_minutes`
  - usually `15` for dynamic tariffs
- `max_fetch_points_per_series`
  - limits how many raw samples per series are fetched in a single request chunk

Recommended production core:

```ini
[victoriametrics]
base_url = http://<vm-host>:8428
db_label = evcc
host_label =
timezone = Europe/Berlin
metric_prefix = evcc
raw_sample_step = 10s
energy_rollup_step = 60s
price_bucket_minutes = 15
max_fetch_points_per_series = 28000
```

Important:

- `metric_prefix = evcc` creates production rollups such as `evcc_pv_energy_daily_wh`
- keep `host_label` empty unless you have a very good reason not to
- rollups should be based on business labels, not infrastructure labels

## 5. Inspect the rollup before writing

### 5.1 Detect dimensions

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

### 5.2 Show the rollup plan

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

### 5.3 Run the benchmark

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

This is useful because it tells you early:

- whether the raw data can be read at all
- whether query runtimes are acceptable
- whether `max_fetch_points_per_series` fits your hardware

## 6. Run the initial rollup backfill

This creates the daily rollups in the `evcc_*` namespace.

### 6.1 Dry-run first

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress
```

### 6.2 Then run the real write

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress \
  --write
```

Notes:

- the backfill is processed and written month by month
- the script does not keep the full historical range in memory at once
- that keeps memory usage and progress visibility manageable

## 7. Verify the rollups

Example check for a daily PV rollup:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh{db="evcc"}' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Then run the repository checker again:

```bash
python3 check_data.py \
  --base-url http://<vm-host>:8428 \
  --db evcc \
  --end-time 2026-03-30T23:59:59Z
```

## 8. Set up the hourly rollup refresh

### 8.1 Example wrapper script

Create `/usr/local/bin/evcc-vm-rollup-hourly.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day "$(date -d 'yesterday' +%F)" \
  --end-day "$(date +%F)" \
  --write
```

Then:

```bash
sudo chmod +x /usr/local/bin/evcc-vm-rollup-hourly.sh
```

### 8.2 systemd timer example

Service file `/etc/systemd/system/evcc-vm-rollup-hourly.service`:

```ini
[Unit]
Description=EVCC VictoriaMetrics hourly rollup refresh

[Service]
Type=oneshot
ExecStart=/usr/local/bin/evcc-vm-rollup-hourly.sh
```

Timer file `/etc/systemd/system/evcc-vm-rollup-hourly.timer`:

```ini
[Unit]
Description=Run EVCC VictoriaMetrics rollup refresh hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now evcc-vm-rollup-hourly.timer
systemctl list-timers | grep evcc-vm-rollup-hourly
```

### 8.3 Simple cron alternative

```cron
7 * * * * /usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day $(date -d 'yesterday' +\%F) --end-day $(date +\%F) --write >> /var/log/evcc-vm-rollup.log 2>&1
```

## 9. Remove InfluxDB from the active dashboard path

Once you are sure that:

- raw data arrives correctly in VictoriaMetrics
- rollups are running correctly
- the first host cleanup step is complete or consciously postponed

EVCC no longer needs to depend on InfluxDB for dashboarding.

At that point you can:

- keep InfluxDB only as backup or reference
- or later shut it down completely

## Easy things to forget

- Grafana must point to VictoriaMetrics, not InfluxDB
- `Today*` and the long-range dashboards work on different data layers
- `metric_prefix` must be `evcc`, not `test_evcc`
- the raw-data import does not replace the ongoing rollup process
- the rollup needs a scheduler, or `Month/Year/All-time` will stop updating
- `host` should be treated as infrastructure noise unless you explicitly need it
- if something looks wrong, verify raw data first, then rollups

## Recommendation for this repository

Current recommendation:

- use `vmctl influx` for the raw-data import
- remove `host` as the first cleanup step
- keep business labels such as `loadpoint`, `vehicle`, `id`, and `title`
- only deduplicate subset labelsets later after explicit comparison
- use `check_data.py` after import and after the initial rollup backfill

## Short version

1. verify VictoriaMetrics
2. import raw data with `vmctl influx`
3. verify raw data and run `check_data.py`
4. remove `host` with `vm-rewrite-drop-label.py`
5. create the production rollup config
6. run `detect`, `plan`, and `benchmark`
7. run the initial rollup backfill with `--write`
8. verify the rollups
9. set up the hourly rollup job
10. keep InfluxDB only as fallback or historical reference


