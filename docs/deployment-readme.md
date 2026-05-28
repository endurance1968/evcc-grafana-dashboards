# Dashboard Deployment Quick Start

This is the short deployment reference. For the full walkthrough, use [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). For every config option, use [vm-dashboard-install.md](./vm-dashboard-install.md).

## Recommended Path

Linux / Raspberry Pi:

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Windows / PowerShell:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimal `vm-dashboard-install.env`:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<your_service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
DASHBOARD_SET=tabs
PURGE=false
```

Use `DASHBOARD_SET=default` if you do not run Grafana 13.0.1 or newer.

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
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
chmod +x deploy-bash.sh
sudo apt install -y jq
./deploy-bash.sh
```

For beginners, prefer `deploy-python.sh` because the migration and rollup path already require Python.