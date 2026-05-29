# First Release Checklist

This checklist is intended for the first public end-user release of the VictoriaMetrics-based EVCC dashboard set.

Use it as a release gate. If one of the items below is still open, the release should remain in preview.

## 1. Documentation

- [x] Root [README.md](../README.md) still matches the current repo scope and preview status
- [x] [docs/README.md](./README.md) still reflects the recommended end-to-end order
- [ ] [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) is tested and up to date
- [x] [victoriametrics-install-docker.md](./victoriametrics-install-docker.md) is reviewed and still accurate
- [ ] [grafana-install-debian-13.md](./grafana-install-debian-13.md) is tested and up to date
- [x] [grafana-install-docker.md](./grafana-install-docker.md) is reviewed and still accurate
- [x] [influx-to-vm-migration.md](./influx-to-vm-migration.md) matches the current migration and rollup commands
- [x] [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md) matches the current Grafana setup and deploy flow
- [x] [deployment-readme.md](./deployment-readme.md) and [vm-dashboard-install.md](./vm-dashboard-install.md) match the current deployer options

## 2. Installation and migration validation

- [ ] Fresh VictoriaMetrics install on Debian 13 works end to end
- [ ] Fresh Grafana install on Debian 13 works end to end
- [ ] If Docker is part of the first release promise: VictoriaMetrics Docker guide is validated on a clean host
- [ ] If Docker is part of the first release promise: Grafana Docker guide is validated on a clean host
- [ ] InfluxDB raw-data import works on a realistic EVCC history dataset
- [x] Initial rollup backfill works without manual fixes
- [ ] Daily rollup refresh works via `systemd` timer or `cron`
- [x] At least one clean “new user” dry run exists using only the published docs

## 3. Dashboard deployment validation

- [x] `deploy.ps1` works on Windows PowerShell with a clean dashboard deployment
- [ ] `deploy-python.sh` works on Linux with a clean dashboard deployment
- [ ] `deploy-bash.sh` works on Linux with a clean dashboard deployment
- [ ] `purge=true` deletes and recreates dashboards and embedded library panels correctly
- [ ] `purge=false` updates existing library panels and shows the correct preflight information
- [ ] Dashboard override variables are documented and verified:
- [ ] `DASHBOARD_FILTER_PEAK_POWER_LIMIT`
- [ ] `DASHBOARD_ENERGY_SAMPLE_INTERVAL`
- [ ] `DASHBOARD_TARIFF_PRICE_INTERVAL`
- [ ] `DASHBOARD_INSTALLED_WATT_PEAK`
- [ ] `DASHBOARD_FILTER_LOADPOINT_BLOCKLIST`
- [ ] `DASHBOARD_FILTER_EXT_BLOCKLIST`
- [ ] `DASHBOARD_FILTER_AUX_BLOCKLIST`
- [ ] `DASHBOARD_FILTER_VEHICLE_BLOCKLIST`
- [ ] `DASHBOARD_EVCC_URL`
- [ ] `DASHBOARD_PORTAL_TITLE`
- [ ] `DASHBOARD_PORTAL_URL`

## 4. Dashboard quality

- [x] All six VM dashboards load without panel errors in the production-style deploy path
- [x] `Today` renders correctly including embedded library panels
- [x] `Month` renders correctly including the consumer panels
- [x] `Year` renders correctly including the consumer panels and year navigation buttons
- [x] `All-time` renders correctly including the top-day and yearly/monthly comparison panels
- [ ] Dashboard links between `Today`, `Month`, `Year`, and `All-time` work as intended
- [ ] `Year`, `Previous year`, and `2 years ago` behave consistently with the intended time semantics
- [ ] Units, decimals, background styling, and panel layout are visually consistent

## 5. Localization

- [ ] `node scripts/localization/audit-localization.mjs` reports `0` missing candidates
- [x] localized dashboards are regenerated from the current `orig/en` source
- [ ] release documentation screenshots under [docs/screenshots](./screenshots/README.md) are updated only for dashboards that visibly changed
- [ ] spot-check at least `de`, `fr`, and one non-Latin target (`zh` or `hi`) in Grafana

## 6. Release packaging

- [ ] final commit is pushed to the release remote
- [ ] release notes summarize:
- [ ] supported installation paths
- [ ] migration path from InfluxDB
- [ ] deployer variants
- [ ] known limitations
- [ ] preview wording is removed or reduced once the release is truly ready

## Suggested minimum release gate

At minimum, do not publish a first end-user release until all of these are true:

- [ ] Debian 13 VictoriaMetrics install tested
- [ ] Debian 13 Grafana install tested
- [ ] InfluxDB migration tested
- [x] rollup backfill tested
- [ ] daily rollup refresh tested
- [ ] Windows and Linux deployers tested
- [ ] localization audit at `0`
- [ ] curated release screenshot set under [docs/screenshots](./screenshots/README.md) reflects the final visible dashboard state
- [ ] one complete end-to-end user walkthrough completed from the published docs

## Current Evidence Notes

Last updated: 2026-05-29.

Checked items above are based on the completed documentation restructuring, the successful `npm run test:rollup-path` run on 2026-05-28, and the local Windows Docker walkthrough on 2026-05-29. The Docker walkthrough used separate VictoriaMetrics/Grafana containers for a new-user stream and an InfluxDB migration stream, imported synthetic EVCC raw data, migrated 2,752 samples with `vmctl influx`, generated rollups with `evcc-vm-rollup.py`, deployed the TAB dashboard set with `deploy.ps1`, and passed render smoke checks for all six dashboards in both Grafana instances.

Still open: fresh Debian host install validation, Docker validation on a completely clean host with default ports, realistic full-history InfluxDB migration, Linux deployer runs, localization audit at `0`, and curated release screenshots.
