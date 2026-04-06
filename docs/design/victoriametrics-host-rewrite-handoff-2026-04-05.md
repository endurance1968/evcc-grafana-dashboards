# VictoriaMetrics Host Rewrite Handoff (2026-04-05)

This note captures the latest known-good migration-debugging state for the EVCC `host` label cleanup in VictoriaMetrics.

## Current code baseline

- Repository: `evcc-grafana-dashboards`
- Script: `scripts/helper/vm-rewrite-drop-label.py`
- Current script version: `2026.04.05.21`
- Current commit with the last successful dry-run state: `2ebac6b`

## Operational prerequisites

After `vmrestore`, ownership must be repaired before VictoriaMetrics starts cleanly:

```bash
./restore.sh
chown -R victoriametrics:victoriametrics /var/lib/victoriametrics
systemctl restart victoriametrics
curl -fsSL http://127.0.0.1:8428/health
```

A clean baseline was previously validated with:

```bash
python3 compare_import_coverage.py \
  --influx-url http://192.168.1.183:8086 \
  --influx-db evcc \
  --vm-base-url http://127.0.0.1:8428 \
  --vm-db-label evcc \
  --start 2025-01-01T00:00:00Z \
  --end 2026-04-02T23:59:59Z \
  --only-problems \
  --progress
```

## Proven special case

The `pvPower_value{db="evcc",id="",host!=""}` family is a `delete-only` case.

The following mode was validated as safe for that family:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://127.0.0.1:8428 \
  --matcher '{__name__="pvPower_value",db="evcc",id="",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/pvPower-total-host.jsonl \
  --rewritten-jsonl backups/pvPower-total-hostless.jsonl \
  --merge-target \
  --delete-source-when-fully-shadowed \
  --write \
  --reset-cache
```

Result:

- source series deleted without re-import
- `compare_import_coverage.py` remained OK for `pvPower`

## Broad dry-run status

The first stable broad dry-run used this command:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://127.0.0.1:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-hostless.jsonl \
  --merge-target \
  --delete-source-when-fully-shadowed \
  --keep-target-values-on-conflict
```

Observed summary on 2026-04-05:

- `exported_series`: `175`
- `exported_points`: `187695`
- `overlap_timestamps`: `187695`
- `value_conflicts`: `4774`
- `delete_only_series`: `2`
- `delete_only_points`: `4774`
- `grouped_unresolved_value_conflicts`: `0`
- `grouped_source_value_conflicts`: `0`
- `unresolved_value_conflicts`: `0`
- `output_points`: `184018277`

Interpretation:

- all host-tagged source points already map onto hostless targets
- only two grouped target families are handled as `delete-only`
- there are currently no unresolved grouped conflicts blocking a broad write when `--keep-target-values-on-conflict` is enabled

## Next recommended command

From a clean restored baseline, the next intended operation is:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://127.0.0.1:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-hostless.jsonl \
  --merge-target \
  --delete-source-when-fully-shadowed \
  --keep-target-values-on-conflict \
  --write \
  --reset-cache
```

Immediately afterwards, rerun:

```bash
python3 compare_import_coverage.py \
  --influx-url http://192.168.1.183:8086 \
  --influx-db evcc \
  --vm-base-url http://127.0.0.1:8428 \
  --vm-db-label evcc \
  --start 2025-01-01T00:00:00Z \
  --end 2026-04-02T23:59:59Z \
  --only-problems \
  --progress
```

## Why this note exists

This is a persistent handoff note so the current migration-debugging state is recoverable without depending on chat history.

## Successful broad write (2026-04-06)

The broad `host` cleanup was successfully executed with:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://127.0.0.1:8428 \
  --matcher '{db="evcc",host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-hostless.jsonl \
  --merge-target \
  --delete-source-when-fully-shadowed \
  --keep-target-values-on-conflict \
  --write \
  --reset-cache
```

Observed write summary:

- `exported_series`: `175`
- `delete_only_series`: `2`
- `deleted_target_series`: `173`
- `imported_source_series`: `173`
- `imported_chunk_series`: `590`
- `source_series_after_delete`: `0`
- `import_verification.ok`: `true`
- `unresolved_value_conflicts`: `0`
- `total_seconds`: about `1046.6`

Post-write coverage result:

- `Repo-relevant problems`: `0`
- `Critical energy problems`: `0`
- final status: `OK FOR REPO`

Remaining additional missing measurements are outside the active dashboard schema and currently look like metadata / string / boolean families only.

This means the repository-relevant raw data is healthy enough to proceed with rollups and the next migration steps.
## Successful initial rollup backfill (2026-04-06)

The first production rollup backfill was successfully executed with:

```bash
python3 evcc-vm-rollup.py \
  --config ./evcc-vm-rollup.conf \
  backfill \
  --start-day 2025-01-01 \
  --end-day 2026-04-02 \
  --progress \
  --write
```

Observed write summary:

- `rollup metrics`: `36`
- `output series`: `1064`
- `output samples`: `24885`
- `month chunks`: `16`
- `import batches`: `17`
- `total runtime`: about `122.4 s`
- `peak RAM`: about `1240.7 MB`

Post-write validation:

- `check_data.py` ran in `phase=full`
- rollups were detected successfully
- host-tagged raw series remained at `0`
- all core raw metrics and all core rollup metrics were `OK`
- `evcc_pv_energy_daily_wh{db="evcc"}` exists across the expected local month/year label combinations

Remaining warning:

- `prioritySoc_value` was `0` in the current raw window, so `check_data.py` ended with `Overall: WARNING`
- this does not currently block the rollup migration result because the repo-relevant raw and rollup families are present and healthy

This means the VM migration is now in the expected post-backfill state: raw data is normalized, production `evcc_*` daily rollups exist, and the next operational step is scheduler setup and dashboard cutover to the rollup-backed long-range panels.
