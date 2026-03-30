# EVCC with VictoriaMetrics and Grafana

This is the fastest end-to-end entry point for a user who:

- already runs EVCC
- currently stores EVCC history in InfluxDB
- wants to move to VictoriaMetrics and the new EVCC dashboard set

## Recommended order

1. Install VictoriaMetrics
2. Install Grafana
3. Import historic InfluxDB raw data into VictoriaMetrics
4. Generate the daily rollups
5. Connect Grafana to VictoriaMetrics
6. Deploy the EVCC dashboards
7. Set up the hourly rollup refresh

## Choose your runtime

### Debian 13 VM or LXC

- VictoriaMetrics:
  - [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)
- Grafana:
  - [grafana-install-debian-13.md](./grafana-install-debian-13.md)

### Docker

- VictoriaMetrics:
  - [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- Grafana:
  - [grafana-install-docker.md](./grafana-install-docker.md)

## Then migrate data and build rollups

If you already have EVCC + InfluxDB, continue with:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

That guide covers:

- one-time raw-data import from InfluxDB into VictoriaMetrics
- initial rollup backfill
- ongoing hourly rollup refresh

## Then connect Grafana and deploy dashboards

Once VictoriaMetrics is running and the data is present, continue with:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

That guide covers:

- creating the VictoriaMetrics datasource in Grafana
- creating a Grafana service-account token
- the first dashboard deployment
- later dashboard updates

## Additional end-user deploy docs

- quick deploy guide:
  - [deployment-readme.md](./deployment-readme.md)
- technical deploy details:
  - [vm-dashboard-install.md](./vm-dashboard-install.md)

## Short version

For a typical migration from EVCC + InfluxDB to EVCC + VictoriaMetrics, there are really only three major blocks:

1. Get VictoriaMetrics running
2. Move raw data and rollups into VictoriaMetrics
3. Connect Grafana and deploy the dashboards
