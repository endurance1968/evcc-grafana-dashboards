# Release Notes

These notes summarize the public VictoriaMetrics-based EVCC dashboard releases.

## Unreleased

No entries yet.

## V2026-06-30

### New Features

- EVCC green share is visible as a KPI in `Today`, `Month`, `Year`, and `All-time`. The value follows EVCC's `greenShareHome_value` and represents EVCC's home green share as a trend KPI.
- Optional grid-control/14a audit path: a collector can write EVCC limits and control events to VictoriaMetrics and keep a local CSV history. `Today - Details` shows these values in the `Grid control` tab with grid limits, compliance reserves, current limits, controllable groups, and an event table.
- The collector supports explicitly configured controllable groups, for example combined loadpoints, heat pump, and battery grid charge.

### Improvements

- `Year` and `Month` group home, consumer, and finance areas more clearly: supply-mix panels live under `Home`, while cost and price panels live under `Finances`.
- Grid-control panels use consistent signs and colors: import/consumption in red, feed-in in green, and calculated values in blue; feed-in is shown as negative.
- The deployer writes a more useful dashboard build marker with build/source instead of only the deployment timestamp.

### User Notes

- Long-range green-share panels in month, year, and all-time dashboards require the regular EVCC VM rollup for the affected date ranges. The current long-range values are trend KPIs based on daily EVCC ratios, not an external renewable-tariff or CO2 assessment.
- The grid-control tab is shown only when `evcc_audit_*` metrics exist. This optional view requires the collector to be installed and running; the documentation uses `/opt/evcc-vm-tools` for that setup.

## V2026-06-14

### New Features

- PV generation costs (LCOE) are now available as optional finance panels in `Year` and `All-time`. The calculation uses an investment file, supports multiple investments per asset, linear depreciation per position, shared investments, and shows data coverage directly in the asset label. Commits: `b7b1638`, `2e463c1`, `3d61f5d`, `126ae00`, `bfb43fd`.
- A weekly investment helper for Linux production systems can refresh the LCOE metrics alongside the regular EVCC rollup. If no investment metrics exist, the optional panels are hidden automatically. Commits: `67d6497`, `0192569`.
- Historic PV yield from external sources can be imported as EVCC-compatible daily PV energy by `title`. The included SMA Portal importer is one example path for historic systems; investment calculation and energy import remain separate. Commits: `b7b1638`, `a863616`.
- `Year` and `All-time` include new PV asset comparisons for yearly energy and specific yield (`kWh/kWp`). Specific yield prefers asset peak power from investment data and keeps the existing `installedWattPeak` fallback for older installations. Commits: `8e6be9b`, `85d821c`, `2e4bd12`.

### Dashboard Improvements

- `Today` now uses Grafana 13 sparkline gauges as the default overview. The former separate Today Gauges variant has been folded into the normal Today dashboard path.
- Autarky, self-consumption, and storage SOC use consistent sparkline gauges and a shared color scheme across dashboards.
- Forecast comparison panels show a direct message inside the affected panel when EVCC forecast data is missing instead of silently empty comparison data.
- Year and month dashboards show partial PV data with coverage labels instead of hiding useful partial years by default.

### Quality And Validation

- The energy comparison validator no longer auto-selects local `current-evcc-agg` snapshots as the Tibber-vs-Influx release baseline. Those files remain available for explicit manual analysis, but they no longer block the reproducible release path.
- Local release checks cover static dashboard semantics, MetricsQL readback, localization idempotency, PowerShell compatibility, and Grafana render E2E against disposable Docker instances.

## Supported Installation Paths

Supported end-user paths:

- VictoriaMetrics on Debian 13
- VictoriaMetrics with Docker
- Grafana on Debian 13
- EVCC/Telegraf live ingest to VictoriaMetrics
- Grafana with Docker
- dashboard deployment from Windows PowerShell
- dashboard deployment from Linux with the Python deployer
- optional Linux Bash deployer for systems that prefer Bash and `jq`

Start with [system-requirements.md](./system-requirements.md), then follow [README.md](../README_EN.md) for the recommended order.

## Migration From InfluxDB

The normal migration path is documented in [influx-to-vm-migration.md](./influx-to-vm-migration.md):

1. install or prepare VictoriaMetrics
2. prepare EVCC/Telegraf live ingest, but keep the VictoriaMetrics write path disabled during migrations
3. import raw EVCC history from InfluxDB v1 with `vmctl influx`
4. validate raw coverage with `check_data.py` and `compare_import_coverage.py`
5. normalize infrastructure labels such as `host` when the checker requires it
6. run `evcc-vm-rollup.py` dry-run and write backfill for daily `evcc_*` metrics
7. schedule the daily rollup refresh for completed local days
8. run the final delta import, refresh rollups for newly completed days if needed, and then enable the VictoriaMetrics write path
9. connect Grafana to VictoriaMetrics and deploy dashboards

The release validation checked the live-ingest path, imported a real multi-year EVCC history into VictoriaMetrics, cleaned `host` labels, verified `db=0`, built rollups, and rendered the dashboards against the migrated data.

## Dashboard Set

The deployed dashboards always use the Grafana 13 tab-navigation layout and require Grafana 13.0.1 or newer. The legacy row-based deploy path and dashboard set selection have been removed from the deploy manifest and scripts.

The release screenshots document the German generated tab-navigation dashboard set directly under [screenshots](../screenshots/README_EN.md), including the active Grafana tab bar where dashboards use tabs.

## Deployer Variants

Supported deployers:

- `scripts/deploy.ps1` for Windows PowerShell
- `scripts/deploy-python.sh` for Linux and Raspberry Pi-class systems
- `scripts/deploy-bash.sh` as an optional Bash and `jq` path

All deployers support the same core configuration:

- Grafana URL and authentication
- VictoriaMetrics datasource UID
- dashboard language
- dashboard variant
- dashboards
- purge or update behavior
- dashboard variable overrides such as EVCC URL, portal URL, blocklists, and installed peak power

## Localization

Generated dashboard translations are available for:

- `de`
- `fr`
- `nl`
- `es`
- `it`
- `zh`
- `hi`

The release gate includes localization idempotency checks and Grafana spot-checks for German, French, and Chinese.

## Known Limitations

- Use one VictoriaMetrics instance per EVCC instance. Do not multiplex multiple EVCC systems through a synthetic `db` label.
- Long-range dashboards require daily `evcc_*` rollups. `Today`, `Today - Mobile`, and `Today - Details` use raw metrics directly.
- The rollup write path intentionally rejects the current local day by default. Schedule refreshes for yesterday or another completed day.
- Telegraf live fan-out must avoid infrastructure labels. Set `omit_hostname = true` and use `[[outputs.http]]` with `data_format = "influx"` for VictoriaMetrics.
- Docker Desktop users must remember that `localhost` inside Grafana points to the Grafana container. Use `host.docker.internal` or a shared Docker network name for the VictoriaMetrics datasource URL.
- `prioritySoc_value` can be reported as a warning when it exists historically but is not active in the current EVCC raw window. That does not block the core dashboard path.

## Validation Summary

Release validation covered:

- Debian 13 VictoriaMetrics install
- Debian 13 Grafana install
- Docker-based VictoriaMetrics and Grafana install paths
- realistic InfluxDB history migration
- raw coverage and label hygiene checks
- full rollup dry-run and write backfill
- daily rollup refresh path
- Windows and Linux dashboard deployers
- German tab-navigation dashboard screenshots for every active tab
- Grafana localization spot-checks for `de`, `fr`, and `zh`
- local static/unit/dashboard checks via `npm test`
