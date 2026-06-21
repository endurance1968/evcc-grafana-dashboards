# VM Dashboard Install Reference

For a first-time walkthrough, start with [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). For a short command-only version, use [deployment-readme.md](./deployment-readme.md).

This document is the deployer option reference.

## Deployer Goals

- no Node.js required for end users
- import dashboards with inline panels; no Grafana library panels are created
- support Windows PowerShell, portable POSIX shell with Python, and Bash + `jq`
- keep `PURGE=false` and `PURGE_ONLY=false` as the safe default

## Default Behavior

Defaults:

- source repo: `endurance1968/evcc-grafana-dashboards`
- ref: `main`
- language: `de`
- variant: `gen`
- dashboards: fixed Grafana 13 tab-navigation list from `dashboards/deploy-manifest.json`
- folder UID/title: `evcc` / `EVCC`
- datasource UID: `vm-evcc`
- optional audit datasource UID for grid-control audit/14a: empty, falls back to `vm-evcc`
- purge before import: `false`

Grafana 13.0.1 or newer is required. Dashboard set selection is no longer supported; the deployers always use the fixed tab-navigation file list from `dashboards/deploy-manifest.json`.

## Required Config

Copy `vm-dashboard-install.env.example` to `vm-dashboard-install.env` and set at least:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
# Optional, only when grid-control audit metrics use a separate datasource:
GRAFANA_DS_VM_EVCC_AUDIT_UID=
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
- `DASHBOARD_VARIANT`: `gen` for generated localized dashboards, `orig` for the original English source dashboards. `orig` always stays English and uses `dashboards/original/en` regardless of `DASHBOARD_LANGUAGE`.

The deployable file lists are defined in `dashboards/deploy-manifest.json`.

## Source Selection

`DASHBOARD_SOURCE_MODE` selects exactly where dashboard JSON files are loaded from. The deployer validates the variables required by the selected mode and ignores source variables from the other modes. Define each env key only once; duplicate keys are rejected because shell-style env files would otherwise let the last assignment win silently.

GitHub source:

```env
DASHBOARD_SOURCE_MODE=github
GITHUB_REPO=endurance1968/evcc-grafana-dashboards
GITHUB_REF=main
```

Raw URL source. The value must point at the repository root raw path, typically `<server:port>/<reponame>/raw/branch/main`; the deployer appends paths such as `dashboards/deploy-manifest.json`, `dashboards/translation/de/...`, or for `DASHBOARD_VARIANT=orig` `dashboards/original/en/...`:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Local dashboard directory source. The directory must contain the seven deployable dashboard JSON files for the selected language/variant; the deployer does not read a repository manifest in this mode:

```env
DASHBOARD_SOURCE_MODE=localdir
DASHBOARD_LOCAL_DIR=/path/to/evcc-grafana-dashboards/dashboards/translation/de
```

## Folder And Datasource

```env
GRAFANA_FOLDER_UID=evcc
GRAFANA_FOLDER_TITLE=EVCC
GRAFANA_DS_VM_EVCC_UID=vm-evcc
# Optional, only when grid-control audit metrics use a separate datasource:
GRAFANA_DS_VM_EVCC_AUDIT_UID=
```

If your datasource UID is not `vm-evcc`, set `GRAFANA_DS_VM_EVCC_UID` before deployment.

The Daily Details tab for external grid/14a control uses optional `evcc_audit_*` metrics from the [grid-control audit collector](./grid-control-audit.md). By default the deployer looks for these metrics in the same datasource as EVCC. If the audit collector writes to a separate VictoriaMetrics instance, set `GRAFANA_DS_VM_EVCC_AUDIT_UID` to that Grafana datasource UID. The tab stays visible; without audit metrics the panels show no data. The table is filled from `evcc_audit_gridsession_event_start_timestamp_seconds`; fields such as start, end, type, status, and limit come from that metric's labels.

### Optionally Set The Grafana Theme

The deployer can set the Grafana organization preference for the theme:

```env
GRAFANA_THEME=dark
# or
GRAFANA_THEME=light
```

Accepted values are `dark`, `light`, `bright` as an alias for `light`, and `default` to use Grafana's default again. Leave it empty to avoid changing Grafana preferences. Personal user preferences in Grafana can still override the organization preference. In `PURGE_ONLY` mode the theme is not changed.

## Update Behavior

```env
PURGE=false
PURGE_ONLY=false
```

`PURGE=false` overwrites known dashboards by UID. Dashboards use inline panels; library panels are not created or updated.
`PURGE_ONLY=false` keeps the deployer in normal import mode.

```env
PURGE=true
```

`PURGE=true` deletes known EVCC dashboards first and then imports them again. Use this for a deliberate full rebuild.

```env
PURGE_ONLY=true
```

`PURGE_ONLY=true` deletes known EVCC dashboards, then stops without importing anything. Use this only when you intentionally want to remove the deployed dashboards from Grafana.

## Optional Dashboard Variable Overrides

These values let you set hidden dashboard variables and optional header buttons without editing dashboard JSON files:

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
# Optional external portal button. Without DASHBOARD_PORTAL_URL no portal button is shown.
# DASHBOARD_PORTAL_TITLE=Portal
# DASHBOARD_PORTAL_URL=https://example.invalid/portal
```

Quote regex values containing `|`, `(`, `)`, spaces, or non-ASCII characters so the Bash deployer can source the env file safely.

The blocklist and heat-pump values are regexes against existing EVCC labels. They do not rename series and do not delete data; they only control what the dashboards show or filter out of totals. `^none$` is the recommended value when nothing should be filtered. If detail panels look empty or wrongly grouped, first check the EVCC labels in [migration-troubleshooting.md#business-labels-titles-and-blocklists](./migration-troubleshooting.md#business-labels-titles-and-blocklists).

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
- deploy from a local dashboard directory with `DASHBOARD_SOURCE_MODE=localdir`

The deployer intentionally does not rewrite colors or arbitrary panel settings.
