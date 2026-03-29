# VM Dashboard Install

For a simple end-user walkthrough, see:

- `docs/installation-readme.md`

This is the end-user install path for the VM dashboards.

Goal:

- no Node.js required
- simple first deploy defaults
- import both dashboards and Grafana library panels

## Recommended Grafana access

Use a Grafana API token or service-account token with permissions to:

- create/update folders
- create/update dashboards
- create/update library panels
- delete dashboards/library panels when purge is enabled

This is simpler and safer than using username/password automation.

## Default behavior

The installer defaults to:

- source repo: `endurance1968/evcc-grafana-dashboards`
- ref: `main`
- language: `en`
- variant: `orig`
- folder UID/title: `evcc` / `EVCC`
- datasource UID: `vm-evcc`
- purge before import: `false`

Default is `PURGE=false`, so existing dashboards are kept unless you explicitly opt into deleting them before import.

When `PURGE=true`, the installer deletes only the dashboards whose `uid` is present in the 6 VM dashboard JSON files and only the library panels whose `uid` is referenced under `__elements` in those same files.

For the first deploy, only these two values normally need to be changed:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`

It does **not** patch dashboard internals during install.

That means:

- colors come from the checked-in dashboard JSONs
- filter defaults come from the checked-in dashboard variables
- user-specific tweaks should be made in Grafana after import, or by maintaining a local dashboard source

## Config file

Copy:

- `vm-dashboard-install.env.example`

to:

- `vm-dashboard-install.env`

and set at least:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`

Optional:

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

Runtime override parameters are also available:

- PowerShell: `-url`, `-token`, `-purge`
- Shell: `--url`, `--token`, `--purge`

These override the config values for a single run.

## User customization

The installer is intentionally import-only.

Recommended ways to customize:

- change dashboard variables in Grafana and save the dashboard
- or deploy from a local dashboard directory via `DASHBOARD_SOURCE_MODE=local`

The installer intentionally does not rewrite:

- colors
- blocklist defaults
- panel settings

## Windows

PowerShell only, no Node required:

```powershell
.\scripts\install-vm.ps1
```

With explicit config:

```powershell
.\install-vm.ps1 -config .\vm-dashboard-install.env
```

Or directly with the important values:

```powershell
.\install-vm.ps1 -url http://<grafana-host>:3000 -token <token> -purge false
```

## Linux / Raspberry Pi

The shell installer uses `python3`, which is usually already present.

If not:

```bash
sudo apt install python3
```

Run:

```bash
sh ./install-vm-python.sh
```

With explicit config:

```bash
sh ./install-vm-python.sh --config ./vm-dashboard-install.env
```

Or directly with the important values:

```bash
sh ./install-vm-python.sh --url http://<grafana-host>:3000 --token <token> --purge false
```

## Maintainer note

The Node.js scripts under `scripts/test` remain the maintainer workflow for:

- localization generation
- test-folder imports
- screenshot automation
- smoke checks

End users should prefer the installer scripts above.

