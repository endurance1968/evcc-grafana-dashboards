# Setup And Filter Status Panel

German version: [setup-filter-status-panel-decision.md](../../de/design/setup-filter-status-panel-decision.md).

## Decision

No permanently visible setup or filter status panel will be added to the standard dashboards.

The important deploy and filter values remain inspectable through these paths:

- `Build` variable in the dashboard header: shows deployment timestamp, language/variant, and source ref in the tooltip.
- Dashboard variables in Grafana: show effective values such as `peakPowerLimit`, `energySampleInterval`, `tariffPriceInterval`, `loadpointBlocklist`, `extBlocklist`, `auxBlocklist`, `vehicleBlocklist`, and `heatPumpLoadpointRegex`.
- `vm-dashboard-install.env`: remains the leading configuration source for deploy overrides.
- Troubleshooting docs: explain how to check EVCC labels and blocklists.

## Rationale

A visible status panel would consume dashboard space on every installation, although these values are mainly needed during setup, troubleshooting, or review. For normal use, energy, power, loadpoint, vehicle, and cost values are more important than internal filter configuration.

Such a panel could also imply that blocklists modify data. They do not: blocklists only filter the dashboard view and do not delete or migrate VictoriaMetrics series.

## When To Revisit

Revisit this decision if a dedicated diagnostics or setup tab is introduced that does not disturb the normal today, month, year, or all-time views. In that case, the panel should live there as an optional read-only panel and show:

- build info
- datasource UID
- important time intervals
- peak-power limit
- active blocklists
- heat-pump regex

## References

- Deploy options: [../vm-dashboard-install.md](../vm-dashboard-install.md)
- EVCC/Telegraf live ingest: [../evcc-telegraf-live-ingest.md](../evcc-telegraf-live-ingest.md)
- Troubleshooting for labels and blocklists: [../migration-troubleshooting.md#business-labels-titles-and-blocklists](../migration-troubleshooting.md#business-labels-titles-and-blocklists)