# VictoriaMetrics mit Docker installieren

Englische Version: [victoriametrics-install-docker_EN.md](./victoriametrics-install-docker_EN.md).

Diese Anleitung beschreibt eine einfache VictoriaMetrics-Single-Node-Installation mit Docker.

Pruefe vor Beginn die zentralen Voraussetzungen: [system-requirements.md](./system-requirements.md).

## Voraussetzungen

- Docker oder Docker Compose
- persistentes Volume fuer VictoriaMetrics-Daten
- Netzwerkzugriff von EVCC/Telegraf und Grafana auf VictoriaMetrics

## Docker Compose Beispiel

```yaml
services:
  victoriametrics:
    image: victoriametrics/victoria-metrics:v1.139.0
    container_name: victoriametrics
    restart: unless-stopped
    ports:
      - "8428:8428"
    command:
      - "-storageDataPath=/victoria-metrics-data"
      - "-retentionPeriod=10y"
    volumes:
      - vm-data:/victoria-metrics-data

volumes:
  vm-data:
```

Start:

```bash
docker compose up -d
curl -fsSL http://localhost:8428/health
```

## Daten schreiben

Influx-Line-Protocol kann nach VictoriaMetrics geschrieben werden:

```text
http://<vm-host>:8428/influx/write
```

Beispiel fuer Telegraf:

```toml
[[outputs.http]]
  alias = "victoriametrics_evcc"
  url = "http://<vm-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]
```

## Grafana anbinden

In Grafana die VictoriaMetrics Datasource mit URL `http://<vm-host>:8428` und UID `vm-evcc` anlegen.

## Backup

Das Volume `vm-data` enthaelt die Messdaten. Plane regelmaessige Backups und teste Restore-Prozesse, bevor du InfluxDB abschaltest.

## Naechste Schritte

- Neuer Stack: [grafana-install-docker.md](./grafana-install-docker.md)
- Migration: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Dashboards: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)