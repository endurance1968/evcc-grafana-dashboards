# Install VictoriaMetrics on Debian 13

This guide covers the installation of a current single-node VictoriaMetrics instance on a Debian 13 VM or Debian 13 LXC.

Assumptions:

- Debian 13 is already running
- you want a single VictoriaMetrics instance
- the instance should run locally via `systemd`

Not covered here:

- installing Grafana
- EVCC configuration
- dashboard deployment

## Goal

At the end, VictoriaMetrics runs as a `systemd` service:

- binary: `victoria-metrics-prod`
- HTTP port: `8428`
- data path: `/var/lib/victoria-metrics`
- service name: `victoriametrics`

## Which version?

As of now, the current community release is:

- `v1.138.0`

Sources:

- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)

Important:

- VictoriaMetrics moves quickly
- always verify the latest release page before installation

## 1. Install base packages

```bash
sudo apt update
sudo apt install -y curl tar ca-certificates
```

## 2. Download the correct release

For Debian 13 on `amd64`:

```bash
cd /tmp
curl -fL -o victoria-metrics-linux-amd64-v1.138.0.tar.gz https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v1.138.0/victoria-metrics-linux-amd64-v1.138.0.tar.gz
```

For `arm64`, use:

- `victoria-metrics-linux-arm64-v1.138.0.tar.gz`

To check your system architecture:

```bash
uname -m
```

Typical values:

- `x86_64` -> `amd64`
- `aarch64` -> `arm64`

## 3. Install the binary

```bash
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-v1.138.0.tar.gz -C /usr/local/bin
```

Then verify:

```bash
/usr/local/bin/victoria-metrics-prod --version
```

## 4. Create the system user and data directory

```bash
sudo useradd -r -s /usr/sbin/nologin victoriametrics
sudo mkdir -p /var/lib/victoria-metrics
sudo chown -R victoriametrics:victoriametrics /var/lib/victoria-metrics
```

## 5. Create the systemd service

Create the service file:

```bash
sudo editor /etc/systemd/system/victoriametrics.service
```

Content:

```ini
[Unit]
Description=VictoriaMetrics service
After=network.target

[Service]
Type=simple
User=victoriametrics
Group=victoriametrics
ExecStart=/usr/local/bin/victoria-metrics-prod \
  -storageDataPath=/var/lib/victoria-metrics \
  -retentionPeriod=10y \
  -selfScrapeInterval=10s
SyslogIdentifier=victoriametrics
Restart=always

PrivateTmp=yes
ProtectHome=yes
NoNewPrivileges=yes
ProtectSystem=full

[Install]
WantedBy=multi-user.target
```

Notes:

- `-storageDataPath` is the local data path
- `-retentionPeriod=10y` keeps data for ten years
- `-selfScrapeInterval=10s` tells VictoriaMetrics to scrape its own internal metrics from `/metrics` every 10 seconds

That is useful if you want to inspect VictoriaMetrics internals quickly in `vmui`. If you do not need those internal metrics, you can omit the flag.

## 6. Start and enable the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victoriametrics.service
```

Check status:

```bash
sudo systemctl status victoriametrics.service
```

## 7. Verify the installation

Health check:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Root page:

```bash
curl -fsSL http://127.0.0.1:8428/
```

VMUI in the browser:

- `http://<your-host>:8428/vmui`

## 8. Optionally expose the port to the network

If Grafana or EVCC should access VictoriaMetrics from another host, port `8428` must be reachable.

Check:

```bash
ss -ltnp | grep 8428
```

If you use a firewall, open the port there as well.

## 9. Upgrade later

Upgrade flow:

1. download the new release
2. extract the binary into `/usr/local/bin`
3. restart the service

Example:

```bash
sudo systemctl stop victoriametrics
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-vX.Y.Z.tar.gz -C /usr/local/bin
sudo systemctl start victoriametrics
```

Then verify again:

```bash
/usr/local/bin/victoria-metrics-prod --version
sudo systemctl status victoriametrics
```

## 10. Prepare for EVCC

For EVCC and the dashboard set, you normally need:

- VictoriaMetrics reachable at `http://<host>:8428`
- a Grafana datasource pointing to that URL
- EVCC or migration and rollup scripts reading from or writing to that URL

The InfluxDB-to-VictoriaMetrics migration is described separately:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

## Common issues

- wrong architecture downloaded (`amd64` vs. `arm64`)
- data path is not writable
- the service user does not have permissions on `/var/lib/victoria-metrics`
- port `8428` works locally but is blocked externally
- retention was configured too short

## Sources

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
