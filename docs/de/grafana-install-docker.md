# Grafana mit Docker installieren

Englische Version: [grafana-install-docker.md](../en/grafana-install-docker.md).

Pruefe vor den Kommandos zuerst die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Diese Anleitung beschreibt eine einfache Grafana-Installation mit Docker.

Annahmen:

- Docker ist bereits installiert.
- Grafana soll lokal mit persistentem Speicher laufen.
- Grafana nutzt spaeter VictoriaMetrics als Datasource.

Nicht enthalten:

- Docker selbst installieren
- VictoriaMetrics selbst installieren
- Dashboards deployen

Weiter mit:

- [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Docker-Image

Grafana empfiehlt aktuell:

- `grafana/grafana`

Wichtig:

- `grafana/grafana-oss` ist nicht mehr der zentrale gepflegte Image-Pfad.
- `grafana/grafana` ist der aktuelle OSS-freundliche Docker-Image-Pfad.

Referenz:

- [Run Grafana Docker image](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/)

## Ziel

Am Ende laeuft Grafana:

- auf Port `3000`
- mit persistentem Host-Speicher
- erreichbar unter `http://<host>:3000`

## 1. Datenverzeichnis erstellen

Linux-Host:

```bash
mkdir -p /opt/grafana/data
cd /opt/grafana
```

Windows Docker Desktop Host:

```powershell
New-Item -ItemType Directory -Force C:\evcc\grafana\data
```

Nutze diesen Windows-Pfad in der `-v`-Option, zum Beispiel `-v C:\evcc\grafana\data:/var/lib/grafana`.

## 2. Image ziehen

```bash
docker pull grafana/grafana
```

## 3. Container starten

```bash
docker run -d \
  --name grafana \
  --restart unless-stopped \
  -p 3000:3000 \
  -v /opt/grafana/data:/var/lib/grafana \
  -e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource \
  grafana/grafana
```

Windows PowerShell Beispiel:

```powershell
docker run -d `
  --name grafana `
  --restart unless-stopped `
  -p 3000:3000 `
  -v C:\evcc\grafana\data:/var/lib/grafana `
  -e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource `
  grafana/grafana
```

## Wichtige Optionen

- `-p 3000:3000`
  - veroeffentlicht Grafana auf Port `3000`
- `-v /opt/grafana/data:/var/lib/grafana`
  - haelt Nutzer, Datasources und Dashboards persistent auf dem Host
- `-e GF_INSTALL_PLUGINS=victoriametrics-metrics-datasource`
  - installiert das fuer diese Dashboards benoetigte Datasource Plugin
- `--restart unless-stopped`
  - startet Grafana nach Reboots automatisch wieder

## 4. Installation pruefen

Containerstatus:

```bash
docker ps | grep grafana
```

HTTP-Check:

```bash
curl -I http://127.0.0.1:3000
```

Browser:

- `http://<dein-host>:3000`

Eine frische Installation startet typischerweise mit:

- Benutzername: `admin`
- Passwort: `admin`

Grafana erzwingt beim ersten Login normalerweise eine Passwortaenderung.

## 5. Logs pruefen

```bash
docker logs --tail 100 grafana
```

## 6. Container spaeter aktualisieren

```bash
docker pull grafana/grafana
docker stop grafana
docker rm grafana
```

Danach dasselbe `docker run`-Kommando erneut ausfuehren.

Wichtig:

- Das Host-Verzeichnis `/opt/grafana/data` bleibt bestehen.
- Nutzer, Datasources und Dashboards bleiben erhalten.

## Haeufige Probleme

- Port `3000` ist bereits belegt; waehle einen anderen Host-Port wie `-p 13030:3000` und setze `GRAFANA_URL` spaeter auf diesen Host-Port.
- Volume fehlt, dadurch verschwinden Daten nach Container-Neuerstellung.
- Default-Passwort wurde noch nicht geaendert.
- Grafana laeuft, aber VictoriaMetrics-Datasource existiert noch nicht.

## Naechster Schritt

Wenn Grafana und VictoriaMetrics laufen, weiter mit:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)