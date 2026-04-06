# Migrate from InfluxDB to VictoriaMetrics

This guide describes the recommended end-user path from an existing EVCC + InfluxDB setup to VictoriaMetrics.

Note:

- this guide uses `localhost` for VictoriaMetrics examples
- replace `localhost` with your actual VictoriaMetrics host if VictoriaMetrics is not running locally

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
curl -fsSLo compare_import_coverage.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/compare_import_coverage.py
curl -fsSLo vm-rewrite-drop-label.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/vm-rewrite-drop-label.py
```

## Files used in this migration

- raw-data import:
  - `vmctl`
- health and presence checks:
  - `check_data.py`
- source-versus-import coverage check:
  - `compare_import_coverage.py`
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
curl -fsSL http://localhost:8428/health
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
  --vm-addr='http://localhost:8428'
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
  --vm-addr='http://localhost:8428'
```

Notes:

- `vmctl` adds `db="evcc"` from the selected Influx database
- the imported raw model can include labels such as `loadpoint`, `vehicle`, `id`, `title`, and sometimes `host`
- that richer label model is expected and is the basis for the cleanup step below

### 2.2 Verify the raw data directly

Query VictoriaMetrics directly:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

You should also inspect a few labelsets:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

### 2.3 Run the repository data check

Use the VM-only checker after the import. In the default `auto` phase it validates raw data first and only checks rollups once they exist. It also reports whether `host`-tagged series are present and should be normalized away.

For a current production VM:

```bash
python3 check_data.py --base-url http://localhost:8428 --db evcc

# explicit raw-import phase
python3 check_data.py --base-url http://localhost:8428 --db evcc --phase raw
```

For a historical benchmark or migration VM, anchor the logical check point to the imported range:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --db evcc \
  --end-time 2026-03-30T23:59:59Z
```

### 2.4 Compare import coverage against Influx before cleanup

Run this directly after `vmctl` and before any `host` rewrite. The default run checks the full Influx measurement set, but splits the result into `repo-relevant` and `additional` groups so the conclusion clearly shows whether the active dashboard schema is blocked or only extra EVCC metadata families are affected.

If this check reports problems, stop here and explicitly re-import the affected measurements before cleanup or rollups.

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --vm-db-label evcc \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Use `--measurement-regex '^batterySoc$'` if you want to inspect only one suspicious measurement. Use `--repo-relevant-only` only when you explicitly want to limit the check to the active dashboard schema. Additional findings now include a short `Hint` so you can see whether they are likely string/boolean metadata or a real extra import gap. The helper now also runs a critical monthly PV total-series parity check against the original Influx legacy semantics for `pvPower{id=""}` so it can catch cases where the measurement exists in VM but the imported raw values are still materially too low.

If that critical PV check fails, the safest repair path is:

1. delete the affected raw `pvPower_value` family in VictoriaMetrics
2. re-import only `pvPower` via `vmctl influx --influx-filter-series`
3. rerun `compare_import_coverage.py` for `pvPower`
4. rebuild the `evcc_*` rollups after the raw PV data is healthy again

Example repair run for `pvPower` only:

```bash
curl -fsS -X POST 'http://localhost:8428/api/v1/admin/tsdb/delete_series' \
  --data-urlencode 'match[]=pvPower_value{db="evcc"}'

yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-series "on evcc from pvPower" \
  --influx-filter-time-start='2025-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-31T23:59:59Z' \
  --vm-addr='http://localhost:8428'

python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --vm-db-label evcc \
  --start 2025-01-01T00:00:00Z \
  --end 2026-03-31T23:59:59Z \
  --measurement-regex '^pvPower$' \
  --only-problems
