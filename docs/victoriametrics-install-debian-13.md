# VictoriaMetrics auf Debian 13 installieren

Diese Anleitung beschreibt die Installation einer aktuellen Single-Node-VictoriaMetrics-Instanz auf einer Debian-13-VM oder einem Debian-13-LXC.

Annahmen:

- Debian 13 läuft bereits
- du willst eine einzelne VictoriaMetrics-Instanz betreiben
- die Instanz soll lokal per `systemd` laufen

Nicht Bestandteil dieser Anleitung:

- Grafana-Installation
- EVCC-Konfiguration
- Dashboard-Deployment

## Ziel

Am Ende läuft VictoriaMetrics als `systemd`-Service:

- Binary: `victoria-metrics-prod`
- HTTP-Port: `8428`
- Datenpfad: `/var/lib/victoria-metrics`
- Service-Name: `victoriametrics`

## Welche Version?

Stand heute ist die aktuelle Community-Version laut GitHub Releases:

- `v1.133.0`

Quelle:

- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)

Wichtig:

- VictoriaMetrics entwickelt sich schnell
- prüfe vor der Installation immer die aktuelle Release-Seite

## Schritt 1: Basis-Pakete installieren

```bash
sudo apt update
sudo apt install -y curl tar ca-certificates
```

## Schritt 2: Passendes Release herunterladen

Für Debian 13 auf `amd64`:

```bash
cd /tmp
curl -fL -o victoria-metrics-linux-amd64-v1.133.0.tar.gz https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v1.133.0/victoria-metrics-linux-amd64-v1.133.0.tar.gz
```

Für `arm64` muss der Dateiname entsprechend angepasst werden:

- `victoria-metrics-linux-arm64-v1.133.0.tar.gz`

Wenn du vor dem Download prüfen willst, welche Architektur dein System hat:

```bash
uname -m
```

Typische Werte:

- `x86_64` -> `amd64`
- `aarch64` -> `arm64`

## Schritt 3: Binary installieren

```bash
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-v1.133.0.tar.gz -C /usr/local/bin
```

Danach prüfen:

```bash
/usr/local/bin/victoria-metrics-prod --version
```

## Schritt 4: Systembenutzer und Datenverzeichnis anlegen

```bash
sudo useradd -r -s /usr/sbin/nologin victoriametrics
sudo mkdir -p /var/lib/victoria-metrics
sudo chown -R victoriametrics:victoriametrics /var/lib/victoria-metrics
```

## Schritt 5: systemd-Service anlegen

Datei anlegen:

```bash
sudo editor /etc/systemd/system/victoriametrics.service
```

Inhalt:

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
  -retentionPeriod=365d \
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

Hinweise:

- `-storageDataPath` ist dein lokaler Datenpfad
- `-retentionPeriod=365d` ist nur ein Beispiel
- `-selfScrapeInterval=10s` ist praktisch für erste Funktionstests

## Schritt 6: Service starten und aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victoriametrics.service
```

Status prüfen:

```bash
sudo systemctl status victoriametrics.service
```

## Schritt 7: Funktion prüfen

Health-Check:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Root-Seite:

```bash
curl -fsSL http://127.0.0.1:8428/
```

VMUI im Browser:

- `http://<dein-host>:8428/vmui`

## Schritt 8: Optional Port im Netzwerk freigeben

Wenn Grafana oder EVCC von einem anderen Host zugreifen sollen, muss Port `8428` erreichbar sein.

Prüfen:

```bash
ss -ltnp | grep 8428
```

Wenn eine Firewall aktiv ist, musst du den Port dort zusätzlich freigeben.

## Schritt 9: Upgrade auf eine neuere Version

Upgrade-Ablauf:

1. neues Release herunterladen
2. Binary nach `/usr/local/bin` entpacken
3. Service neu starten

Beispiel:

```bash
sudo systemctl stop victoriametrics
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-vX.Y.Z.tar.gz -C /usr/local/bin
sudo systemctl start victoriametrics
```

Danach wieder prüfen:

```bash
/usr/local/bin/victoria-metrics-prod --version
sudo systemctl status victoriametrics
```

## Schritt 10: Für EVCC vorbereiten

Für den späteren EVCC- und Dashboard-Betrieb brauchst du typischerweise:

- VictoriaMetrics erreichbar unter `http://<host>:8428`
- Grafana-Datasource auf diese URL
- EVCC oder Migrations-/Rollup-Skripte, die auf diese URL schreiben bzw. lesen

Die eigentliche Influx->VictoriaMetrics-Migration ist separat beschrieben in:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

## Typische Stolperfallen

- falsche Architektur geladen (`amd64` vs. `arm64`)
- Datenpfad nicht beschreibbar
- Service-Benutzer hat keine Rechte auf `/var/lib/victoria-metrics`
- Port `8428` ist lokal ok, aber von außen geblockt
- Retention zu knapp gewählt

## Quellen

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)

