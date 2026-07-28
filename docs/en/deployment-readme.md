# Dashboard Deployment Quick Start

This is the short deployment reference. Before dashboard deployment, current EVCC raw data must arrive in VictoriaMetrics; see [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md). For the full walkthrough, use [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). For every config option, use [vm-dashboard-install.md](./vm-dashboard-install.md).

## Recommended Path

The examples use GitHub as `BASE`. For a local Forgejo repository, set `BASE` to the raw repository root instead, typically `http://<server:port>/<owner>/<repo>/raw/branch/main`.

Linux / Raspberry Pi:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo example:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-python.sh "$BASE/scripts/deploy-python.sh"
curl -fsSLo vm-dashboard-install.env.example "$BASE/scripts/vm-dashboard-install.env.example"
chmod +x deploy-python.sh
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Windows / PowerShell:

```powershell
$Base = "https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo example:
# $Base = "http://<server:port>/<owner>/<repo>/raw/branch/main"

Invoke-WebRequest "$Base/scripts/deploy.ps1" -OutFile deploy.ps1
Invoke-WebRequest "$Base/scripts/vm-dashboard-install.env.example" -OutFile vm-dashboard-install.env.example
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimal `vm-dashboard-install.env`:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<your_service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
GRAFANA_DS_VM_EVCC_AUDIT_UID=   # optional: separate EVCC-SmartMeterCtrl/§14a audit datasource
# optional: GRAFANA_THEME=dark or GRAFANA_THEME=light
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
PURGE=false
PURGE_ONLY=false
```

Grafana 13.0.1 or newer is required. The deployers always install the tab-navigation dashboards; the legacy row-based deploy path and dashboard set selection are no longer available. The deployment default is `DASHBOARD_LANGUAGE=de` with `DASHBOARD_VARIANT=gen`; `DASHBOARD_VARIANT=orig` intentionally remains English.

## Source And Settings

`DASHBOARD_SOURCE_MODE` decides where dashboard JSON files are imported from:

```env
DASHBOARD_SOURCE_MODE=github
# or: DASHBOARD_SOURCE_MODE=rawurl
# or: DASHBOARD_SOURCE_MODE=localdir
```

For a self-hosted raw endpoint use the repository root raw URL pattern:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Common dashboard variable overrides can also be set in `vm-dashboard-install.env`:

```env
DASHBOARD_INSTALLED_WATT_PEAK=22
DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM=6
DASHBOARD_FUEL_COST_PER_L=1.75
DASHBOARD_STORAGE_CAPACITY_WH=9500
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_FILTER_CONSUMER_BLOCKLIST=^none$
DASHBOARD_CONSUMER_LEGACY_EXT_REGEX="^(Dishwasher|Washing Machine)$"
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_EVCC_URL=http://home:7070/#/
# Optional external portal button. Without DASHBOARD_PORTAL_URL no portal button is shown.
# DASHBOARD_PORTAL_TITLE=Portal
# DASHBOARD_PORTAL_URL=https://example.invalid/portal
```

Sum or parent meters can be removed from both the display and `Other` with the blocklist for their Consumer, EXT, or AUX role. Use only one level of each meter hierarchy; see [Excluding Sum And Parent Meters From Home Attribution](./migration-troubleshooting.md#excluding-sum-and-parent-meters-from-home-attribution) for a concrete example.

After an EXT-to-Consumer role change, `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` must contain exactly the same former end consumers as `consumer_legacy_ext_regex` in the rollup configuration. This keeps historical raw data visible in `Today - Details`; current Consumer samples take precedence during overlap. The `^$` default disables the fallback. Never include distribution or sum meters.

The full option list is in [vm-dashboard-install.md](./vm-dashboard-install.md) and the commented template is `vm-dashboard-install.env.example`. Define each env key only once; duplicate keys are rejected.

## Run

Linux:

```bash
./deploy-python.sh
```

Windows:

```powershell
.\deploy.ps1
```

The deployer prints a preflight summary and asks for confirmation before importing dashboards.

## Verify

After deployment:

- Grafana folder `EVCC` exists.
- `Today` shows raw data.
- `Month`, `Year`, and `All-time` show `evcc_*` rollup data.
- No panel shows datasource or query errors.

## Optional Bash Deployer

`deploy-bash.sh` is still supported for Linux systems that prefer Bash and `jq`:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo example:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-bash.sh "$BASE/scripts/deploy-bash.sh"
chmod +x deploy-bash.sh
sudo apt install -y jq
./deploy-bash.sh
```

For beginners, prefer `deploy-python.sh` because the migration and rollup path already require Python.
