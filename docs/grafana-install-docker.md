# Grafana mit Docker installieren

Englische Version: [grafana-install-docker_EN.md](./grafana-install-docker_EN.md).

Diese Anleitung beschreibt eine einfache Grafana-Installation per Docker fuer die EVCC/VictoriaMetrics-Dashboards.

Pruefe vor Beginn die zentralen Voraussetzungen: [system-requirements.md](./system-requirements.md).

## Voraussetzungen

- Docker oder Docker Compose
- persistentes Volume fuer Grafana-Daten
- Netzwerkzugriff von Grafana auf VictoriaMetrics

## Docker Compose Beispiel

```yaml
services:
  grafana:
    image: grafana/grafana:13.0.1
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: change-me

volumes:
  grafana-data:
```

Start:

```bash
docker compose up -d
```

Grafana ist danach unter `http://<host>:3000` erreichbar.

## VictoriaMetrics Datasource Plugin

Installiere das VictoriaMetrics Datasource Plugin in Grafana. Je nach Setup geht das ueber die Grafana-Oberflaeche oder per Container-Environment:

```yaml
environment:
  GF_INSTALL_PLUGINS: victoriametrics-metrics-datasource
```

Nach Plugin-Installation Grafana neu starten.

## Datasource anlegen

1. In Grafana `Connections` / `Data sources` oeffnen.
2. VictoriaMetrics Datasource auswaehlen.
3. URL setzen, z. B. `http://victoriametrics:8428`.
4. UID auf `vm-evcc` setzen.
5. `Save & test` ausfuehren.

## Service-Account-Token

Fuer die Deploy-Skripte wird ein Service-Account-Token empfohlen:

1. `Administration` / `Service accounts` oeffnen.
2. Service Account mit Rechten fuer Dashboard-Import anlegen.
3. Token erzeugen.
4. Token in `vm-dashboard-install.env` als `GRAFANA_API_TOKEN` setzen.

## Dashboard Deployment

Weiter mit [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).