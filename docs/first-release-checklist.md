# First Release Checklist

This checklist is intended for the first public end-user release of the VictoriaMetrics-based EVCC dashboard set.

Use it as a release gate. If one of the items below is still open, the release should remain in preview.

## 1. Documentation

- [ ] Root [README.md](../README.md) still matches the current repo scope and preview status
- [ ] [docs/README.md](./README.md) still reflects the recommended end-to-end order
- [ ] [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) is tested and up to date
- [ ] [victoriametrics-install-docker.md](./victoriametrics-install-docker.md) is reviewed and still accurate
- [ ] [grafana-install-debian-13.md](./grafana-install-debian-13.md) is tested and up to date
- [ ] [grafana-install-docker.md](./grafana-install-docker.md) is reviewed and still accurate
- [ ] [influx-to-vm-migration.md](./influx-to-vm-migration.md) matches the current migration and rollup commands
- [ ] [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md) matches the current Grafana setup and deploy flow
- [ ] [deployment-readme.md](./deployment-readme.md) and [vm-dashboard-install.md](./vm-dashboard-install.md) match the current deployer options

## 2. Installation and migration validation

- [ ] Fresh VictoriaMetrics install on Debian 13 works end to end
- [ ] Fresh Grafana install on Debian 13 works end to end
- [ ] If Docker is part of the first release promise: VictoriaMetrics Docker guide is validated on a clean host
- [ ] If Docker is part of the first release promise: Grafana Docker guide is validated on a clean host
- [ ] InfluxDB raw-data import works on a realistic EVCC history dataset
- [ ] Initial rollup backfill works without manual fixes
- [ ] Hourly rollup refresh works via `systemd` timer or `cron`
- [ ] At least one clean “new user” dry run exists using only the published docs

## 3. Dashboard deployment validation

- [ ] `deploy.ps1` works on Windows PowerShell with a clean dashboard deployment
- [ ] `deploy-python.sh` works on Linux with a clean dashboard deployment
- [ ] `deploy-bash.sh` works on Linux with a clean dashboard deployment
- [ ] `purge=true` deletes and recreates dashboards and embedded library panels correctly
- [ ] `purge=false` keeps existing library panels and shows the correct preflight information
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

- [ ] All six VM dashboards load without panel errors in the production-style deploy path
- [ ] `Today` renders correctly including embedded library panels
- [ ] `Month` renders correctly including the consumer panels
- [ ] `Year` renders correctly including the consumer panels and year navigation buttons
- [ ] `All-time` renders correctly including the top-day and yearly/monthly comparison panels
- [ ] Dashboard links between `Today`, `Month`, `Year`, and `All-time` work as intended
- [ ] `Year`, `Previous year`, and `2 years ago` behave consistently with the intended time semantics
- [ ] Units, decimals, background styling, and panel layout are visually consistent

## 5. Localization

- [ ] `node scripts/localization/audit-localization.mjs --family=vm` reports `0` missing candidates
- [ ] localized dashboards are regenerated from the current `orig/en` source
- [ ] screenshots are regenerated from the current localized dashboards
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
- [ ] rollup backfill tested
- [ ] hourly rollup refresh tested
- [ ] Windows and Linux deployers tested
- [ ] localization audit at `0`
- [ ] screenshot set regenerated from the final sources
- [ ] one complete end-to-end user walkthrough completed from the published docs
