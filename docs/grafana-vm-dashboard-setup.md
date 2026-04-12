# Set Up Grafana with VictoriaMetrics and the EVCC Dashboards

This guide covers the end-user path to:

- connect Grafana to a running VictoriaMetrics instance
- deploy the EVCC dashboards for the first time
- update the dashboards later

This guide assumes VictoriaMetrics is already running.

If not, start here:

- [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)
- [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

## Target state

At the end you should have in Grafana:

- a VictoriaMetrics datasource
- a folder called `EVCC`
- the EVCC dashboard set deployed into that folder

Important:

- the `Today*` dashboards read raw data directly from VictoriaMetrics
- `Month`, `Year`, and `All-time` also depend on the generated `evcc_*` rollups

## Prerequisites

You need:

- a running Grafana instance
- a running VictoriaMetrics instance
- a Grafana service-account token
- internet access to GitHub

On Linux you additionally need:

- for `deploy-python.sh`: `curl` and `python3`
- for `deploy-bash.sh`: `bash`, `curl`, and `jq`

Minimal Debian packages:

```bash
sudo apt update
sudo apt install -y curl python3 jq
```

## 1. Create the VictoriaMetrics datasource in Grafana

In Grafana:

1. Open `Connections` or `Administration`
2. Open `Data sources`
3. Click `Add data source`
4. Select `VictoriaMetrics`

If the datasource plugin is not offered:

- install the VictoriaMetrics datasource plugin first
- restart Grafana

Typical datasource settings:

- Name:
  - `VM-EVCC`
- URL:
  - `http://<your-vm-host>:8428`
- Access:
  - `Server` or `Proxy`

Recommended UID:

```text
vm-evcc
```

Why the UID matters:

- the deploy scripts use this datasource UID by default
- if you choose a different UID, you must pass that value during deployment

Then:

1. click `Save & test`
2. verify that Grafana can reach VictoriaMetrics successfully

## 2. Create a Grafana service-account token

In Grafana:

1. Open `Administration`
2. Open `Users and access`
3. Open `Service accounts`
4. Click `Add service account`
5. Create something like `evcc-dashboard-deployer`
6. Open the service account
7. Click `Add service account token`
8. Give the token a name, such as `default`
9. Click `Generate token`
10. copy the token immediately

For normal local deployments, `Admin` in the current organization is usually enough.

## 3. Download the deployer

### Windows / PowerShell

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

### Linux / Raspberry Pi with the Python deployer

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

### Linux / Raspberry Pi with the Bash deployer

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-bash.sh
```

## 4. Create the config file

Copy the example config:

Windows:

```powershell
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Linux:

```bash
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimal settings:

```env
GRAFANA_URL=http://<your-grafana-ip>:3000
GRAFANA_API_TOKEN=<your_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
PURGE=false
```

Default values also used by the deployer:

- folder UID: `evcc`
- folder title: `EVCC`
- source mode: `github`
- repo: `endurance1968/evcc-grafana-dashboards`
- branch: `main`
- language: `en`
- variant: `gen`

Important:

- `PURGE=false` is intentionally the safe default
- for a first deployment that is usually the right choice

## 5. Run the first deployment

### Windows

```powershell
.\deploy.ps1
```

Or directly with parameters:

```powershell
.\deploy.ps1 -url http://<your-grafana-ip>:3000 -token <your_token> -purge false
```

### Linux with the Python deployer

```bash
./deploy-python.sh
```

Or directly with parameters:

```bash
./deploy-python.sh --url http://<your-grafana-ip>:3000 --token <your_token> --purge false
```

### Linux with the Bash deployer

```bash
./deploy-bash.sh
```

Or directly with parameters:

```bash
./deploy-bash.sh --url http://<your-grafana-ip>:3000 --token <your_token> --purge false
```

## What the deployer does

The deployer:

- verifies Grafana access first
- shows which dashboards will be imported
- shows which library panels are embedded
- shows what would be deleted if `purge=true`
- asks for confirmation before writing
- imports the EVCC dashboard set into the `EVCC` folder

With `purge=false`:

- existing EVCC dashboards are overwritten by UID
- existing EVCC library panels referenced by `__elements` are updated before dashboard import, so stale panel models are not kept

With `purge=true`:

- known EVCC dashboards and their library panels are deleted first
- then the full set is imported again

## 6. Verify the result

After deployment, check:

- the dashboards exist in the `EVCC` folder
- `Today` shows current raw data
- `Month`, `Year`, and `All-time` show rollup values
- the forecast is visible in the `Today` main panel

## Example: update dashboards later

The normal update flow is simple:

1. download the latest deploy script again, or keep using the existing copy
2. run the same deploy command again

### Gentle update

If you only want a newer dashboard revision without deliberately deleting anything first:

Windows:

```powershell
.\deploy.ps1 -purge false
```

Linux:

```bash
./deploy-python.sh --purge false
```

This is the normal update mode.

### Full rebuild

If you want to rebuild the EVCC folder from scratch:

Windows:

```powershell
.\deploy.ps1 -purge true
```

Linux:

```bash
./deploy-python.sh --purge true
```

This is useful when:

- library panels appear broken
- a previous import left Grafana in an inconsistent state
- you intentionally want a completely fresh import

## Change the dashboard language

To use German instead of English, set in `vm-dashboard-install.env`:

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Then run the same deployer again.

Typical values:

- `en` + `gen`
- `de` + `gen`
- `fr` + `gen`
- `en` + `orig`

Meaning:

- `orig`: original dashboards
- `gen`: generated localized dashboards

## If you use a different datasource UID

Then set:

```env
GRAFANA_DS_VM_EVCC_UID=<your_uid>
```

Without that change, the deploy scripts expect:

```text
vm-evcc
```

## Common errors

### `Missing GRAFANA_API_TOKEN`

The token is missing:

- in `vm-dashboard-install.env`
- in the CLI parameters
- or in the environment

### 403 / Permission denied

The token does not have enough rights.

Check:

- the service account still exists
- the token is still valid
- the account can manage dashboards, folders, and library panels

### Dashboards imported, but empty

Usually check first:

- the datasource really points to VictoriaMetrics
- the URL is correct
- raw data and rollups already exist in VictoriaMetrics

### `Today` works, but `Month/Year/All-time` are empty

That usually means the rollups are still missing.

See:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

## Related docs

For more detail, continue directly here instead of rereading the same basics:

- [deployment-readme.md](./deployment-readme.md)
- [vm-dashboard-install.md](./vm-dashboard-install.md)
- [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)
- [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- [influx-to-vm-migration.md](./influx-to-vm-migration.md)
