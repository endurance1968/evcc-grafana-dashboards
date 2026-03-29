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

Keep v1 and v2 separated by port.

Example:

```toml
[[inputs.influxdb_listener]]
  service_address = ":8086"
  read_timeout = "30s"
  write_timeout = "30s"
  basic_username = "..."
  basic_password = "..."

[[inputs.influxdb_v2_listener]]
  service_address = ":8186"
  read_timeout = "30s"
  write_timeout = "30s"
  token = "..."
```

Practical meaning:

- `:8086` stays available for manual Influx-v1 style tests.
- `:8186` is the EVCC write target when EVCC uses the v2 write API.

## Example output fan-out

```toml
[[outputs.influxdb]]
  urls = ["http://192.168.1.183:8086"]
  database = "evcc"
  username = "..."
  password = "..."
  timeout = "10s"

[[outputs.influxdb]]
  urls = ["http://192.168.1.160:8428"]
  database = "evcc"
  timeout = "10s"

[[outputs.postgresql]]
  connection = "host=192.168.1.164 user=... password=... dbname=telemetry sslmode=disable"
  tags_as_foreign_keys = false
```

## Operational checks after changes

After any listener or output change, verify all of the following:

1. EVCC can write successfully to the intended Telegraf listener.
2. A fresh probe point appears in InfluxDB.
3. The same probe series appears in VictoriaMetrics.
4. The same probe data appears in PostgreSQL.
5. Telegraf logs show no continuous output errors.

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
