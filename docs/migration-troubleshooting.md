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