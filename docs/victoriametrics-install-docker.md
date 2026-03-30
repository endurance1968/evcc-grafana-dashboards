# VictoriaMetrics mit Docker installieren

Diese Anleitung beschreibt eine einfache Single-Node-Installation von VictoriaMetrics mit Docker.

Annahmen:

- Docker ist bereits installiert
- du willst eine einzelne VictoriaMetrics-Instanz betreiben
- die Daten sollen persistent auf dem Host liegen

Nicht Bestandteil dieser Anleitung:

- Installation von Docker selbst
- Migration von InfluxDB nach VictoriaMetrics
- Grafana- oder Dashboard-Deployment

Dafür weiter mit:

- InfluxDB -> VictoriaMetrics Migration:
  - [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Grafana mit VictoriaMetrics und EVCC-Dashboards:
  - [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Verwendetes Image

Diese Anleitung nutzt:

- `victoriametrics/victoria-metrics:v1.138.0`

Wichtig:

- die Version ist bewusst gepinnt
- prüfe bei Bedarf neuere Releases vor der Installation

Quellen:

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)

## Ziel

Am Ende läuft VictoriaMetrics:

- auf Port `8428`
- mit persistentem Datenverzeichnis auf dem Host
- mit Browser-Zugriff auf `vmui`

## Schritt 1: Verzeichnis anlegen

```bash
mkdir -p /opt/victoriametrics/data
cd /opt/victoriametrics
```

## Schritt 2: Image laden

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
```

## Schritt 3: Container starten

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

## Bedeutung der wichtigsten Optionen

- `-p 8428:8428`
  - veröffentlicht VictoriaMetrics auf Port `8428`
- `-v /opt/victoriametrics/data:/victoria-metrics-data`
  - speichert Daten persistent auf dem Host
- `--retentionPeriod=10y`
  - hält Daten für zehn Jahre
- `--selfScrapeInterval=10s`
  - sammelt die eigenen internen VM-Metriken alle 10 Sekunden ein

## Schritt 4: Funktion prüfen

Containerstatus:

```bash
docker ps | grep victoriametrics
```

Health-Check:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Browser:

- `http://<dein-host>:8428/vmui`

## Schritt 5: Logs prüfen

```bash
docker logs --tail 100 victoriametrics
```

## Schritt 6: Container später aktualisieren

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
docker stop victoriametrics
docker rm victoriametrics
```

Danach denselben `docker run`-Befehl erneut ausführen.

Wichtig:

- das Host-Verzeichnis `/opt/victoriametrics/data` bleibt dabei erhalten
- die Daten bleiben deshalb bestehen

## Typische Stolperfallen

- Port `8428` ist schon belegt
- das Host-Verzeichnis ist nicht beschreibbar
- keine Persistenz, wenn das Volume vergessen wurde
- Firewall blockiert Port `8428`

## Nächster Schritt

Wenn VictoriaMetrics läuft, weiter mit:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)
- oder bei bestehender InfluxDB zuerst mit:
  - [influx-to-vm-migration.md](./influx-to-vm-migration.md)

