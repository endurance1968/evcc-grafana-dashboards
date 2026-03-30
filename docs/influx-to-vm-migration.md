# Migrate from InfluxDB to VictoriaMetrics

This guide describes the full end-user path from an existing EVCC + InfluxDB setup to VictoriaMetrics.

Assumptions:

- VictoriaMetrics is already installed and reachable
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

- raw data is not overwritten
- rollups are added on top
- the `Today*` dashboards continue to use raw data

## What you need

- Python 3.11 or newer
- HTTP access to the InfluxDB v1 query API
- HTTP access to VictoriaMetrics

Practical minimum on Linux:

```bash
sudo apt update
sudo apt install -y python3 curl
```

## Download the required files

Create a working directory:

```bash
mkdir -p /opt/evcc-vm-migration
cd /opt/evcc-vm-migration
```

Download the required files:

```bash
curl -fsSLo reimport_influx_to_vm.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/reimport_influx_to_vm.py
curl -fsSLo evcc-vm-rollup.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.py
curl -fsSLo evcc-vm-rollup-prod.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup-prod.conf.example
```

Optional:

```bash
curl -fsSLo evcc-vm-rollup.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.conf.example
```

## Files used in this migration

- raw-data import:
  - `reimport_influx_to_vm.py`
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

The helper imports numeric Influx measurements directly into VictoriaMetrics.

Important:

- the current helper uses the InfluxDB v1 query API
- it expects direct HTTP access
- it does not currently implement built-in auth-header handling
- if your InfluxDB requires auth, use a local proxy/tunnel or extend the script

### 2.1 Dry-run first

Example:

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z \
  --dry-run
```

The dry-run shows:

- how many measurements were found
- how many series and samples would be imported

### 2.2 Run the real import

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z
```

Optional single-measurement import:

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --measurement pvPower \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z
```

### 2.3 Verify the raw data

Query VictoriaMetrics directly:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-02T00:00:00Z'
```

If this returns data, the raw-data layer is in place.

## 3. Create the rollup configuration

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

### Background on `max_fetch_points_per_series`

This is the main tuning knob for the balance between:

- RAM usage
- number of VictoriaMetrics requests
- total rollup runtime

What it does in practice:

- the rollup process does not fetch arbitrarily large time ranges in one request
- instead, large periods are split into smaller fetch chunks
- `max_fetch_points_per_series` defines the upper bound per series per fetch

If the value is **larger**:

- fewer HTTP requests are needed
- the run is often faster
- but more samples sit in memory at the same time

If the value is **smaller**:

- more fetches are required
- the run becomes slower
- but memory usage drops

Rule of thumb:

- stronger hosts:
  - keep it higher
- smaller systems such as a Raspberry Pi:
  - reduce it gradually if you hit RAM limits

The default `28000` is a pragmatic compromise:

- high enough for good runtime
- low enough to avoid unnecessary memory pressure

Only change it if you have a real reason:

- OOM or RAM pressure
- unusually slow backfills
- very long raw-data history on weak hardware

If you experiment, do it in small steps, for example:

- `28000`
- `20000`
- `15000`

Then measure runtime and peak RAM again.

## 4. Inspect the rollup before writing

### 4.1 Detect dimensions

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

### 4.2 Show the rollup plan

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

### 4.3 Run the benchmark

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

This is useful because it tells you early:

- whether the raw data can be read at all
- whether query runtimes are acceptable
- whether `max_fetch_points_per_series` fits your hardware

## 5. Run the initial rollup backfill

This creates the daily rollups in the `evcc_*` namespace.

### 5.1 Dry-run first

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress
```

### 5.2 Then run the real write

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress \
  --write
```

Notes:

- the backfill is processed and written month by month
- January is handled as one block, then February, then March, and so on
- the script does not keep the full historical range in memory at once
- that keeps memory usage and progress visibility manageable
- the run writes only `evcc_*`
- raw data remains untouched

## 6. Verify the rollups

After the initial backfill, check directly:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/query' \
  --data-urlencode 'query=sum(evcc_pv_energy_daily_wh{db="evcc"})'
```

Also recommended:

- compare against a known time range
- compare with previous Influx-based expectations if needed

## 7. Set up the ongoing rollup refresh

The rollups are daily metrics. To keep the current day up to date, you should recalculate the current day regularly.

Recommendation:

- rerun **yesterday + today** every hour

Why not just `today`:

- some raw samples arrive a little late
- midnight and timezone transitions are more robust
- small late corrections from the previous day are captured automatically

### 7.1 Manual hourly refresh

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day $(date -d 'yesterday' +%F) \
  --end-day $(date +%F) \
  --write
```

