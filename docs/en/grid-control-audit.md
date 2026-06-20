# EVCC Grid-Control Audit To VictoriaMetrics

German version: [grid-control-audit.md](../de/grid-control-audit.md).

This optional guide installs the helper collector used by the Daily Details `Grid control` tab. The normal EVCC/Telegraf live ingest remains unchanged and continues to provide the regular EVCC metrics. The audit collector reads EVCC through read-only API calls, writes additional `evcc_audit_*` metrics to VictoriaMetrics, and keeps a local cumulative CSV file for detected interventions.

The tab is shown only when the selected time range contains either an active external limit or an EVCC GridSession event.

## What The Collector Writes

The collector polls these EVCC endpoints:

- `/api/state`
- `/api/gridsessions`

It writes metrics such as:

- `evcc_audit_hems_effective_max_consumption_power_w`
- `evcc_audit_hems_effective_max_production_power_w`
- `evcc_audit_site_grid_import_power_w`
- `evcc_audit_site_grid_export_power_w`
- `evcc_audit_gridsession_event_start_timestamp_seconds`
- `evcc_audit_minimum_allowed_power_w`
- `evcc_audit_control_group_power_w`

Additionally, the collector writes `AUDIT_DATA_DIR/events/evcc-grid-control-events.csv`. This local CSV contains one row per intervention with start, end, type, status, limit, grid power at start, intervention source, and the EEBUS SKI when EVCC provides it.

Normal EVCC metrics show what happened at the grid connection. These audit metrics additionally show whether EVCC knows about an external limit or control event.

## Install On The VictoriaMetrics Host

GitHub source:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
```

Alternative Forgejo source:

```bash
BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"
```

Install the script and examples:

```bash
sudo mkdir -p /opt/evcc-vm-migration
curl -fsSLo /tmp/collect-evcc-grid-control-audit.py "$BASE/scripts/helper/collect-evcc-grid-control-audit.py"
curl -fsSLo /tmp/evcc-grid-control-audit.env.example "$BASE/scripts/helper/evcc-grid-control-audit.env.example"
curl -fsSLo /tmp/evcc-grid-control-audit.service.example "$BASE/scripts/helper/evcc-grid-control-audit.service.example"

sudo install -m 0755 /tmp/collect-evcc-grid-control-audit.py /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py
sudo install -m 0640 /tmp/evcc-grid-control-audit.env.example /etc/evcc-grid-control-audit.env
sudo install -m 0644 /tmp/evcc-grid-control-audit.service.example /etc/systemd/system/evcc-grid-control-audit.service
```

Edit the config:

```bash
sudo nano /etc/evcc-grid-control-audit.env
```

Minimal example:

```env
EVCC_BASE_URL=http://192.168.1.197:7070
VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus
SITE_ID=home
EVCC_API_POLL_SECONDS=10
HTTP_TIMEOUT_SECONDS=10
AUDIT_DATA_DIR=/var/lib/evcc-grid-control-audit
LOCAL_EVENT_CSV=true
```

When the collector runs directly on the VictoriaMetrics host, `VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus` is usually correct. The local CSV is written to `/var/lib/evcc-grid-control-audit/events/evcc-grid-control-events.csv` by default.

## Optional: Name Controllable Groups

Set `EVCC_14A_CONTROL_GROUPS` when you want the dashboard to show how much power each controllable group currently uses.

Example for two loadpoints and battery grid charging:

```env
EVCC_14A_CONTROL_GROUPS=lp|Loadpoints|loadpoints|1+2;battery|Battery grid charge|battery_grid_charge|
```

Syntax:

```text
id|Display name|Kind|Members;id2|Display name|Kind|Members
```

Supported kinds:

- `loadpoints`: members are EVCC loadpoint numbers, for example `1+2`
- `battery_grid_charge`: members stay empty

For the minimum-power calculation, the collector uses the number of configured groups by default. Override this explicitly when needed:

```env
EVCC_14A_CONTROL_UNITS=2
EVCC_14A_MIN_POWER_BASE_W=4200
EVCC_14A_ADDITIONAL_UNIT_FACTOR=0.4
```

## One-Shot Test

Before enabling the service, run one collector cycle:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py \
  --evcc-url http://192.168.1.197:7070 \
  --vm-write-url http://127.0.0.1:8428/api/v1/import/prometheus \
  --site home \
  --once
```

Print metrics without writing to VictoriaMetrics or the local CSV:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py \
  --evcc-url http://192.168.1.197:7070 \
  --site home \
  --once \
  --dry-run
```

## Enable The Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now evcc-grid-control-audit.service
sudo systemctl status evcc-grid-control-audit.service
```

Logs:

```bash
journalctl -u evcc-grid-control-audit.service -f
```

## Grafana Datasource

If the collector writes to the same VictoriaMetrics instance as the EVCC data, no additional dashboard deployer setting is needed. If you use a separate VictoriaMetrics instance for audit data, set this during dashboard deployment:

```env
GRAFANA_DS_VM_EVCC_AUDIT_UID=<datasource_uid>
```
