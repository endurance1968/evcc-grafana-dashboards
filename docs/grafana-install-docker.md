# Install Grafana with Docker

Before running commands, review the central requirements overview: [system-requirements.md](./system-requirements.md).

This guide covers a simple Grafana installation with Docker.

Assumptions:

- Docker is already installed
- Grafana should run locally with persistent storage
- Grafana will later use VictoriaMetrics as its datasource

Not covered here:

- installing Docker itself
- installing VictoriaMetrics itself
- deploying dashboards

Continue with:

- [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Docker image

Grafana currently recommends:

- `grafana/grafana`

Important:

- `grafana/grafana-oss` is no longer the main maintained image path
- `grafana/grafana` is the correct current OSS-friendly Docker image path

Reference:

- [Run Grafana Docker image](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)

## Goal

At the end, Grafana runs:

- on port `3000`
- with persistent host storage
- reachable at `http://<host>:3000`

## 1. Create the data directory

Linux host:

```bash
mkdir -p /opt/grafana/data
cd /opt/grafana
```

Windows Docker Desktop host:

```powershell
New-Item -ItemType Directory -Force C:\evcc\grafana\data
```

Use that Windows path in the `-v` option, for example `-v C:\evcc\grafana\data:/var/lib/grafana`.

## 2. Pull the image

```bash
docker pull grafana/grafana
```

## 3. Start the container

```bash
docker run -d \
  --name grafana \
  --restart unless-stopped \
  -p 3000:3000 \
  -v /opt/grafana/data:/var/lib/grafana \
  -e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource \
  grafana/grafana
```

Windows PowerShell example:

```powershell
docker run -d `
  --name grafana `
  --restart unless-stopped `
  -p 3000:3000 `
  -v C:\evcc\grafana\data:/var/lib/grafana `
  -e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource `
  grafana/grafana
```

## Important options

- `-p 3000:3000`
  - publishes Grafana on port `3000`
- `-v /opt/grafana/data:/var/lib/grafana`
  - keeps users, datasources, and dashboards persistent on the host
- `-e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource`
  - installs the datasource plugin needed by these dashboards
- `--restart unless-stopped`
  - starts Grafana again automatically after reboots

## 4. Verify the installation

Container status:

```bash
docker ps | grep grafana
```

HTTP check:

```bash
curl -I http://127.0.0.1:3000
```

Browser:

- `http://<your-host>:3000`

A fresh installation typically starts with:

- username: `admin`
- password: `admin`

Grafana will normally force a password change on first login.

## 5. Check logs

```bash
docker logs --tail 100 grafana
```

## 6. Update the container later

```bash
docker pull grafana/grafana
docker stop grafana
docker rm grafana
```

Then run the same `docker run` command again.

Important:

- the host directory `/opt/grafana/data` remains in place
- users, datasources, and dashboards stay available

## Common issues

- port `3000` is already in use; choose another host port such as `-p 13030:3000` and set `GRAFANA_URL` to that host port later
- the volume is missing, so data disappears after container recreation
- the default password was not changed
- Grafana is running but the VictoriaMetrics datasource does not exist yet

## Next step

Once Grafana and VictoriaMetrics are running, continue with:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)
