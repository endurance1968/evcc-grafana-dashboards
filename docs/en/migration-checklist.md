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

## Live Ingest Prepared But Not Active Yet

- [ ] EVCC/Telegraf is prepared; see [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md).
- [ ] During a migration, EVCC continues to write to InfluxDB while the import runs.
- [ ] The VictoriaMetrics output in Telegraf remains disabled until the final delta import.
- [ ] If Telegraf is used, `omit_hostname = true` is set.

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

## Live Ingest

- [ ] Final delta import up to the cutover time has completed.
- [ ] If the delta import contained newly completed days, those rollups were refreshed with `--replace-range --write`.
- [ ] The VictoriaMetrics output in Telegraf was enabled after the final delta import.
- [ ] EVCC writes current raw data directly or through Telegraf to VictoriaMetrics; see [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md).
- [ ] Current raw series exist in VictoriaMetrics, for example `gridPower_value`, `pvPower_value`, or `batteryPower_value` for the last few minutes.
- [ ] VictoriaMetrics has no synthetic `db` label for this dashboard stack.
- [ ] If InfluxDB is still written in parallel, the planned legacy-path shutdown is documented.

## Grafana

- [ ] Grafana can reach the VictoriaMetrics datasource.
- [ ] Grafana datasource UID is `vm-evcc`, or `GRAFANA_DS_VM_EVCC_UID` is set to the actual UID.
- [ ] Dashboards are in the `EVCC` folder.
- [ ] `Today` shows current raw data.
- [ ] `Today - Details` shows raw detail panels without datasource errors.
- [ ] `Month`, `Year`, and `All-time` show rollup values.
- [ ] Grafana 13.0.1 or newer is used and the fixed tab-navigation dashboard deploy was tested.

## Cutover

Only remove InfluxDB from the active dashboard path after all previous sections are checked.

Pay special attention to the gap between the end of the last import and the first live samples in VictoriaMetrics. If even a small gap matters to you, repeat the final delta import for a cleanly completed time window before live ingest started.

Safe final state:

- EVCC writes current data to VictoriaMetrics.
- InfluxDB is retained only as fallback/reference, or shut down after backup.
- Rollup scheduler is active.
- Grafana dashboards point to VictoriaMetrics, not InfluxDB.
