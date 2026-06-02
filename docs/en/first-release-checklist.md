# First Release Checklist

German version: [first-release-checklist.md](../de/first-release-checklist.md).

This checklist is intended for the first public end-user release of the VictoriaMetrics-based EVCC dashboards.

Use it as a release gate. If one of the items below is still open, the release should not be published as final.

## 1. Documentation

- [x] Root [README.md](../../README.md) still matches the current repo scope and release status
- [x] [docs/en/README.md](../README_EN.md) still reflects the recommended end-to-end order
- [x] [system-requirements.md](./system-requirements.md) centralizes runtime, hardware, network, storage, and label hygiene requirements
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
- [x] Daily rollup refresh works via `systemd` timer or `cron`
- [x] At least one clean “new user” dry run exists using only the published docs

## 3. Dashboard deployment validation

- [x] `deploy.ps1` works on Windows PowerShell with a clean dashboard deployment
- [x] `deploy-python.sh` works on Linux with a clean dashboard deployment
- [x] `deploy-bash.sh` works on Linux with a clean dashboard deployment
- [x] `purge=true` recreates the dashboards with inline panels correctly
- [x] `purge=false` updates existing dashboards and shows the correct preflight information
- [x] Dashboard override variables are documented and verified:
- [x] `DASHBOARD_FILTER_PEAK_POWER_LIMIT`
- [x] `DASHBOARD_ENERGY_SAMPLE_INTERVAL`
- [x] `DASHBOARD_TARIFF_PRICE_INTERVAL`
- [x] `DASHBOARD_INSTALLED_WATT_PEAK`
- [x] `DASHBOARD_FILTER_LOADPOINT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_EXT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_AUX_BLOCKLIST`
- [x] `DASHBOARD_FILTER_VEHICLE_BLOCKLIST`
- [x] `DASHBOARD_EVCC_URL`
- [x] `DASHBOARD_PORTAL_TITLE`
- [x] `DASHBOARD_PORTAL_URL`

## 4. Dashboard quality

- [x] All six VM dashboards load without panel errors in the production-style deploy path
- [x] `Today` renders correctly with inline panels
- [x] `Month` renders correctly including the consumer panels
- [x] `Year` renders correctly including the consumer panels and year navigation buttons
- [x] `All-time` renders correctly including the top-day and yearly/monthly comparison panels
- [x] Dashboard links between `Today`, `Month`, `Year`, and `All-time` work as intended
- [x] `Year`, `Previous year`, and `2 years ago` behave consistently with the intended time semantics
- [x] Units, decimals, background styling, and panel layout are visually consistent

## 5. Localization

- [x] `node scripts/localization/audit-localization.mjs` reports `0` missing candidates
- [x] localized dashboards are regenerated from the current `orig/en` source
- [x] release documentation screenshots under [docs/screenshots](../screenshots/README_EN.md) are updated only for dashboards that visibly changed, and tab-navigation screenshots show the active Grafana tab bar
- [x] spot-check at least `de`, `fr`, and one non-Latin target (`zh` or `hi`) in Grafana

## 6. Release packaging

- [x] final commit is pushed to the release remote
- [x] release notes summarize:
- [x] supported installation paths
- [x] migration path from InfluxDB
- [x] deployer variants
- [x] known limitations
- [x] preview wording is removed or reduced once the release is truly ready

## Suggested minimum release gate

At minimum, do not publish a first end-user release until all of these are true:

- [x] Debian 13 VictoriaMetrics install tested
- [x] Debian 13 Grafana install tested
- [x] InfluxDB migration tested
- [x] rollup backfill tested
- [x] daily rollup refresh tested
- [x] Windows and Linux deployers tested
- [x] localization audit at `0`
- [x] curated release screenshot set under [docs/screenshots](../screenshots/README_EN.md) reflects the final visible dashboard state, including tab navigation state
- [x] one complete end-to-end migration walkthrough completed from the published docs

## Current Evidence Notes

Last updated: 2026-05-31.

