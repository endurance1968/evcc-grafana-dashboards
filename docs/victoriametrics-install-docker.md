# Install VictoriaMetrics with Docker

This guide covers a simple single-node VictoriaMetrics installation with Docker.

Assumptions:

- Docker is already installed
- you want a single VictoriaMetrics instance
- the data should be stored persistently on the host

Not covered here:

- installing Docker itself
- migrating from InfluxDB to VictoriaMetrics
- Grafana or dashboard deployment

Continue with:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Docker image

This guide uses:

- `victoriametrics/victoria-metrics:v1.138.0`

Important:

- the version is pinned on purpose
- check for newer releases when needed

Sources:

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)

## Goal

At the end, VictoriaMetrics runs:

- on port `8428`
- with persistent host storage
- with browser access to `vmui`

## 1. Create the data directory

```bash
mkdir -p /opt/victoriametrics/data
cd /opt/victoriametrics
```

## 2. Pull the image

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
```

## 3. Start the container

```bash
docker run -d \
  --name victoriametrics \
  --restart unless-stopped \
  -p 8428:8428 \
  -v /opt/victoriametrics/data:/victoria-metrics-data \
  victoriametrics/victoria-metrics:v1.138.0 \
  --storageDataPath=/victoria-metrics-data \
  --retentionPeriod=10y \
  --selfScrapeInterval=10s
```

## Important options

- `-p 8428:8428`
  - publishes VictoriaMetrics on port `8428`
- `-v /opt/victoriametrics/data:/victoria-metrics-data`
  - stores data persistently on the host
- `--retentionPeriod=10y`
  - keeps data for ten years
- `--selfScrapeInterval=10s`
  - collects VictoriaMetrics internal metrics every 10 seconds

## 4. Verify the installation

Container status:

```bash
docker ps | grep victoriametrics
```

Health check:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Browser:

- `http://<your-host>:8428/vmui`

## 5. Check logs

```bash
docker logs --tail 100 victoriametrics
```

## 6. Update the container later

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
docker stop victoriametrics
docker rm victoriametrics
```

Then run the same `docker run` command again.

Important:

- the host directory `/opt/victoriametrics/data` remains in place
- the stored data remains available

## Common issues

- port `8428` is already in use
- the host directory is not writable
- no persistence because the volume was forgotten
- the firewall blocks port `8428`

## Next step

Once VictoriaMetrics is running, continue with:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)
- or, if you already have InfluxDB history, first:
  - [influx-to-vm-migration.md](./influx-to-vm-migration.md)
