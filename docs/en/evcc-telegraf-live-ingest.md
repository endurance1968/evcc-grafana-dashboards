# EVCC/Telegraf Live Ingest To VictoriaMetrics

German version: [evcc-telegraf-live-ingest.md](../de/evcc-telegraf-live-ingest.md).

This guide explains how current EVCC metrics are written to VictoriaMetrics.

For a new installation, enable the write path immediately. For an InfluxDB migration, prepare it first and enable it only after the final delta import. This lets you test the configuration early while avoiding a period that is written to VictoriaMetrics both by live ingest and by import.

In short:

- new stack: configure, enable, verify, then continue to Grafana
- migration: configure, keep the VictoriaMetrics output disabled, migrate history, run the final delta import, then enable and verify

## Which Path Should I Use?

### New VictoriaMetrics Stack Without Legacy InfluxDB

If you do not need to keep a legacy InfluxDB path running in parallel, EVCC can write directly to VictoriaMetrics.

Use this path for new installations.

### Migration From InfluxDB

If existing InfluxDB dashboards should continue to work during the migration, use Telegraf as fan-out:

```text
EVCC -> Telegraf -> InfluxDB v1 + VictoriaMetrics
```

This is the recommended migration path because EVCC writes to one target and Telegraf distributes the data to old and new backends.

Important for migrations: set up Telegraf early, but enable the VictoriaMetrics output only at cutover. Until then, Telegraf continues to write only to InfluxDB. The old environment stays stable, and the VictoriaMetrics history is populated in a controlled way by the InfluxDB import.

## Prerequisites

- VictoriaMetrics is reachable, for example `http://<victoriametrics-host>:8428`.
- EVCC can reach the target host.
- For Telegraf fan-out, Telegraf is installed and can reach InfluxDB and VictoriaMetrics.
- Use one VictoriaMetrics instance per EVCC instance. Do not use a synthetic `db` label for multiple EVCC systems in one shared VM instance.

## Path A: EVCC Writes Directly To VictoriaMetrics

EVCC uses its `influx:` configuration. VictoriaMetrics provides an InfluxDB-compatible API.

In `evcc.yaml`:

```yaml
influx:
  url: http://<victoriametrics-host>:8428
```

If VictoriaMetrics is protected with Basic Auth, username and password can be embedded in the URL:

```yaml
influx:
  url: http://<user>:<password>@<victoriametrics-host>:8428
```

Notes:

- Values set in the EVCC web configuration can override file values from `evcc.yaml`.
- Use this direct path only when EVCC does not also need to keep writing to an old InfluxDB instance.
- The dashboards need raw metrics such as `pvPower_value`, `gridPower_value`, `homePower_value`, and `chargePower_value` to arrive in VictoriaMetrics.

Reload or restart EVCC afterwards, depending on your installation type.

## Path B: EVCC Writes To Telegraf And Telegraf Fans Out

This path is recommended for migrations.

### 1. Point EVCC At Telegraf

Configure EVCC with an InfluxDB-v2-compatible target pointing at the Telegraf listener:

```yaml
influx:
  url: http://<telegraf-host>:8086
  database: evcc
  token: <listener-token>
  org: evcc
```

The `database`, `token`, and `org` values must match the Telegraf listener. For InfluxDB v2, `database` means bucket, but EVCC keeps the name `database` for compatibility.

### 2. Configure The Telegraf Listener

In the Telegraf config:

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

[[inputs.influxdb_v2_listener]]
  service_address = ":8086"
  read_timeout = "30s"
  write_timeout = "30s"
  token = "<listener-token>"
```

Important:

- `[[inputs.influxdb_v2_listener]]` is suitable for EVCC's `/api/v2/write` path.
- `omit_hostname = true` prevents Telegraf from adding an infrastructure-only `host` label.
- The old `[[inputs.influxdb_listener]]` for `/write` is only needed when you explicitly run InfluxDB-v1 write clients through Telegraf.

### 3. Prepare The VictoriaMetrics Output

Write to VictoriaMetrics through `outputs.http`:

```toml
[[outputs.http]]
  alias = "victoriametrics_evcc"
  url = "http://<victoriametrics-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]
```

For a new installation, keep this block active. For a migration, comment out the block until cutover or keep it prepared and enable it only after the final delta import:

```toml
# [[outputs.http]]
#   alias = "victoriametrics_evcc"
#   url = "http://<victoriametrics-host>:8428/influx/write"
#   method = "POST"
#   data_format = "influx"
#   timeout = "10s"
#   non_retryable_statuscodes = [400]
```

Do not use `[[outputs.influxdb]]` for VictoriaMetrics. That plugin can create a synthetic `db` label. The dashboards and rollups expect a dedicated VictoriaMetrics instance without shared `db` multiplexing.

### 4. Optionally Keep Writing To Legacy InfluxDB

If old InfluxDB dashboards should keep working, keep InfluxDB as an additional Telegraf output:

```toml
[[outputs.influxdb]]
  alias = "influx_legacy"
  urls = ["http://<influxdb-host>:8086"]
  database = "evcc"
  username = "<influxdb-user>"
  password = "<influxdb-password>"
  timeout = "10s"