```

The `--influx-filter-series` flag is documented in the official vmctl InfluxDB docs: [Filtering](https://docs.victoriametrics.com/victoriametrics/vmctl/influxdb/).

## 3. First cleanup step: remove `host` only if needed

Do this step only if the data check or a direct series query shows host-tagged raw series.

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

### 3.1 Check first whether `host` is present

The default `check_data.py` output already reports this in the `Cleanup checks` section.

You can also query it directly:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={db="evcc",host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

If this returns no series, skip the `host` cleanup step.

### 3.2 Dry-run the rewrite first

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

The dry-run exports the host-tagged source series, removes `host` in memory, and reports:

- how many source series were exported
- whether transformed timestamps overlap existing hostless target series
- whether there are value conflicts

### 3.3 Recommended write mode

If the dry-run looks clean, use merge mode so existing hostless targets are preserved and merged safely:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
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
- if the analysis shows that all source points already overlap existing hostless target points and only value conflicts remain, prefer `--keep-target-values-on-conflict` so the existing hostless target values stay authoritative
- only use `--allow-value-conflicts` if you have reviewed the differences and want source values to win explicitly

Typical conflict-safe write command for that case:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --keep-target-values-on-conflict \
  --reset-cache \
  --write
```

Verified examples from 2026-04-06:

- conflict-preserving case on a partially normalized test VM:
  - background: a short Telegraf transition phase had written duplicate raw series with `host!=""`
  - dry-run result: `175` host-tagged source series, `187695` source points, `187695` overlapping timestamps, `4774` value conflicts
  - interpretation: all host-tagged samples already had hostless counterparts, so the hostless series were treated as authoritative and host-tagged samples were merged only when timestamps were missing
  - write result with `--merge-target --keep-target-values-on-conflict`: import verification passed with `ok=true`, `checked_targets=175`, `failures=[]`, and `source_series_after_delete=0`
- clean end-to-end migration run on a freshly restored VM using `vm-rewrite-drop-label.py v2026.04.06.2`:
  - analyze result: `175` host-tagged source series, `187695` source points, `0` exact overlaps, `0` conflicts
  - write result: `import_verification.ok=true`, `failures=[]`, `source_series_after_delete=0`, `Host-tagged series: 0`
  - follow-up validation: `compare_import_coverage.py` reported `Repo-relevant problems: 0`, `Critical energy problems: 0`, and `OK FOR REPO`

This gives two verified production cases for the same command:

- if exact hostless target series already exist, keep them authoritative with `--keep-target-values-on-conflict`
- if only the host-tagged transition series exist, the rewrite cleanly recreates the hostless targets and removes the host-tagged originals

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
base_url = http://localhost:8428
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
- the `[benchmark]` section is optional; if omitted, the script uses the last 30 days with `step = 1d`

## 5. Inspect the rollup before writing

Use these two commands before the first backfill:

- `detect`
  - shows which business dimensions were found in the raw data, for example loadpoints, vehicles, `EXT` titles, and `AUX` titles
- `plan`
  - shows which rollups will be created from the detected raw model and helps verify that the config matches your installation

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

- whether the required raw source metrics can be queried from VictoriaMetrics
- whether the direct source queries are fast enough
- which rollups are Python-only and will only be computed during backfill
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
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh{db="evcc"}' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Then run the repository checker again:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --db evcc \
  --end-time 2026-03-30T23:59:59Z
```

## 8. Set up the hourly rollup refresh

Use a simple cron job that runs every hour.

### 8.1 Create the wrapper script

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

### 8.2 Create the cron job

Open root crontab:

```bash
sudo crontab -e
```

Add this entry:

```cron
7 * * * * /usr/local/bin/evcc-vm-rollup-hourly.sh >> /var/log/evcc-vm-rollup.log 2>&1
```

Optional check:

```bash
sudo crontab -l
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
- remove `host` as the first cleanup step only when `host`-tagged series are actually present
- keep business labels such as `loadpoint`, `vehicle`, `id`, and `title`
- use `compare_import_coverage.py` and `check_data.py` after the raw import, then run `check_data.py` again after the initial rollup backfill

## Next steps

- review whether the five basic daily rollups should move closer to the maintainer's PromQL-based logic:
  - PV energy
  - home energy
  - grid import energy
  - grid export energy
  - loadpoint energy
- keep the broader Python backfill logic mainly for rollups that are harder to express cleanly in PromQL:
  - tariff and cost rollups
  - PV/battery/grid attribution
  - more complex vehicle and battery calculations

## Short version

1. verify VictoriaMetrics
2. import raw data with `vmctl influx`
3. verify raw data with `compare_import_coverage.py` and `check_data.py`
4. if needed, remove `host` with `vm-rewrite-drop-label.py`
5. create the production rollup config
6. run `detect`, `plan`, and `benchmark`
7. run the initial rollup backfill with `--write`
8. verify the rollups
9. set up the hourly rollup job
10. keep InfluxDB only as fallback or historical reference



