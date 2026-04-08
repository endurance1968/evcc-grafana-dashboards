# How To Use Telegraf For Parallel Database Writes

This document describes the Telegraf fan-out pattern used for EVCC metrics so the same incoming write stream can be sent to multiple backends in parallel.

## Goal

Use Telegraf as a single ingest point and forward the incoming EVCC metrics to:

- InfluxDB v1 for legacy dashboards
- VictoriaMetrics for new dashboards
- PostgreSQL for SQL-based analysis and historical backfill targets

## Why Telegraf sits in the middle

Telegraf gives us one controlled pipeline:

`evcc -> Telegraf listener -> InfluxDB + VictoriaMetrics + PostgreSQL`

That keeps the write path centralized and avoids teaching every producer about every backend.

## Important API detail

In this setup EVCC writes with the InfluxDB v2 client path:

- request path: `/api/v2/write`
- auth style: `Authorization: Token ...`

A plain `[[inputs.influxdb_listener]]` only handles the Influx v1 write path `/write`.

Because of that, EVCC should target a Telegraf `[[inputs.influxdb_v2_listener]]` endpoint.

## Recommended listener layout

Current setup uses the Influx v2 listener on the standard EVCC write port and keeps the v1 listener disabled.

Example:

```toml
[agent]
  interval = "10s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  flush_interval = "10s"
  flush_jitter = "1s"
  precision = "1s"
  omit_hostname = true
  debug = true

#[[inputs.influxdb_listener]]
#  service_address = ":8086"
#  read_timeout = "30s"
#  write_timeout = "30s"
#  basic_username = "<listener-user>"
#  basic_password = "<listener-password>"

[[inputs.influxdb_v2_listener]]
  service_address = ":8086"
  read_timeout = "30s"
  write_timeout = "30s"
  token = "<listener-token>"
```

Practical meaning:

- `:8086` is the active EVCC write target via the Influx v2 API.
- the v1 listener stays commented out unless you explicitly need `/write` compatibility for manual tests.
- `omit_hostname = true` avoids adding an infrastructure-only `host` label from Telegraf.

## Example output fan-out

```toml
[[outputs.http]]
  alias = "victoriametrics"
  url = "http://<victoriametrics-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]

[[outputs.postgresql]]
  connection = "host=<postgres-host> user=<postgres-user> password=<postgres-password> dbname=telemetry sslmode=disable"
  tags_as_foreign_keys = false

[[outputs.influxdb]]
  alias = "influx"
  urls = ["http://<influxdb-host>:8086"]
  database = "evcc"
  username = "<influxdb-user>"
  password = "<influxdb-password>"
  timeout = "10s"
```

Practical meaning:

- `alias` makes Telegraf logs easier to read when two outputs use the same plugin type.
- VictoriaMetrics uses `outputs.http` with `data_format = "influx"` so Telegraf sends Influx line protocol directly to `/influx/write`.
- This deliberately avoids Telegraf's `outputs.influxdb` database handling, so VictoriaMetrics does not synthesize a `db` label from the write target.

Important:

- Do not use `[[outputs.influxdb]]` for VictoriaMetrics in this repository.
- If you set `database = "evcc"`, VictoriaMetrics will ingest a synthetic `db="evcc"` label.
- If you omit `database`, Telegraf falls back to its default database name and VictoriaMetrics will still ingest a synthetic `db` label such as `db="telegraf"`.
- The repository assumes one VictoriaMetrics instance per EVCC instance, so the live Telegraf path must stay free of any shared `db` multiplexing label.

## Operational checks after changes

After any listener or output change, verify all of the following:

1. EVCC can write successfully to the intended Telegraf listener.
2. A fresh probe point appears in InfluxDB.
3. The same probe series appears in VictoriaMetrics without a `db` label.
4. The same probe data appears in PostgreSQL.
5. Telegraf logs show no continuous output errors.

Quick VictoriaMetrics check:

```bash
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)

curl -sG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=gridPower_value' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END"
```

Expected result for the live Telegraf path:

- a fresh raw series such as `{ "__name__": "gridPower_value" }`
- no `db` field in that series object

## Why we keep InfluxDB during migration

InfluxDB remains in the fan-out while the legacy dashboards are still in use.

That allows us to:

- preserve the existing dashboards without immediate rewrites
- build and test the VictoriaMetrics dashboards in parallel
- backfill historical data into VictoriaMetrics and PostgreSQL without interrupting EVCC writes

## Migration guidance

Recommended order:

1. Confirm the live pipeline works through Telegraf.
2. Keep InfluxDB in the output fan-out so legacy dashboards continue to work.
3. Backfill historical raw data from InfluxDB into VictoriaMetrics.
4. Regenerate or rebuild the required aggregations for the new dashboard set.
5. Backfill historical raw data from InfluxDB into PostgreSQL.
6. Only remove the legacy Influx path after the new dashboards are accepted.
