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
- [x] `DASHBOARD_FILTER_CONSUMER_BLOCKLIST`
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
- [x] The current release candidate was rendered in disposable Grafana against the read-only live VM with the actual deploy overrides and blocklists; fixture data alone is insufficient.
- [x] Every new optional feature in release scope has matching live metrics and a visible end-user check. If the live metric is absent, the feature is explicitly reported as fixture-tested only and not live-validated.
- [x] Consumer, AUX, and EXT sums were checked for parent/child overlap. Filtered detail meters must not silently consume or exceed total home consumption.

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
- [x] Read-only live-source rendering with actual deploy overrides is plausible; new optional features without matching live metrics are not marked as live-validated

## Current Evidence Notes

Last updated: 2026-07-28.

The current release candidate was tested in freshly cleaned Docker instances with the supported Grafana 13.0.1 baseline and additionally with Grafana 13.1.0 against VictoriaMetrics 1.139.0. Production remained read-only; 19 monthly blocks from 2025-01-01 through 2026-07-29 were copied into the isolated test VM. Before end-user visual testing, all old test dashboards were deleted and exactly six current German dashboards were deployed with the production filters.

Current technical evidence:

- The complete rollup processed 573 completed days, 36,625 samples, and 1,388 series in 210.606 seconds with 1,264 MB peak memory.
- `check_data.py --phase full` reported overall `OK`, no duplicate label/day combinations, and no `host` or `db` labels.
- The mandatory `npm run test:rollup-path -- --strict-energy --vm-base-url http://127.0.0.1:18440` run passed on the final release sources in 521.3 seconds: 190 Python tests, 76 dashboard JSON files, 382 real MetricsQL queries, 60 critical panels across six dashboards, 17 additional historical `Today - Details` panel checks, and repeated `--replace-range` without duplicates.
- The VRM import contained 383 days and 2,298 samples. All six VRM metrics matched the normalized source snapshot day by day with `missing=0`, `extra=0`, and `duplicates=0`. June 2026 produced 85.260% efficiency versus the 85.3% reference, a 0.040 percentage-point delta.
- The scheduler lock rejected a concurrently started second write run. The full backfill reported two ignored counter resets, zero power spikes, and 9,910 missing energy buckets.
- Consumer long-range series contain 14 canonical titles. The former `Trocker` spelling appears only as `Trockner` after full replacement; mapped former EXT consumers are not also counted as EXT.
- End-user visual testing under Grafana 13.0.1 and 13.1.0 confirmed 2025 and 2026 in All-time, plausible July 2026 values, `Today` as the actual Grafana range, and separate EVCC and VRM battery values. For June 2026, Grafana showed 96.5% EVCC and 85.3% VRM efficiency.
- The EXT-to-Consumer migration test covered 2026-07-25 before the role change, 2026-07-27 as the cutover day, and the current Today view against the live-data copy under both Grafana versions. All four Home panels stayed populated; 14 historical and 14 current consumer titles were returned without identical duplicate titles and without Carport or Main Distribution sum meters.
- The Month battery layout was corrected at 1280 pixels: metrics and daily axis labels no longer overlap.

Earlier installation, migration, and localization evidence remains valid. Ole manually approved the final dashboard revision on 2026-07-28. The curated gallery was then regenerated completely and contains 25 views, including Consumer and additional-meter tabs.

The release gate is fully satisfied: Ole manually approved the final view, 25 curated screenshots represent the final revision, and the mandatory rollup path passed on the final sources in 521.3 seconds. Issue #30 is closed with this release. Issue #35 remains explicitly outside this release scope.
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
