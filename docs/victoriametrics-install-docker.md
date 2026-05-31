# VictoriaMetrics mit Docker installieren

Englische Version: [victoriametrics-install-docker_EN.md](./victoriametrics-install-docker_EN.md).

Pruefe vor den Befehlen die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Diese Anleitung beschreibt eine einfache VictoriaMetrics-Single-Node-Installation mit Docker.

Annahmen:

- Docker ist bereits installiert
- du moechtest eine einzelne VictoriaMetrics-Instanz betreiben
- die Daten sollen persistent auf dem Host gespeichert werden

Nicht Teil dieser Anleitung:

- Docker selbst installieren
- Migration von InfluxDB nach VictoriaMetrics
- Grafana oder Dashboard-Deployment

Weiterfuehrend:

- [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md)
- [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Docker-Image

Diese Anleitung verwendet:

- `victoriametrics/victoria-metrics:v1.138.0`

Wichtig:

- die Version ist absichtlich fest gepinnt
- pruefe bei Bedarf, ob es neuere Releases gibt

Quellen:

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)

## Zielzustand

Am Ende laeuft VictoriaMetrics:

- auf Port `8428`
- mit persistentem Host-Speicher
- mit Browserzugriff auf `vmui`

## 1. Datenverzeichnis anlegen

Linux-Host:

```bash
mkdir -p /opt/victoriametrics/data
cd /opt/victoriametrics
```

Windows-Docker-Desktop-Host:

```powershell
New-Item -ItemType Directory -Force C:\evcc\victoriametrics\data
```

Verwende diesen Windows-Pfad in der Option `-v`, zum Beispiel `-v C:\evcc\victoriametrics\data:/victoria-metrics-data`.

## 2. Image laden

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
```

## 3. Container starten

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

Windows-PowerShell-Beispiel:

```powershell
docker run -d `
  --name victoriametrics `
  --restart unless-stopped `
  -p 8428:8428 `
  -v C:\evcc\victoriametrics\data:/victoria-metrics-data `
  victoriametrics/victoria-metrics:v1.138.0 `
  --storageDataPath=/victoria-metrics-data `
  --retentionPeriod=10y `
  --selfScrapeInterval=10s
```

## Wichtige Optionen

- `-p 8428:8428`
  - veroeffentlicht VictoriaMetrics auf Port `8428`
- `-v /opt/victoriametrics/data:/victoria-metrics-data`
  - speichert Daten persistent auf dem Host
- `--retentionPeriod=10y`
  - behaelt Daten zehn Jahre
- `--selfScrapeInterval=10s`
  - sammelt interne VictoriaMetrics-Metriken alle 10 Sekunden

## 4. Installation pruefen

Containerstatus:

```bash
docker ps | grep victoriametrics
```

Healthcheck:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Browser:

- `http://<dein-host>:8428/vmui`

## 5. Logs pruefen

```bash
docker logs --tail 100 victoriametrics
```

## 6. Container spaeter aktualisieren

```bash
docker pull victoriametrics/victoria-metrics:v1.138.0
docker stop victoriametrics
docker rm victoriametrics
```

Danach denselben `docker run`-Befehl erneut ausfuehren.

Wichtig:

- das Host-Verzeichnis `/opt/victoriametrics/data` bleibt erhalten
- die gespeicherten Daten bleiben verfuegbar

## Haeufige Probleme

- Port `8428` ist bereits belegt; waehle einen anderen Host-Port, zum Beispiel `-p 18428:8428`, und verwende diesen Port in Checks und Datasource-URLs
- das Host-Verzeichnis ist nicht beschreibbar
- keine Persistenz, weil das Volume vergessen wurde
- die Firewall blockiert Port `8428`

## Naechster Schritt

Wenn VictoriaMetrics laeuft, richte zuerst den aktuellen EVCC-Schreibpfad ein:

- [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md)

Danach:

- bei vorhandener InfluxDB-Historie: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- ohne Historie oder nach abgeschlossener Migration: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)
