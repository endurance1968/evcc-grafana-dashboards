# Grafana mit Docker installieren

Diese Anleitung beschreibt eine einfache Grafana-Installation mit Docker.

Annahmen:

- Docker ist bereits installiert
- Grafana soll lokal mit persistentem Datenverzeichnis laufen
- Grafana soll später mit VictoriaMetrics als Datasource genutzt werden

Nicht Bestandteil dieser Anleitung:

- Installation von Docker selbst
- Installation von VictoriaMetrics selbst
- Dashboard-Deployment selbst

Dafür weiter mit:

- VictoriaMetrics mit Docker installieren:
  - `victoriametrics-install-docker.md`
- Grafana mit VictoriaMetrics und EVCC-Dashboards:
  - `grafana-vm-dashboard-setup.md`

## Verwendetes Image

Grafana empfiehlt aktuell die Verwendung von:

- `grafana/grafana`

Wichtig:

- `grafana/grafana-oss` wird laut offizieller Doku nicht mehr weiter aktualisiert
- `grafana/grafana` ist der richtige OSS-Dockerpfad

Quelle:

- [Run Grafana Docker image](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)

## Ziel

Am Ende läuft Grafana:

- auf Port `3000`
- mit persistentem Datenverzeichnis auf dem Host
- mit Webzugriff unter `http://<host>:3000`

## Schritt 1: Verzeichnis anlegen

```bash
mkdir -p /opt/grafana/data
cd /opt/grafana
```

## Schritt 2: Image laden

```bash
docker pull grafana/grafana
```

## Schritt 3: Container starten

```bash
docker run -d \
  --name grafana \
  --restart unless-stopped \
  -p 3000:3000 \
  -v /opt/grafana/data:/var/lib/grafana \
  grafana/grafana
```

## Bedeutung der wichtigsten Optionen

- `-p 3000:3000`
  - veröffentlicht Grafana auf Port `3000`
- `-v /opt/grafana/data:/var/lib/grafana`
  - speichert Benutzer, Datasources und Dashboards persistent auf dem Host
- `--restart unless-stopped`
  - startet Grafana nach Reboots automatisch neu

## Schritt 4: Funktion prüfen

Containerstatus:

```bash
docker ps | grep grafana
```

HTTP-Test:

```bash
curl -I http://127.0.0.1:3000
```

Browser:

- `http://<dein-host>:3000`

Standard-Login bei einer frischen Installation ist typischerweise:

- Benutzer: `admin`
- Passwort: `admin`

Beim ersten Login verlangt Grafana normalerweise direkt ein neues Passwort.

## Schritt 5: Logs prüfen

```bash
docker logs --tail 100 grafana
```

## Schritt 6: Container später aktualisieren

```bash
docker pull grafana/grafana
docker stop grafana
docker rm grafana
```

Danach denselben `docker run`-Befehl erneut ausführen.

Wichtig:

- das Host-Verzeichnis `/opt/grafana/data` bleibt bestehen
- dadurch bleiben Benutzer, Datasources und Dashboards erhalten

## Typische Stolperfallen

- Port `3000` ist schon belegt
- Volume fehlt, dadurch gehen Daten bei Container-Neustart verloren
- Standardpasswort wurde noch nicht geändert
- Grafana läuft, aber VictoriaMetrics-Datasource ist noch nicht angelegt

## Nächster Schritt

Wenn Grafana und VictoriaMetrics laufen, weiter mit:

- `grafana-vm-dashboard-setup.md`