```

Use this `outputs.influxdb` block only for legacy InfluxDB, not for VictoriaMetrics.

### 5. Restart Telegraf

```bash
sudo systemctl restart telegraf
sudo systemctl status telegraf
```

Check logs:

```bash
journalctl -u telegraf -n 100 --no-pager
```

During a migration, this restart is also useful in preparation mode. Verify that EVCC still writes through Telegraf to InfluxDB. The VictoriaMetrics output remains disabled at this point.

## Enable The VictoriaMetrics Write Path During Migration

Run this section only after the InfluxDB history has been imported, checked, and the final delta import has completed.

A simple cutover for non-experts:

1. Note the cutover time.
2. Import the last missing InfluxDB data up to that time into VictoriaMetrics.
3. Enable the prepared `[[outputs.http]]` block in Telegraf.
4. Restart Telegraf.
5. Verify that current series arrive in VictoriaMetrics.

If you must avoid even a few seconds of missing data, plan a short maintenance window: stop EVCC briefly, run the final delta import, enable the VictoriaMetrics output, start Telegraf, and start EVCC again. That is easier and cleaner than intentionally overlapping import and live-ingest time ranges.

## Verify Live Ingest

### VictoriaMetrics Health Check

```bash
curl -fsSL http://<victoriametrics-host>:8428/health
```

Expected:

```text
OK
```

### Find A Current EVCC Series

After a few EVCC write intervals:

```bash
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START=$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ)

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=gridPower_value' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END"
```

Expected:

- at least one `gridPower_value` series
- no `db` label
- no `host` label when Telegraf is used with `omit_hostname = true`

### Check EVCC Business Labels

Before deploying dashboards, quickly verify that EVCC sends the business labels. These labels later decide how Grafana separates or groups PV, battery, AUX/EXT, loadpoint, and vehicle series:

```bash
curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'end=now'

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'end=now'
```

Expected result:

- PV, battery, AUX, and EXT series have stable `title` values when the devices are named in EVCC.
- Loadpoint series have a `loadpoint` label.
- Vehicle series have a `vehicle` label once EVCC writes vehicle data.
- Missing AUX/EXT series are OK when you do not use such EVCC meters; the dashboards should still remain usable.

If a name is wrong, fix EVCC first. New samples will then use the new name; old historical labels stay unchanged until you intentionally migrate them.


### Verify PV Forecast From EVCC

The dashboard forecast panels do not call forecast providers directly. They only display EVCC's `tariffSolar_value` metric. This metric exists only when a solar forecast is configured in EVCC, for example through EVCC's `solar` tariff/forecast configuration with Forecast.Solar, Solcast, or Open-Meteo.

If you do not use an EVCC solar forecast, empty forecast panels are expected and are not a VictoriaMetrics or dashboard error. PV, grid, home, and battery panels can still work correctly.

Check whether EVCC writes forecast values to VictoriaMetrics:

```bash
curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=tariffSolar_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/query' \
  --data-urlencode 'query=last_over_time(tariffSolar_value[24h])'
```

Expected result:

- With an EVCC solar forecast: at least one `tariffSolar_value` series and a recent value.
- Without an EVCC solar forecast: no series or an empty result; this is a tolerated optional state for forecast panels.

Configure or fix forecast providers in EVCC, not in the Grafana dashboard. EVCC will then write new `tariffSolar_value` samples, and Grafana will show them automatically.
### Optional Telegraf Probe Write

Run only against a test or intentionally prepared instance:

```bash
curl -i -XPOST 'http://<telegraf-host>:8086/api/v2/write?org=evcc&bucket=evcc&precision=s' \
  -H 'Authorization: Token <listener-token>' \
  --data-binary "evcc_ingest_probe value=1 $(date +%s)"
```

Then search VictoriaMetrics for `evcc_ingest_probe`. This probe is not relevant for production dashboards; it only validates the write path.

## Common Errors

- EVCC still points at the old InfluxDB instead of Telegraf or VictoriaMetrics.
- Telegraf uses `[[outputs.influxdb]]` for VictoriaMetrics and creates a `db` label.
- `omit_hostname = true` is missing and Telegraf creates a `host` label.
- Grafana or EVCC uses `localhost` although the service runs in another container or on another host.
- Firewall or Docker port mapping blocks `8428` or `8086`.
- EVCC web configuration overrides the expected `evcc.yaml` value.
- Dashboard details show only totals or wrong groups: EVCC labels such as `title`, `loadpoint`, or `vehicle` are missing, were renamed historically, or do not match the blocklist regexes.

## Next Step

Once current EVCC raw data arrives in VictoriaMetrics, continue with Grafana:

- install Grafana if you do not already have a suitable instance: [grafana-install-debian-13.md](./grafana-install-debian-13.md) or [grafana-install-docker.md](./grafana-install-docker.md)
- create the Grafana datasource and deploy dashboards: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

If you used this guide only to prepare an InfluxDB migration, go back to [influx-to-vm-migration.md](./influx-to-vm-migration.md) now. Enable the VictoriaMetrics write path only after the final delta import.

## Sources

- [EVCC Influx configuration](https://docs.evcc.io/docs/reference/configuration/influx)
- [EVCC Tariffs and forecasts](https://docs.evcc.io/en/docs/tariffs)
- [EVCC Forecast.Solar](https://docs.evcc.io/en/tariffs/forecast-solar)
- [Telegraf influxdb_v2_listener](https://docs.influxdata.com/telegraf/v1/input-plugins/influxdb_v2_listener/)
- [Telegraf HTTP output](https://docs.influxdata.com/telegraf/v1/output-plugins/http/)
- [Telegraf output data formats](https://docs.influxdata.com/telegraf/v1/data_formats/output/)
