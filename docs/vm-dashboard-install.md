# VM Dashboard Install Reference

For a first-time walkthrough, start with [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). For a short command-only version, use [deployment-readme.md](./deployment-readme.md).

This document is the deployer option reference.

## Deployer Goals

- no Node.js required for end users
- import dashboards and embedded Grafana library panels
- support Windows PowerShell, portable POSIX shell with Python, and Bash + `jq`
- keep `PURGE=false` and `PURGE_ONLY=false` as the safe default

## Default Behavior

Defaults:

- source repo: `endurance1968/evcc-grafana-dashboards`
- ref: `main`
- language: `en`
- variant: `gen`
- dashboards: fixed Grafana 13 tab-navigation list from `dashboards/deploy-manifest.json`
- folder UID/title: `evcc` / `EVCC`
- datasource UID: `vm-evcc`
- purge before import: `false`

Grafana 13.0.1 or newer is required. Dashboard set selection is no longer supported; the deployers always use the fixed tab-navigation file list from `dashboards/deploy-manifest.json`.

## Required Config

Copy `vm-dashboard-install.env.example` to `vm-dashboard-install.env` and set at least:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
```

`GRAFANA_API_TOKEN` is the preferred setting for Grafana 13 service-account tokens. `GRAFANA_SERVICE_ACCOUNT_TOKEN` is accepted as an alias if `GRAFANA_API_TOKEN` is empty.

Local recovery fallback when basic auth is enabled:

```env
GRAFANA_AUTH_MODE=basic
GRAFANA_USER=admin
GRAFANA_PASSWORD=<admin_password>
```

## Dashboard Selection

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Values:

- `DASHBOARD_LANGUAGE`: `en`, `de`, `fr`, `es`, `it`, `nl`, `hi`, `zh`
- `DASHBOARD_VARIANT`: `gen` for generated localized dashboards, `orig` for original source dashboards

The deployable file lists are defined in `dashboards/deploy-manifest.json`.

## Source Selection

Default GitHub source:

```env
DASHBOARD_SOURCE_MODE=github
GITHUB_REPO=endurance1968/evcc-grafana-dashboards
GITHUB_REF=main
```

Local Forgejo or another raw file endpoint can be used without changing the source mode. The value must point at the repository root raw path; the deployer appends paths such as `dashboards/deploy-manifest.json` and `dashboards/translation/de/...`:

```env
DASHBOARD_SOURCE_MODE=github
DASHBOARD_RAW_BASE_URL=http://192.168.1.222:3000/olaf-krause/evcc-grafana-dashboards/raw/branch/main
```

Local checkout source:

```env
DASHBOARD_SOURCE_MODE=local
DASHBOARD_LOCAL_DIR=/path/to/evcc-grafana-dashboards/dashboards/translation/de
```

## Folder And Datasource

```env
GRAFANA_FOLDER_UID=evcc
GRAFANA_FOLDER_TITLE=EVCC
GRAFANA_DS_VM_EVCC_UID=vm-evcc
```

If your datasource UID is not `vm-evcc`, set `GRAFANA_DS_VM_EVCC_UID` before deployment.

## Update Behavior

```env
PURGE=false
PURGE_ONLY=false
```

`PURGE=false` overwrites known dashboards by UID and updates referenced library panels in place.
`PURGE_ONLY=false` keeps the deployer in normal import mode.

```env
PURGE=true
```

`PURGE=true` deletes known EVCC dashboards first and then recreates dashboards and embedded library panels. Use this for a deliberate full rebuild.

```env
PURGE_ONLY=true
```

`PURGE_ONLY=true` deletes known EVCC dashboards and referenced EVCC library panels, then stops without importing anything. Use this only when you intentionally want to remove the deployed dashboards from Grafana.

## Optional Dashboard Variable Overrides

These values let you set hidden dashboard variables and header buttons without editing dashboard JSON files:

```env
DASHBOARD_FILTER_PEAK_POWER_LIMIT=30000
DASHBOARD_ENERGY_SAMPLE_INTERVAL=30s
DASHBOARD_TARIFF_PRICE_INTERVAL=15m
DASHBOARD_INSTALLED_WATT_PEAK=20
DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM=6
DASHBOARD_FUEL_COST_PER_L=1.75
DASHBOARD_PV_PURCHASE_PRICE=24884
DASHBOARD_BATTERY_PURCHASE_PRICE=5500
DASHBOARD_RUNNING_COSTS_YEARLY=100
DASHBOARD_STORAGE_CAPACITY_WH=9500
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_EVCC_URL=http://home:7070/#/
DASHBOARD_PORTAL_TITLE=Solarman
DASHBOARD_PORTAL_URL=https://globalhome.solarmanpv.com/plant/infos/data
```

Quote regex values containing `|`, `(`, `)`, spaces, or non-ASCII characters so the Bash deployer can source the env file safely.

Backward-compatible aliases are still accepted:

- `DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL`
- `DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL`
- `DASHBOARD_ICE_CONSUMPTION_L_PER_100KM` for `DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM`
- `DASHBOARD_FUEL_PRICE_PER_L` for `DASHBOARD_FUEL_COST_PER_L`
- `DASHBOARD_BATTERY_CAPACITY_WH` for `DASHBOARD_STORAGE_CAPACITY_WH`

Every deployed dashboard includes a small visible `Build` variable in the header. Hover over it to see deployment timestamp, selected language/variant, and source ref.

## Runtime Arguments

PowerShell:

```powershell
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purge false
# Delete only, no re-import:
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purgeonly true
```

Portable shell with Python:

```bash
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge false
# Delete only, no re-import:
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Bash + `jq`:

```bash
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge false
# Delete only, no re-import:
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Runtime arguments override the config file for that run.

## User Customization

The deployer is intentionally import-only. Recommended customization paths:

- change dashboard variables in Grafana and save the dashboard
- set deploy-time dashboard variable overrides in `vm-dashboard-install.env`
- deploy from a local dashboard directory with `DASHBOARD_SOURCE_MODE=local`

The deployer intentionally does not rewrite colors or arbitrary panel settings.

## Maintainer Note

Node.js scripts under `scripts/test` remain the maintainer workflow for localization generation, test-folder imports, screenshot automation, and smoke checks. End users should prefer the deploy scripts above.