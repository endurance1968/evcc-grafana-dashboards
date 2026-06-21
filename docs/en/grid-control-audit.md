# EVCC Grid-Control Audit To VictoriaMetrics

German version: [grid-control-audit.md](../de/grid-control-audit.md).

This optional guide installs the helper collector used by the Daily Details `Grid control` tab. The normal EVCC/Telegraf live ingest remains unchanged and continues to provide the regular EVCC metrics. The audit collector reads EVCC through read-only API calls, writes additional `evcc_audit_*` metrics to VictoriaMetrics, and keeps a local cumulative CSV file for detected interventions.

The tab stays visible so grid-control data can be checked explicitly. Without audit metrics the panels show no data; once the collector writes values or GridSession events, limits, reserves, controllable groups, and the event table are populated.

## What The Collector Writes

The collector polls these EVCC endpoints:

- `/api/state`
- `/api/gridsessions`

In normal operation it writes only additional audit and event metrics that are not already covered by the normal EVCC/Telegraf ingest:

- `evcc_audit_hems_effective_max_consumption_power_w`
- `evcc_audit_hems_effective_max_production_power_w`
- `evcc_audit_gridsession_event_start_timestamp_seconds`
- `evcc_audit_minimum_allowed_power_w`
- `evcc_audit_control_group_power_w`
- `evcc_audit_control_units`
- `evcc_audit_collector_up`
- `evcc_audit_collector_last_success_timestamp_seconds`

Grid power, home consumption, battery values, and raw loadpoint values are not stored again as long-term `evcc_audit_*` copies. The dashboards use the regular EVCC metrics such as `gridPower_value` for those values; the collector only uses them internally for calculations.


Additionally, the collector writes `AUDIT_DATA_DIR/events/evcc-grid-control-events.csv`. This local CSV contains one row per intervention with start, end, type, status, limit, grid power at start, intervention source, and the EEBUS SKI when EVCC provides it.

The Grafana table does not read directly from EVCC and does not read the CSV directly. The intended path is: EVCC API -> collector -> local CSV + VictoriaMetrics -> Grafana. When the local CSV is enabled, the collector keeps that file as the local event history and normally writes new or changed EVCC events plus a short replay window from the local CSV as `evcc_audit_gridsession_event_*` metrics to VictoriaMetrics. The default window is `EVENT_REPLAY_LOOKBACK_DAYS=8`, keeping the 7-day Grafana table populated after a VictoriaMetrics restart without re-importing the full history on every poll. If VictoriaMetrics was rebuilt or event metrics are missing, intentionally replay the full CSV with `REPLAY_EVENTS=true` or `--replay-events`.

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
REPLAY_EVENTS=false
```

When the collector runs directly on the VictoriaMetrics host, `VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus` is usually correct. The local CSV is written to `/var/lib/evcc-grid-control-audit/events/evcc-grid-control-events.csv` by default.

## Control Event Source

The `EVCC control events` table uses the source in this order:

1. source from the EVCC event itself, if `/api/gridsessions` exposes it
2. EVCC HEMS configuration from `/api/state`, for example `hems.config.type=eebus`
3. optional fallback from `EVCC_14A_INTERVENTION_SOURCE`

The EVCC event label `type` stays unchanged and still describes `production` or `consumption`. It is not the technical source. If your EVCC version does not expose the HEMS configuration via `/api/state`, set the fallback explicitly:

```env
EVCC_14A_INTERVENTION_SOURCE=EEBUS
# Alternatives: Relay, HEMS, FNN
```

## Optional: Name Controllable Groups

`EVCC_14A_CONTROL_GROUPS` describes only the groups that should be shown as controllable in the `Grid control` tab. The collector does not infer groups automatically from EVCC names. If a loadpoint or heat pump is not actually controllable, do not list it here.

Example for two loadpoints as one combined group, one heat pump represented as an EVCC loadpoint, and battery grid charging:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Loadpoints|loadpoints|Carport Corner+Carport Stairs;wp1|Heat pump|heat_pump|Heat pump;battery|Battery grid charge|battery_grid_charge|
```

Syntax:

```text
id|display name|kind|members;id2|display name|kind|members2
```

Supported kinds:

- `loadpoint` / `loadpoints`: members are visible EVCC loadpoint names, for example `Carport Corner`, or optional EVCC loadpoint numbers like `1`. Combine multiple members with `+`.
- `heat_pump`: members are visible EVCC loadpoint names for heat pumps represented as EVCC loadpoints
- `battery_grid_charge`: members stay empty

For the minimum-power calculation, the collector uses the number of configured groups by default. This is only a technical default. The relevant value is how many controllable consumption units the grid operator or electrical installation actually treats as controllable.

If two loadpoints are controlled together and count as one controllable unit from the grid side, configure them as one group and set the unit count explicitly to `1`:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Loadpoints|loadpoints|Carport Corner+Carport Stairs
EVCC_14A_CONTROL_UNITS=1
```

If the same two loadpoints count as two separately controllable consumption units, the dashboard can still show them as one combined group; set the legal unit count to `2`:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Loadpoints|loadpoints|Carport Corner+Carport Stairs
EVCC_14A_CONTROL_UNITS=2
```

The minimum-power value is calculated from your configuration and is not legally binding evidence. The default is `EVCC_14A_MIN_POWER_MODE=ems`. The collector then uses the GZF table for EMS control: one unit 4.2 kW, two units 7.56 kW, three units 10.5 kW. For direct per-unit control, set `direct`; the collector then uses 4.2 kW per unit. If the grid operator or installer provides a concrete value, set it directly:

```env
EVCC_14A_MIN_POWER_MODE=ems
# Alternative: direct
# EVCC_14A_MIN_POWER_OVERRIDE_W=10500
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
