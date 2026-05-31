# Set Up Grafana With VictoriaMetrics Dashboards

Before running commands, review the central requirements overview: [system-requirements.md](./system-requirements.md).

This is the canonical end-user deployment guide. It covers:

- creating the VictoriaMetrics datasource in Grafana
- creating a Grafana service-account token
- deploying the EVCC dashboards
- updating dashboards later

If VictoriaMetrics data and rollups are not ready yet, finish [influx-to-vm-migration.md](./influx-to-vm-migration.md) first.

## Target State

Grafana should have:

- a VictoriaMetrics datasource with UID `vm-evcc`
- a folder called `EVCC`
- the EVCC dashboard set deployed into that folder

`Today*` dashboards read raw VictoriaMetrics data. `Month`, `Year`, and `All-time` need the generated `evcc_*` rollups.

## Prerequisites

Required:

- running Grafana instance
- running VictoriaMetrics instance
- Grafana service-account token
- internet access to GitHub for the default deploy source

Recommended:

- Grafana 13.0.1 or newer with `DASHBOARD_SET=tabs`
- Linux deploys use `deploy-python.sh` as the primary path
- Windows deploys use `deploy.ps1`

Linux package minimum:

```bash
sudo apt update
sudo apt install -y curl python3
```

`deploy-bash.sh` remains available for systems that prefer Bash + `jq`, but it is not the primary beginner path.

## 1. Create The VictoriaMetrics Datasource

In Grafana:

1. Open `Connections` or `Administration`.
2. Open `Data sources`.
3. Add a VictoriaMetrics datasource.
4. Set URL to `http://<your-vm-host>:8428`.
5. Set access to `Server` or `Proxy`.
6. Set UID to `vm-evcc`.
7. Click `Save & test`.

If the VictoriaMetrics datasource plugin is not available, install it first and restart Grafana.

On a Debian package install, use:

```bash
sudo grafana cli \
  --homepath=/usr/share/grafana \
  --pluginsDir /var/lib/grafana/plugins \
  plugins install victoriametrics-metrics-datasource
sudo systemctl restart grafana-server
```

Docker note: if Grafana and VictoriaMetrics run as separate Docker containers, `localhost` inside Grafana points to the Grafana container, not to VictoriaMetrics. On Docker Desktop, use a datasource URL such as `http://host.docker.internal:8428`. On a user-defined Docker network, use the VictoriaMetrics container name, for example `http://victoriametrics:8428`.

## 2. Create A Service-Account Token

In Grafana:

1. Open `Administration`.
2. Open `Users and access`.
3. Open `Service accounts`.
4. Create `evcc-dashboard-deployer`.
5. Add a service-account token.
6. Copy the token immediately.

For a simple local deployment, `Admin` in the current organization is usually enough. Grafana 12 and 13 both support service-account tokens for this deploy path.

## 3. Download The Deployer

Linux / Raspberry Pi:

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

Windows / PowerShell:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

Optional Bash deployer:

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
chmod +x deploy-bash.sh
sudo apt install -y jq
```

## 4. Create The Config File

Linux:

```bash
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Windows:

```powershell
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimal config:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<your_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
DASHBOARD_SET=tabs
PURGE=false
PURGE_ONLY=false
```

Personal dashboard variable overrides can be kept in the same env file. For example:

```env
DASHBOARD_INSTALLED_WATT_PEAK=22
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^Altherma-3$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_EVCC_URL=http://192.168.1.197:7070/#/
DASHBOARD_PORTAL_TITLE=VRM
DASHBOARD_PORTAL_URL=https://vrm.victronenergy.com/installation/795774/dashboard
```

If the dashboard files should come from the local Forgejo mirror instead of GitHub, add:

```env
DASHBOARD_RAW_BASE_URL=http://192.168.1.222:3000/olaf-krause/evcc-grafana-dashboards/raw/branch/main
```

Use `DASHBOARD_SET=default` if Grafana is older than 13.0.1 or if you explicitly prefer the classic row-based dashboards.

## 5. Run The Deployment

Linux:

```bash
./deploy-python.sh
```

Windows:

```powershell
.\deploy.ps1
```

The deployer shows a preflight summary and asks for confirmation before writing.

Direct one-time commands are also supported:

```bash
./deploy-python.sh --url http://<your-grafana-ip>:3000 --token <your_token> --purge false --dashboard-set tabs
```

```powershell
.\deploy.ps1 -url http://<your-grafana-ip>:3000 -token <your_token> -purge false -dashboardset tabs
```

## What The Deployer Does

- verifies Grafana access
- resolves the selected dashboard set from `dashboards/deploy-manifest.json`
- shows which dashboards will be imported
- updates embedded library panels before dashboard import
- imports dashboards into the `EVCC` folder

With `PURGE=false`, existing dashboards are overwritten by UID and library panels are updated in place.
With `PURGE_ONLY=false`, the deployer stays in normal import mode.

With `PURGE=true`, known EVCC dashboards are deleted first and then recreated. Use it only when you intentionally want a full rebuild.
With `PURGE_ONLY=true`, known EVCC dashboards and referenced EVCC library panels are deleted, then the deployer stops without importing anything.

## 6. Verify The Result

In Grafana:

- the `EVCC` folder exists
- `Today` shows current raw data
- `Today - Details` opens without datasource errors
- `Month`, `Year`, and `All-time` show rollup values
- the dashboard header build variable shows the selected language, variant, source ref, and deployment time

If `Today` works but long-range dashboards are empty, rollups are missing. Return to [influx-to-vm-migration.md](./influx-to-vm-migration.md).

## Update Later

Normal update:

```bash
./deploy-python.sh --purge false
```

Windows:

```powershell
.\deploy.ps1 -purge false
```

Full rebuild:

```bash
./deploy-python.sh --purge true
```

Windows:

```powershell
.\deploy.ps1 -purge true
```

## Common Errors

### `Missing GRAFANA_API_TOKEN`

Set `GRAFANA_API_TOKEN` in `vm-dashboard-install.env` or pass `--token` / `-token`.

### 403 / Permission denied

The service account lacks permissions to manage dashboards, folders, or library panels.

### 401 / `Invalid API key`

Create a fresh Grafana service-account token and set:

```env
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<new_service_account_token>
```

### Dashboards imported, but empty

Check:

- datasource URL points to VictoriaMetrics
- datasource UID matches `GRAFANA_DS_VM_EVCC_UID`
- raw data exists for `Today*`
- `evcc_*` rollups exist for long-range dashboards

## References

- Quick deploy reference: [deployment-readme.md](./deployment-readme.md)
- Full deployer option reference: [vm-dashboard-install.md](./vm-dashboard-install.md)
- Migration checklist: [migration-checklist.md](./migration-checklist.md)