Checked items above are based on the completed documentation restructuring, the successful `npm run test:rollup-path` run on 2026-05-28, the local Windows Docker migration walkthrough on 2026-05-29 using Ole's real EVCC/Influx data, and the manually refreshed release screenshots from 2026-05-31.

Real-data migration evidence from 2026-05-29:

- source InfluxDB v1 database `evcc`, read-only access during the test
- source EVCC API was used only for read-only topology verification
- disposable target VictoriaMetrics used Docker image `victoriametrics/victoria-metrics:v1.138.0`
- disposable target Grafana used Docker image `grafana/grafana`, Grafana `13.0.1+security-01`
- `vmctl influx` imported 643 series, 267,886,076 samples, and 5.3 GB from the real Influx history for `2025-01-01T00:00:00Z` through the live import snapshot on 2026-05-29
- real labels after import included 3 loadpoints (`Carport_Ecke`, `Carport_Treppe`, `Daikin-WP`), 3 vehicles (`Altherma-3`, `BMW i3`, `Schneeflittchen`), and 16 EXT titles
- host-label cleanup dry-runs reported `GO FOR IT`; final `check_data.py` confirmed `host` series `0` and `db` series `0`
- `compare_import_coverage.py` over the completed window `2026-05-22T00:00:00Z` through `2026-05-28T23:59:59Z` reported 0 repo-relevant problems and 0 critical energy problems
- rollup `detect`, `plan`, and `benchmark` succeeded; full backfill from `2025-01-01` through `2026-05-28` wrote 36 rollup metrics, 1,154 series, and 30,013 samples
- `deploy.ps1` deployed the German generated tab-navigation dashboards from the local checkout with `PURGE=true`
- `render-smoke-check.mjs` passed strictly for all 6 dashboards and 49 critical panels against the real-data test VM
- Manual dashboard safety review from 2026-05-30 completed successfully: navigation between Today, Month, Year, and All-time, year time navigation semantics, units, decimals, background styling, and panel layout were accepted.
- Clean new-user Docker dry run from 2026-05-30 completed from the published docs path: fresh VictoriaMetrics `v1.139.0`, fresh Grafana `13.0.1`, datasource UID `vm-evcc`, and German generated tab-navigation deployment via `deploy-python.sh`.
- Release screenshots from 2026-05-31 were manually refreshed and curated directly under `docs/screenshots` as one PNG per relevant dashboard or active dashboard tab.
- Localization Grafana spot-checks from 2026-05-30 passed for `de`, `fr`, and `zh`; French and Chinese deployments showed localized dashboard and panel titles in Grafana.
- Release notes were added in `docs/en/release-notes.md`, and root preview wording was removed from `README.md`.

Still open: none for the first public release gate.

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

Additional autonomous release-gate evidence from 2026-05-29:

- `deploy-python.sh` v2026.05.29.1 was syntax-checked in blank `debian:trixie` and completed a clean Linux deployment (`PURGE=true`) of the German generated tab-navigation dashboard set against Grafana `13.0.1` on disposable Docker port `13035`.
- `deploy-bash.sh` v2026.05.29.1 was syntax-checked in blank `debian:trixie`, completed `PURGE=true`, and then completed `PURGE=false` against the same disposable Grafana instance.
- The Linux deployers now handle Grafana dashboard v2 JSON via `/apis/dashboard.grafana.app/v2/...`, including folder annotations and `metadata.resourceVersion` updates for existing dashboards.
- Dashboard override validation queried Grafana after deployment and verified 46 override variable instances across all 6 dashboards, including v2 tab-navigation dashboards and classic dashboards, with folder placement in `evcc-release-bash`.
- Daily rollup refresh validation used the documented cron-style `date -d 'yesterday'` wrapper shape in blank `debian:trixie`; the run executed `backfill --replace-range --write` successfully after `rollup-e2e.py` had validated repeated replacement without duplicate daily samples.
- Localization audit now reports `0` missing candidates for `de`, `fr`, `nl`, `es`, `it`, `zh`, and `hi`; generated localized dashboards were regenerated and `npm run test:localization-idempotency` passed.
