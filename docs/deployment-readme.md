# Deployment README

This guide is intended for the first dashboard deployment.

## Prerequisites

You need:

- a running Grafana instance
- a working VictoriaMetrics datasource in Grafana
- a Grafana service-account token
- internet access to GitHub

On Linux or Raspberry Pi you additionally need:

- for `deploy-python.sh`: `curl` and `python3`
- for `deploy-bash.sh`: `bash`, `curl`, and `jq`

If something is missing:

```bash
sudo apt update
sudo apt install -y curl python3 jq
```

## 1. Download the deployer and example config

### Linux / Raspberry Pi with the Python deployer

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

### Linux / Raspberry Pi with the Bash-only deployer

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-bash.sh
```

### Windows / PowerShell

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

## 2. Verify the datasource in Grafana

In Grafana:

1. Open `Connections` or `Administration`
2. Open `Data sources`
3. Make sure the VictoriaMetrics datasource exists
4. Note its UID

If you use the default UID, it is usually:

```text
vm-evcc
```

## 3. Create a Grafana service-account token

In Grafana:

1. Open `Administration`
2. Open `Users and access`
3. Open `Service accounts`
4. Click `Add service account`
5. Create something like `evcc-dashboard-installer`
6. Open the service account
7. Click `Add service account token`
8. Give it a name such as `installer`
9. Click `Generate token`
10. Copy the token immediately

For a simple local installation, `Admin` in the current organization is usually enough.

## 4. Quick start

For a first run, URL and token are normally enough. `purge` controls whether existing EVCC dashboards are deleted before import.

### Linux / Raspberry Pi with the Python deployer

```bash
./deploy-python.sh --url http://<your-grafana-ip>:3000 --token <your_token> --purge false
```

### Linux / Raspberry Pi with the Bash-only deployer

```bash
./deploy-bash.sh --url http://<your-grafana-ip>:3000 --token <your_token> --purge false
```

### Windows

```powershell
./deploy.ps1 -url http://<your-grafana-ip>:3000 -token <your_token> -purge false
```

## 5. Optional: config file

If you do not want to pass URL and token every time, copy:

- `vm-dashboard-install.env.example`

to:

- `vm-dashboard-install.env`

Minimal content:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_API_TOKEN=<your_token>
```

Optional dashboard filter overrides in `vm-dashboard-install.env`:

```env
DASHBOARD_FILTER_PEAK_POWER_LIMIT=30000
DASHBOARD_ENERGY_SAMPLE_INTERVAL=30s
DASHBOARD_TARIFF_PRICE_INTERVAL=15m
DASHBOARD_FILTER_EXT_BLOCKLIST=.*Car.*|.*Haupt.*
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
```

All of these values are optional. They are applied when you run the deployer again later, so you can change the hidden dashboard filter defaults without editing the JSON files by hand. The behavior is the same in `deploy.ps1`, `deploy-python.sh`, and `deploy-bash.sh`.

If you want to delete old EVCC dashboards and library panels before import, set:

```env
PURGE=true
```

Then you can simply run:

### Linux / Raspberry Pi with the Python deployer

```bash
./deploy-python.sh
```

### Linux / Raspberry Pi with the Bash-only deployer

```bash
./deploy-bash.sh
```

### Windows

```powershell
.\deploy.ps1
```

## 6. Verify the result

After the deploy, the Grafana folder `EVCC` should contain these dashboards:

- `VM: EVCC: Today`
- `VM: EVCC: Today - Details`
- `VM: EVCC: Today - Mobile`
- `VM: EVCC: Month`
- `VM: EVCC: Year`
- `VM: EVCC: All-time`

## Common errors

### `Missing GRAFANA_API_TOKEN`

The token is missing:

- in `vm-dashboard-install.env`
- in the CLI parameters
- or in the current environment

### 403 / Permission denied

The token does not have enough rights.

Check:

- the service account still exists
- the token is still valid
- the account can manage dashboards and library panels

## More details

The technical deployment guide is here:

- [vm-dashboard-install.md](./vm-dashboard-install.md)




