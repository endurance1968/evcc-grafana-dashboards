# Release Notes

These notes summarize the first public VictoriaMetrics-based EVCC dashboard release.

## Supported Installation Paths

Supported end-user paths:

- VictoriaMetrics on Debian 13
- VictoriaMetrics with Docker
- Grafana on Debian 13
- Grafana with Docker
- dashboard deployment from Windows PowerShell
- dashboard deployment from Linux with the Python deployer
- optional Linux Bash deployer for systems that prefer Bash and `jq`

Start with [system-requirements.md](./system-requirements.md), then follow [README.md](./README.md) for the recommended order.

## Migration From InfluxDB

The normal migration path is documented in [influx-to-vm-migration.md](./influx-to-vm-migration.md):

1. install or prepare VictoriaMetrics
2. import raw EVCC history from InfluxDB v1 with `vmctl influx`
3. validate raw coverage with `check_data.py` and `compare_import_coverage.py`
4. normalize infrastructure labels such as `host` when the checker requires it
5. run `evcc-vm-rollup.py` dry-run and write backfill for daily `evcc_*` metrics
6. connect Grafana to VictoriaMetrics and deploy dashboards
7. schedule the daily rollup refresh for completed local days

The release validation imported a real multi-year EVCC history into VictoriaMetrics, cleaned `host` labels, verified `db=0`, built rollups, and rendered the dashboard set against the migrated data.

## Dashboard Sets

Two dashboard sets are available:

- `DASHBOARD_SET=tabs`: recommended for Grafana 13.0.1 or newer
- `DASHBOARD_SET=default`: classic row-based layout for older Grafana versions or users who prefer rows

The release screenshots document the German generated TAB set with one screenshot per active tab under [screenshots/tabs](./screenshots/tabs/README.md).

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
- dashboard set
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
- German TAB dashboard screenshots for every active tab
- Grafana localization spot-checks for `de`, `fr`, and `zh`
- local static/unit/dashboard checks via `npm test`
