# Release Notes

These notes summarize the first public VictoriaMetrics-based EVCC dashboard release.

## VNext (unreleased)


### Documentation And Diagnostics

- Implemented Forgejo issue #6: documented the EVCC forecast data flow for `tariffSolar_value`, no-data behavior, and VictoriaMetrics check commands; forecast panels now explain directly that the solar forecast must come from EVCC.

### Improvements

- Implemented the Grafana 13 gauge visualization tracked in Forgejo issue #7 and moved it from hold status into the dashboard path:
  - `3cc765e` add the Today Gauges dashboard
  - `d052a84` simplify the Today Gauges layout
  - `43cdb86` link gauges to the matching Today Details tabs
  - `bf9999c` use Grafana tab state and sparkline gauges
  - `61a7e71` switch autonomy/self-consumption metric panels to sparkline gauges
  - `5f08c29` stabilize metric-gauge sparkline rendering

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
