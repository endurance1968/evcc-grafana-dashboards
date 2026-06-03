# Dashboards

German version: [README.md](./README.md).

This directory contains the Grafana dashboard JSON files for the current VictoriaMetrics-based EVCC dashboard set and the related localization data.

Regular users do not need to import or edit files here manually. The recommended path is deployment through the scripts in [`../scripts`](../scripts) and the setup guide in [`../docs/en/grafana-vm-dashboard-setup.md`](../docs/en/grafana-vm-dashboard-setup.md).

## Current Dashboard Set

The current VM deployment imports the files listed in [`deploy-manifest.json`](./deploy-manifest.json):

- `VM_EVCC_All-time.json`
- `VM_EVCC_Year.json`
- `VM_EVCC_Month.json`
- `VM_EVCC_Today-Details.json`
- `VM_EVCC_Today.json`
- `VM_EVCC_Today-Mobile.json`

Depending on `DASHBOARD_LANGUAGE`, the files are loaded from `translation/<language>/`. With `DASHBOARD_VARIANT=orig`, the English source dashboards from `original/en/` are used.

## Directory Structure

- [`original/en/`](./original/en/): source of truth for the current VM dashboards. Manual dashboard changes belong here.
- [`translation/`](./translation/): generated localized dashboards. Do not edit these files directly.
- [`localization/`](./localization/): language configuration and mapping files for generated localized variants.
- [`influx-legacy/`](./influx-legacy/): archived old InfluxDB dashboards. They are not part of the current VM deployment.
- [`deploy-manifest.json`](./deploy-manifest.json): fixed list of dashboards imported by the deploy scripts.

## Editing Rule

Dashboard JSON files are edited manually only under `dashboards/original/`. After each change, regenerate the generated variants:

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
```

Then run at least the local checks:

```bash
npm test
npm run test:localization-idempotency
```

## Deployment Notes

The dashboards expect EVCC data in VictoriaMetrics plus the related rollups. External services such as Tibber, Victron VRM, or Solarman are not runtime data sources for the dashboards.

Optional header links such as the EVCC URL or an external portal are set during deployment through the env file. Without `DASHBOARD_PORTAL_URL`, no portal button is shown.
