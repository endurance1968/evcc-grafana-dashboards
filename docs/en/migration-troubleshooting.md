# Migration Troubleshooting

Use this document only when the normal path in [influx-to-vm-migration.md](./influx-to-vm-migration.md) reports a problem.

## First Rule: Verify Raw Data Before Rollups

Most long-range dashboard problems start in one of two places:

- raw data did not import completely
- rollups were built from already-broken raw data

Check in this order:

1. VictoriaMetrics health
2. raw metric presence
3. Influx-to-VM coverage
4. host-label hygiene
5. rollup output
6. Grafana datasource and dashboard variables

## Raw Metric Presence

Example raw series check:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

If this returns no series for a time range where InfluxDB has data, re-check the `vmctl influx` command, database name, time range, and credentials.

## Coverage Check Reports Problems

Run the coverage check directly after `vmctl` and before any cleanup:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Interpretation:

- `Repo-relevant problems: 0` means the active dashboard schema is not blocked.
- `Additional` findings can be extra EVCC metadata or non-dashboard measurements.
- `Critical energy problems` must be resolved before rollups are trusted.

To inspect one measurement:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --measurement-regex '^batterySoc$' \
  --only-problems
```

## PV Import Drift Or Missing `pvPower`

If the critical PV parity check fails, repair raw `pvPower` before rebuilding rollups.

1. Delete the affected raw `pvPower_value` family in VictoriaMetrics.
2. Re-import only `pvPower` with `vmctl influx --influx-filter-series`.
3. Rerun coverage for `pvPower`.
4. Rebuild `evcc_*` rollups.

Example:

```bash
curl -fsS -X POST 'http://localhost:8428/api/v1/admin/tsdb/delete_series' \
  --data-urlencode 'match[]=pvPower_value'

yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-series "on evcc from pvPower" \
  --influx-filter-time-start='2025-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-31T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

## `host` Cleanup Reports Conflicts

Check whether `host` exists:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

Dry-run:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Follow the exact recommendation printed by the tool.

Clean case:

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

If the tool reports that a target delete would remove unmanaged hostless sibling series, stop. Re-import or validate the affected measurement family first; otherwise detail dashboards can lose PV string or battery detail series even though aggregate panels still show values.

Conflict-preserving case, when hostless target values should remain authoritative:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --keep-target-values-on-conflict \
  --reset-cache \
  --write
```

Do not blindly drop these labels:

- `loadpoint`
- `vehicle`
- `id`
- `title`

They carry EVCC business meaning.

## Historical Business Label Rename

Use `vm-rewrite-label-value.py` only for deliberate business-label renames, for example after changing a PV title in EVCC. Change the live EVCC configuration first, otherwise new samples will keep using the old label.

Dry-run:

```bash
python3 vm-rewrite-label-value.py \
  --base-url http://localhost:8428 \
  --matcher '{title="Balkon PV"}' \
  --label title \
  --from "Balkon PV" \
  --to "Balkon Sued" \
  --backup-jsonl backups/rename-balkon-pv.jsonl \
  --rewritten-jsonl backups/rename-balkon-sued.jsonl
```

For PV devices, prefer `title` as the stable business key. EVCC can renumber PV `id` values when devices are added, removed, or reordered.

## Business Labels, Titles, And Blocklists

If Grafana finds raw data but individual detail panels look empty, duplicated, or wrongly grouped, check the EVCC business labels first. Common symptoms are:

- PV, battery, Consumer, AUX, or EXT details show only `Total` or unexpected names.
- Home consumption or consumer shares look too high because Consumer, AUX, or EXT meters are not filtered as intended.
- Loadpoints or vehicles are missing because `loadpoint` or `vehicle` is not present as a label.
- A heat pump appears as a normal loadpoint or vehicle consumer instead of the expected group.

Check the series directly in VictoriaMetrics:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=consumersPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=extPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=auxPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'
```

Important points:

- `title` is the most important display name for PV, battery, Consumer, AUX, and EXT devices.
- `loadpoint` separates loadpoints.
- `vehicle` separates vehicles.
- Missing Consumer, AUX, or EXT series are not an error when EVCC does not write such meters.
- Fix EVCC first when a name is wrong. New samples will then arrive correctly; historical values can be adjusted with `vm-rewrite-label-value.py` if needed.

