# Migration Checklist

Use this checklist after [influx-to-vm-migration.md](./influx-to-vm-migration.md) and before shutting down the old InfluxDB dashboard path.

## Runtime

- [ ] VictoriaMetrics responds:

```bash
curl -fsSL http://localhost:8428/health
```

Expected:

```text
OK
```

- [ ] Grafana can reach the VictoriaMetrics datasource.
- [ ] Grafana datasource UID is `vm-evcc`, or `GRAFANA_DS_VM_EVCC_UID` is set to the actual UID.

## Raw Import

- [ ] `vmctl influx` completed for the intended time range.
- [ ] Raw EVCC series exist in VictoriaMetrics:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

Expected: JSON response with at least one `pvPower_value` series for a range where InfluxDB had PV data.

- [ ] VM-only raw check is clean:

```bash
python3 check_data.py --base-url http://localhost:8428 --phase raw
```

Expected: required raw families are present; label hygiene output has no unresolved blocker.

- [ ] Influx-to-VM coverage has no dashboard blockers:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Expected:

```text
Repo-relevant problems: 0
Critical energy problems: 0
OK FOR REPO
```

## Label Hygiene

- [ ] `host` cleanup was skipped because no `host` series exist, or completed with the tool recommendation.
- [ ] No EVCC business labels were dropped manually: `loadpoint`, `vehicle`, `id`, `title`.

Optional final check:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

Expected: empty data array, unless you intentionally kept `host`.

## Rollups

- [ ] Production config uses `metric_prefix = evcc`.
- [ ] `detect` finds the expected dimensions:

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

- [ ] `plan` lists daily rollups:

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

- [ ] Initial backfill completed with `--write`.
- [ ] Daily rollup series exist:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Expected: at least one `evcc_pv_energy_daily_wh` series for a range with PV history.

- [ ] Full checker includes rollups and reports no blocker:

```bash
python3 check_data.py --base-url http://localhost:8428 --end-time 2026-03-30T23:59:59Z
```

## Scheduler

- [ ] `/usr/local/bin/evcc-vm-rollup-daily.sh` exists and is executable.
- [ ] Cron or equivalent scheduler runs once per day after yesterday is complete.
- [ ] Scheduler command uses `--replace-range --write`.
- [ ] Log file receives successful runs:

```bash
tail -n 80 /var/log/evcc-vm-rollup.log
```

## Grafana

- [ ] Dashboards are in the `EVCC` folder.
- [ ] `Today` shows current raw data.
- [ ] `Today - Details` shows raw detail panels without datasource errors.
- [ ] `Month`, `Year`, and `All-time` show rollup values.
- [ ] If Grafana 13.0.1 or newer is used, `DASHBOARD_SET=tabs` was tested or consciously skipped.

## Cutover

Only remove InfluxDB from the active dashboard path after all previous sections are checked.

Safe final state:

- EVCC writes current data to VictoriaMetrics.
- InfluxDB is retained only as fallback/reference, or shut down after backup.
- Rollup scheduler is active.
- Grafana dashboards point to VictoriaMetrics, not InfluxDB.