### 7.2 Recommended `systemd` setup

Wrapper script `/usr/local/bin/evcc-vm-rollup-hourly.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day "$(date -d 'yesterday' +%F)" \
  --end-day "$(date +%F)" \
  --write
```

Make it executable:

```bash
sudo chmod +x /usr/local/bin/evcc-vm-rollup-hourly.sh
```

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

### 7.3 Simple cron alternative

```cron
7 * * * * /usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill-test --start-day $(date -d 'yesterday' +\%F) --end-day $(date +\%F) --write >> /var/log/evcc-vm-rollup.log 2>&1
```

## 8. Remove InfluxDB from the active dashboard path

Once you are sure that:

- raw data arrives correctly in VictoriaMetrics
- rollups are running correctly

EVCC no longer needs to depend on InfluxDB for dashboarding.

At that point you can:

- keep InfluxDB only as backup or reference
- or later shut it down completely

## Easy things to forget

- Grafana must point to VictoriaMetrics, not InfluxDB
- `Today*` and the long-range dashboards work on different data layers
- `metric_prefix` must be `evcc`, not `test_evcc`
- the raw-data reimport does not replace the ongoing rollup process
- the rollup needs a scheduler, or `Month/Year/All-time` will stop updating
- the current reimport helper does not handle Influx auth by itself
- if something looks wrong, verify raw data first, then rollups

## Measure `reimport_influx_to_vm.py` vs. `vmctl` safely

Short version:

- `vmctl` will very likely be faster than `reimport_influx_to_vm.py`
- because `vmctl` is designed for bulk migrations
- and it supports concurrency, compression, and large batches

But the right answer is a clean measurement, not a guess.

### Safe benchmark setup

Do **not** benchmark against your production VictoriaMetrics instance.

Instead:

1. start a temporary second VictoriaMetrics instance
2. write both imports there
3. compare runtime and imported data volume

Example:

```bash
mkdir -p /tmp/vm-bench-data
victoria-metrics-prod -storageDataPath=/tmp/vm-bench-data -httpListenAddr=:18428
```

Important:

- use a different port, for example `18428`
- use a separate empty data path
- keep it isolated from production

### Measure the Python reimport helper

```bash
/usr/bin/time -v python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://127.0.0.1:18428 \
  --db evcc \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z
```

Measure:

- wall clock time
- CPU time
- max RSS
- imported series and samples from the script output

### Measure `vmctl`

According to the VictoriaMetrics docs, the InfluxDB path is:

```bash
/usr/bin/time -v vmctl influx \
  --influx-addr=http://<influx-host>:8086 \
  --influx-database=evcc \
  --influx-filter-time-start=2025-01-01T00:00:00Z \
  --influx-filter-time-end=2025-02-01T00:00:00Z \
  --vm-addr=http://127.0.0.1:18428 \
  -s
```

References:

- [VictoriaMetrics vmctl](https://docs.victoriametrics.com/victoriametrics/vmctl/)
- [VictoriaMetrics vmctl InfluxDB](https://docs.victoriametrics.com/victoriametrics/vmctl/influxdb/)

### Compare fairly

For a fair comparison:

- use the same time range
- use the same InfluxDB source
- reset the temporary VictoriaMetrics data between runs
- start small:
  - 1 day
  - 7 days
  - 30 days
- only then run a larger benchmark

Reset the temporary VictoriaMetrics data:

```bash
rm -rf /tmp/vm-bench-data
mkdir -p /tmp/vm-bench-data
```

Then restart the temporary VictoriaMetrics process.

### What you get from this

Afterwards you will have:

- real runtime for each import path
- real RAM usage
- real sample and series counts
- no risk to your production VictoriaMetrics instance

### Recommendation

For the normal migration path:

- start with the existing Python helper, because it already lives in this repository
- benchmark `vmctl` only if:
  - the raw-data import is very large
  - or the Python helper runtime becomes unattractive

## Short version

1. verify VictoriaMetrics
2. import raw data from InfluxDB into VictoriaMetrics
3. verify the raw data
4. create the production rollup config
5. run `detect`, `plan`, and `benchmark`
6. run the initial rollup backfill with `--write`
7. verify the rollups
8. set up the hourly rollup job
9. keep InfluxDB only as fallback or historical reference
