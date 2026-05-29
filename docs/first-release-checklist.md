# First Release Checklist

This checklist is intended for the first public end-user release of the VictoriaMetrics-based EVCC dashboard set.

Use it as a release gate. If one of the items below is still open, the release should remain in preview.

## 1. Documentation

- [x] Root [README.md](../README.md) still matches the current repo scope and preview status
- [x] [docs/README.md](./README.md) still reflects the recommended end-to-end order
- [x] [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) is tested and up to date
- [x] [victoriametrics-install-docker.md](./victoriametrics-install-docker.md) is reviewed and still accurate
- [x] [grafana-install-debian-13.md](./grafana-install-debian-13.md) is tested and up to date
- [x] [grafana-install-docker.md](./grafana-install-docker.md) is reviewed and still accurate
- [x] [influx-to-vm-migration.md](./influx-to-vm-migration.md) matches the current migration and rollup commands
- [x] [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md) matches the current Grafana setup and deploy flow
- [x] [deployment-readme.md](./deployment-readme.md) and [vm-dashboard-install.md](./vm-dashboard-install.md) match the current deployer options

## 2. Installation and migration validation

- [x] Fresh VictoriaMetrics install on Debian 13 works end to end
- [x] Fresh Grafana install on Debian 13 works end to end
- [x] If Docker is part of the first release promise: VictoriaMetrics Docker guide is validated on a local Docker host
- [x] If Docker is part of the first release promise: Grafana Docker guide is validated on a local Docker host
- [x] InfluxDB raw-data import works on a realistic EVCC history dataset
- [x] Initial rollup backfill works without manual fixes
- [ ] Daily rollup refresh works via `systemd` timer or `cron`
- [ ] At least one clean “new user” dry run exists using only the published docs

## 3. Dashboard deployment validation

- [x] `deploy.ps1` works on Windows PowerShell with a clean dashboard deployment
- [ ] `deploy-python.sh` works on Linux with a clean dashboard deployment
- [ ] `deploy-bash.sh` works on Linux with a clean dashboard deployment
- [x] `purge=true` creates a clean dashboard set and embedded library panels correctly
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

- [x] Debian 13 VictoriaMetrics install tested
- [x] Debian 13 Grafana install tested
- [x] InfluxDB migration tested
- [x] rollup backfill tested
- [ ] daily rollup refresh tested
- [ ] Windows and Linux deployers tested
- [ ] localization audit at `0`
- [ ] curated release screenshot set under [docs/screenshots](./screenshots/README.md) reflects the final visible dashboard state
- [x] one complete end-to-end migration walkthrough completed from the published docs

## Current Evidence Notes

Last updated: 2026-05-29.

Checked items above are based on the completed documentation restructuring, the successful `npm run test:rollup-path` run on 2026-05-28, and the local Windows Docker migration walkthrough on 2026-05-29 using Ole's real EVCC/Influx data.

Real-data migration evidence from 2026-05-29:

- source InfluxDB v1 `http://192.168.1.183:8086`, database `evcc`, read-only access during the test
- source EVCC API `http://192.168.1.197:7070`, used only for read-only topology verification
- disposable target VictoriaMetrics on `http://127.0.0.1:18429`, Docker image `victoriametrics/victoria-metrics:v1.138.0`
- disposable target Grafana on `http://127.0.0.1:13032`, Docker image `grafana/grafana`, Grafana `13.0.1+security-01`
- `vmctl influx` imported 643 series, 267,886,076 samples, and 5.3 GB from the real Influx history for `2025-01-01T00:00:00Z` through the live import snapshot on 2026-05-29
- real labels after import included 3 loadpoints (`Carport_Ecke`, `Carport_Treppe`, `Daikin-WP`), 3 vehicles (`Altherma-3`, `BMW i3`, `Schneeflittchen`), and 16 EXT titles
- host-label cleanup dry-runs reported `GO FOR IT`; final `check_data.py` confirmed `host` series `0` and `db` series `0`
- `compare_import_coverage.py` over the completed window `2026-05-22T00:00:00Z` through `2026-05-28T23:59:59Z` reported 0 repo-relevant problems and 0 critical energy problems
- rollup `detect`, `plan`, and `benchmark` succeeded; full backfill from `2025-01-01` through `2026-05-28` wrote 36 rollup metrics, 1,154 series, and 30,013 samples
- `deploy.ps1` deployed the German generated TAB dashboard set from the local checkout with `PURGE=true`
- `render-smoke-check.mjs` passed strictly for all 6 dashboards and 49 critical panels against the real-data test VM

Still open: Docker validation on a completely clean host with default ports, direct new-user EVCC-to-VictoriaMetrics write-stream validation, Linux deployer runs, localization audit at `0`, dashboard link/time-navigation manual checks, and curated release screenshots.

Debian 13 install evidence from 2026-05-29:

- validated in fresh `debian:trixie` Docker containers reporting Debian `13.5` and `x86_64`
- blank image did not include `sudo`; docs now state that root users can omit `sudo`
- VictoriaMetrics `v1.139.0` binary and `vmctl` installed from the documented release archives
- VictoriaMetrics service file was created; standard Docker has no `systemctl`, so runtime was validated by manually starting `victoria-metrics-prod` as the `victoriametrics` user with the documented data path and flags
- VictoriaMetrics `/health` returned `OK` locally and through the Windows-published Docker port
- Grafana APT repository setup and `grafana-enterprise` installation succeeded on blank Trixie; installed version was `13.0.1+security-01`
- docs now include `curl` in Grafana base packages because the verification step uses `curl -I`
- VictoriaMetrics datasource plugin install was validated with `grafana cli --homepath=/usr/share/grafana --pluginsDir /var/lib/grafana/plugins plugins install victoriametrics-metrics-datasource`
- Grafana `/api/health` returned `database: ok`, and a VictoriaMetrics datasource pointed at the fresh Debian VictoriaMetrics test instance returned `Data source is working`