Starting with version 0.309.2, EVCC writes dedicated consumers as `consumersPower`. Historical devices that previously ran as additional meters under `extPower` are not renamed automatically. For a role change with an unchanged `title`, set `consumer_legacy_ext_regex` in the rollup configuration and recalculate the complete affected period with `--replace-range --write`. Consumer wins per sampling interval during overlap, and the mapped legacy title is not also written as an EXT rollup.

Dashboard blocklists only filter the dashboard view and do not delete data. Put them into `vm-dashboard-install.env`; the deployer applies them during dashboard import:

```env
DASHBOARD_FILTER_CONSUMER_BLOCKLIST=^none$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|waermepumpe|heat pump).*"
```

`^none$` is the safe value for "filter nothing" because normal EVCC names should not match it. Quote regexes that contain `|`, spaces, or special characters. After changing a blocklist, redeploy the dashboards; no data migration is required for that.

### Excluding Sum And Parent Meters From Home Attribution

The Consumer and AUX blocklists apply to visible consumer series and to `Other`. EXT is intentionally separate: `extBlocklist` filters only the `Additional meters` tab, and EXT values are neither subtracted from home consumption nor summed as end consumers. No blocklist deletes VictoriaMetrics data.

Concrete use case: A sum meter and its child meters must not contribute to home attribution at the same time. Typical overlapping hierarchies include:

- **Distribution hierarchy:** `Main Distribution` > `Ground Floor Distribution` > `Office` and `Cinema`.
- **UPS hierarchy:** `UPS` > `Rack Cooler` and `Rack Fans`.
- **Laundry hierarchy:** `Laundry` > `Washing Machine` and `Dryer`.

Choose exactly one non-overlapping level per hierarchy. If, for example, the sum meters are written under EXT and only the child meters should remain visible, the configuration can look like this:

```env
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Main.*|^Ground Floor Distribution$|^UPS$|^Laundry$"
```

Always adapt the regex to the actual EVCC `title` values and the Consumer, EXT, or AUX roles. A filtered Consumer or AUX meter disappears from both the legend and home attribution. A filtered EXT meter disappears only from the separate additional-meter view. Historical merging of an identical EXT/Consumer `title` is handled by the rollup through `consumer_legacy_ext_regex`.

`Other` intentionally remains the difference between `homePower` and all included detail meters. It can therefore contain real conversion and distribution losses as well as loads without a dedicated meter, such as microinverter losses or a load connected to the wallbox feeder rather than to a wallbox itself. If the detail meters remaining after the blocklists exceed home consumption, the dashboard shows the red `Meter overlap` diagnostic; check the hierarchy, sign, and meter assignment in that case.

## Forecast Panel Is Empty

Forecast panels are based exclusively on the EVCC raw metric `tariffSolar_value`. The dashboard does not call Forecast.Solar, Solcast, Open-Meteo, or any other provider directly.

Data flow:

```text
EVCC solar forecast -> tariffSolar_value -> Telegraf/Influx line protocol -> VictoriaMetrics -> Grafana
```

First check whether the metric exists in VictoriaMetrics:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=tariffSolar_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/query' \
  --data-urlencode 'query=last_over_time(tariffSolar_value[24h])'
```

Interpretation:

- Result exists: check Grafana datasource, time range, and panel settings.
- No result: EVCC is not currently writing a solar forecast. Configure the forecast in EVCC or accept that forecast panels stay empty.
- Old history without forecast is not an import error if EVCC did not write `tariffSolar_value` at that time.
- In the Today Details PV tab, the `Solar forecast status` panel visibly shows whether EVCC forecast samples arrived in the last 24 hours. The forecast line in overview panels may still be absent silently.
## Empty Grafana Dashboards

`Today` empty usually means raw data or datasource problems:

- Grafana datasource points to the wrong host.
- Datasource UID does not match `vm-evcc` or the deploy override.
- EVCC is not writing current raw data to VictoriaMetrics.

`Month`, `Year`, or `All-time` empty usually means rollups are missing:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

If no `evcc_*` series exist, rerun the rollup backfill and scheduler setup from [influx-to-vm-migration.md](./influx-to-vm-migration.md).
