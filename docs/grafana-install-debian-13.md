# Install Grafana on Debian 13

This guide covers a straightforward Grafana installation on a Debian 13 VM or Debian 13 LXC.

## Validation status

Current status:

- Grafana APT repository setup: tested on blank `debian:trixie` Docker on 2026-05-29
- `grafana-enterprise` installation: tested
- Grafana HTTP/API health check: confirmed
- VictoriaMetrics datasource plugin installation for this dashboard set: tested

Docker validation note:

A standard `debian:trixie` Docker container does not run `systemd`. In that environment, the package installation can be checked, but `systemctl enable --now grafana-server` must be skipped. For the 2026-05-29 release check, Grafana was started manually with the same Debian package paths as the service file, and `/api/health` returned `database: ok`.

Assumptions:

- Debian 13 is already running
- the commands below are written for a user with `sudo`; if you are logged in as `root`, omit `sudo`
- you want to run Grafana locally via `systemd`
- Grafana will later use VictoriaMetrics as its datasource

Not covered here:

- installing VictoriaMetrics itself
- migrating from InfluxDB to VictoriaMetrics
- deploying the EVCC dashboards

For those topics, continue with:

- [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)
- [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Recommended installation path

For Debian 13, the recommended path is the official Grafana APT repository.

Benefits:

- easy updates through `apt`
- no manual `.deb` handling
- a clean `systemd` service

Official reference:

- [Install Grafana on Debian or Ubuntu](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)

## Which edition?

Grafana currently documents:

- `grafana-enterprise` as the default package
- `grafana` as the OSS package

Important:

- `grafana-enterprise` can be used without a paid license
- for normal EVCC setups this is usually fine
- if you explicitly want OSS only, install `grafana` instead

This guide uses:

- `grafana-enterprise`

## 1. Install base packages

```bash
sudo apt update
sudo apt install -y apt-transport-https wget gnupg curl
```

## 2. Add the Grafana APT key

```bash
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
```

## 3. Add the Grafana repository

For stable releases:

```bash
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
```

Then refresh the package index:

```bash
sudo apt update
```

## 4. Install Grafana

Recommended default edition:

```bash
sudo apt install -y grafana-enterprise
```

If you explicitly want the OSS package:

```bash
sudo apt install -y grafana
```

## 5. Install The VictoriaMetrics Datasource Plugin

The EVCC dashboards use the VictoriaMetrics datasource plugin. Install it before creating the datasource:

```bash
sudo grafana cli \
  --homepath=/usr/share/grafana \
  --pluginsDir /var/lib/grafana/plugins \
  plugins install victoriametrics-metrics-datasource
```

The explicit `--homepath` and `--pluginsDir` flags are important for the Debian package layout. A plain `grafana cli plugins install ...` can fail because it cannot find the packaged Grafana home path.

Restart Grafana after installing or updating plugins.

## 6. Start and enable Grafana

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now grafana-server
```

Check status:

```bash
sudo systemctl status grafana-server
```

## 7. Verify the installation

Local check:

```bash
curl -I http://127.0.0.1:3000
```

Browser:

- `http://<your-host>:3000`

A fresh installation typically starts with:

- username: `admin`
- password: `admin`

Grafana will normally force a password change on first login.

## 8. Verify network access

If Grafana should be reachable from another host:

- port `3000` must be open

Check:

```bash
ss -ltnp | grep 3000
```

If you use a firewall, allow port `3000` there as well.

## 9. Updates

If Grafana was installed from the APT repository, updates work through `apt`:

```bash
sudo apt update
sudo apt upgrade
```

To update Grafana only:

```bash
sudo apt update
sudo apt install grafana-enterprise
```

or for OSS:

```bash
sudo apt update
sudo apt install grafana
```

## 10. Prepare for EVCC

Once Grafana is running, the next normal step is:

1. create the VictoriaMetrics datasource
2. create a Grafana service-account token
3. deploy the EVCC dashboards

Continue with:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Notes for LXC

For a normal Debian LXC, the same steps usually work unchanged.

Main things to watch:

- assign enough RAM
- make port `3000` reachable from the host or network
- keep time and timezone correct inside the container

Grafana itself typically needs at least about:

- 512 MB RAM recommended
- 1 CPU core recommended

## Common issues

- missing or incorrectly installed repository key
- port `3000` open locally but blocked on the network
- default password not changed yet
- VictoriaMetrics datasource not created yet
- later dashboard deploy fails because no service-account token exists

## Sources

- [Install Grafana on Debian or Ubuntu](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)
- [Grafana installation overview](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)