## 2026-04-06 calibration baseline before mean rollup switch

Before switching the Python rollup path from `max` to `mean` for PV and home daily energy, the observed baseline was:

- `evcc_pv_energy_daily_wh`: current VM rollup matched a raw `max` bucket path, while Influx and the usable VRM comparison months tracked the raw `mean` path much more closely.
- `evcc_home_energy_daily_wh`: current VM rollup matched a raw `max` bucket path, while Influx tracked the raw `mean` path much more closely.
- `evcc_grid_import_daily_wh`: current VM rollup matched the `gridEnergy` counter-spread path and was usually closer to VRM than the legacy Influx aggregate, so it was intentionally left unchanged.

This baseline should be used as the before-state when validating the next full backfill after the PV/home reducer change.

## 2026-04-06 verified comparison after PV/home mean switch

After the PV/home reducer switch, the monthly comparison was revalidated against:

- Influx raw monthly semantics for `PV`, `Home`, and `Grid import`
- the Influx `EVCC_AGGREGATIONS` datasource (`evcc_agg`) for dashboard-level `Home`, `Loadpoints`, and `Battery netto`
- VictoriaMetrics rollups in the `evcc_*` namespace
- the locally cached Victron VRM day totals for `PV` and `Grid import`

Important dashboard semantics for the Influx month dashboard `Gesamt: Energieverteilung`:

- `Home` comes from `homeDailyEnergy`
- `Loadpoints` come from `loadpointDailyEnergy`
- `Battery netto` is `chargeDailyEnergy - dischargeDailyEnergy`

Comparison months with complete VRM coverage:

- `2025-08`
- `2025-09`
- `2026-02`
- `2026-03`

Bold values below are the values that were observed to be genuinely close within the same row.

| Month | Metric | Influx | VM rollup | VM aggregation | VRM |
| --- | --- | ---: | ---: | ---: | ---: |
| 2025-08 | PV | **1825.700** | **1826.580** | 1793.831 | **1829.700** |
| 2025-08 | Home | **1990.773** | **1994.219** | **1986.997** | - |
| 2025-08 | Grid import | 655.300 | **633.260** | 657.920 | **634.000** |
| 2025-08 | Loadpoints | **366.213** | **366.768** | 715.256 | - |
| 2025-08 | Battery netto | **57.051** | **55.911** | 125.630 | - |
| 2025-09 | PV | **996.500** | **997.219** | 1021.473 | **996.200** |
| 2025-09 | Home | **1244.685** | **1245.235** | **1239.921** | - |
| 2025-09 | Grid import | 624.000 | **612.290** | 591.455 | **611.900** |
| 2025-09 | Loadpoints | **367.166** | **367.416** | 750.311 | - |
| 2025-09 | Battery netto | **-21.578** | **-19.482** | -41.672 | - |
| 2026-02 | PV | **511.800** | **511.763** | 540.248 | **512.200** |
| 2026-02 | Home | **1128.338** | **1129.096** | **1138.051** | - |
| 2026-02 | Grid import | **1176.500** | **1168.690** | 1149.994 | **1165.600** |
| 2026-02 | Loadpoints | **515.632** | **516.647** | 934.805 | - |
| 2026-02 | Battery netto | **28.346** | **29.868** | 157.272 | - |
| 2026-03 | PV | **1252.900** | **1252.948** | 1185.964 | **1249.900** |
| 2026-03 | Home | **1262.666** | **1265.252** | 1218.546 | - |
| 2026-03 | Grid import | 531.500 | **512.810** | 469.013 | **510.800** |
| 2026-03 | Loadpoints | **405.301** | **406.338** | 796.323 | - |
| 2026-03 | Battery netto | **63.557** | **60.979** | **59.970** | - |

Summary from this verified comparison:

- `VM rollup` is on Influx/VRM level for `PV`
- `VM rollup` is on Influx dashboard level for `Home`, `Loadpoints`, and `Battery netto`
- `VM rollup` is closer to `VRM` than Influx for `Grid import`
- `VM aggregation` remains visibly less reliable, especially for `PV`, `Loadpoints`, and several `Grid import` months

