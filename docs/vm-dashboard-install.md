# VM Dashboard Install

For a simpler first-time walkthrough, start here:

- [deployment-readme.md](./deployment-readme.md)

This document describes the end-user deployment path for the VictoriaMetrics dashboards in more detail.

## Goal

- no Node.js required
- simple first-deploy defaults
- import both dashboards and Grafana library panels

## Recommended Grafana access

Use a Grafana API token or service-account token with permissions to:

- create and update folders
- create and update dashboards
- create and update library panels
- delete dashboards and library panels when `PURGE=true`

This is simpler and safer than automating a username and password.

## Default behavior

The deployer defaults to the generated dashboard set:

- source repo: `endurance1968/evcc-grafana-dashboards`
- ref: `main`
- language: `en`
- variant: `gen`
- folder UID/title: `evcc` / `EVCC`
- datasource UID: `vm-evcc`
- purge before import: `false`

Default is `PURGE=false`, so existing dashboards stay in place unless you explicitly choose to delete them first.

When `PURGE=true`, the deployer deletes only:

- the dashboards whose `uid` is present in the six VM dashboard JSON files
- the library panels whose `uid` is referenced under `__elements` in those same files

For most first deployments you only need to set:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`

The deployer can optionally set the hidden dashboard filter variables during deployment.

That means:

- colors come from the checked-in dashboard JSON files
- dashboard variable defaults can come either from the checked-in dashboard JSON files or from optional deploy-time overrides
- user-specific changes can be done in Grafana after import, by re-running the deployer with dashboard overrides, or by deploying from a local dashboard directory

## Config file

Copy:

- `vm-dashboard-install.env.example`

to:

- `vm-dashboard-install.env`

and set at least:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`

Optional values:

- `GRAFANA_DS_VM_EVCC_UID`
- `GRAFANA_FOLDER_UID`
- `GRAFANA_FOLDER_TITLE`
- `DASHBOARD_LANGUAGE`
- `DASHBOARD_VARIANT`
- `DASHBOARD_SOURCE_MODE=github|local`
- `DASHBOARD_LOCAL_DIR`
- `GITHUB_REPO`
- `GITHUB_REF`
- `PURGE`

Optional dashboard variable overrides:

- `DASHBOARD_FILTER_PEAK_POWER_LIMIT`
- `DASHBOARD_ENERGY_SAMPLE_INTERVAL`
- `DASHBOARD_TARIFF_PRICE_INTERVAL`
- `DASHBOARD_INSTALLED_WATT_PEAK`
- `DASHBOARD_FILTER_LOADPOINT_BLOCKLIST`
- `DASHBOARD_FILTER_EXT_BLOCKLIST`
- `DASHBOARD_FILTER_AUX_BLOCKLIST`
- `DASHBOARD_FILTER_VEHICLE_BLOCKLIST`
- `DASHBOARD_EVCC_URL`
- `DASHBOARD_PORTAL_TITLE`
- `DASHBOARD_PORTAL_URL`

Example:

```env
DASHBOARD_FILTER_PEAK_POWER_LIMIT=30000
DASHBOARD_ENERGY_SAMPLE_INTERVAL=30s
DASHBOARD_TARIFF_PRICE_INTERVAL=15m
DASHBOARD_INSTALLED_WATT_PEAK=20
DASHBOARD_FILTER_EXT_BLOCKLIST=^none$
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_EVCC_URL=http://home:7070/#/
DASHBOARD_PORTAL_TITLE=Solarman
DASHBOARD_PORTAL_URL=https://globalhome.solarmanpv.com/plant/infos/data
```

All of these values are optional. They let you set hidden dashboard variables and the header buttons during deployment without editing the dashboard JSON files manually. `DASHBOARD_INSTALLED_WATT_PEAK` is the installed PV peak in kWp and is used for the specific-yield panels. The behavior is identical in `deploy.ps1`, `deploy-python.sh`, and `deploy-bash.sh`.

The dashboards include a small visible `Build` variable in the header. Hover over it to see the deployment timestamp, selected language/variant, and source ref.

Runtime overrides are also available:

- PowerShell: `-url`, `-token`, `-purge`
- Python shell deployer: `--url`, `--token`, `--purge`
- Bash-only deployer: `--url`, `--token`, `--purge`

Those values override the config file for a single run. The link/button values update the hidden dashboard variables used by the `EVCC` and portal buttons in the header.

Backward compatibility: the old names `DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL` and `DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL` are still accepted as aliases.

## User customization

The deployer is intentionally import-only.

Recommended customization paths:

- change dashboard variables in Grafana and save the dashboard
- or deploy from a local dashboard directory via `DASHBOARD_SOURCE_MODE=local`

The deployer intentionally does not rewrite:

- colors
- panel settings

The only supported deploy-time customization is the set of hidden dashboard filter variables listed above.

## Windows

PowerShell only, no Node.js required:

```powershell
.\deploy.ps1
```

With an explicit config file:

```powershell
.\deploy.ps1 -config .\vm-dashboard-install.env
```

Or directly with the key values:

```powershell
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purge false
```

## Linux / Raspberry Pi with the Python shell deployer

This variant uses `python3`, which is usually already present.

If not:

```bash
sudo apt install python3
```

Run:

```bash
sh ./deploy-python.sh
```

With an explicit config file:

```bash
sh ./deploy-python.sh --config ./vm-dashboard-install.env
```

Or directly with the key values:

```bash
sh ./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge false
```

## Linux / Raspberry Pi with the Bash-only deployer

This variant needs `jq`:

```bash
sudo apt install jq
```

Run:

```bash
sh ./deploy-bash.sh
```

With an explicit config file:

```bash
sh ./deploy-bash.sh --config ./vm-dashboard-install.env
```

Or directly with the key values:

```bash
sh ./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge false
```

## Maintainer note

The Node.js scripts under `scripts/test` remain the maintainer workflow for:

- localization generation
- test-folder imports
- screenshot automation
- smoke checks

End users should prefer the deploy scripts above.







