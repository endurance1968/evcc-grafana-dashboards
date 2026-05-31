# VictoriaMetrics auf Debian 13 installieren

Englische Version: [victoriametrics-install-debian-13_EN.md](./victoriametrics-install-debian-13_EN.md).

Pruefe vor den Kommandos zuerst die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Diese Anleitung beschreibt die Installation einer aktuellen Single-Node-VictoriaMetrics-Instanz auf einer Debian-13-VM oder einem Debian-13-LXC.

## Validierungsstatus

Diese Anleitung wurde im Rahmen der ersten Endnutzer-Release-Vorbereitung manuell ausgefuehrt und validiert.

Aktueller Status:

- VictoriaMetrics-Installation: getestet
- Servicestart per `systemd`: auf normaler Debian-VM/LXC getestet
- Blank-`debian:trixie` Docker-Validierung: am 2026-05-29 getestet
- VictoriaMetrics laeuft nach Installation: bestaetigt

Docker-Validierungshinweis:

Ein Standard-`debian:trixie` Docker-Container laeuft nicht mit `systemd`. In dieser Umgebung koennen Paket- und Service-Datei-Schritte geprueft werden, aber `systemctl enable --now ...` muss uebersprungen werden. Fuer den Release-Check vom 2026-05-29 wurde VictoriaMetrics manuell mit demselben Binary, Nutzer, Datenpfad und denselben Flags wie in der Service-Datei gestartet; `/health` meldete `OK`.

Annahmen:

- Debian 13 laeuft bereits.
- Die Kommandos sind fuer einen Nutzer mit `sudo` geschrieben; wenn du als `root` angemeldet bist, lasse `sudo` weg.
- Du willst eine einzelne VictoriaMetrics-Instanz.
- Die Instanz soll lokal per `systemd` laufen.

Nicht enthalten:

- Grafana installieren
- EVCC/Telegraf-Live-Ingest konfigurieren
- Dashboard-Deployment

## Ziel

Am Ende laeuft VictoriaMetrics als `systemd`-Service:

- Binary: `victoria-metrics-prod`
- Migrationswerkzeug: `vmctl`
- HTTP-Port: `8428`
- Datenpfad: `/var/lib/victoria-metrics`
- Servicename: `victoriametrics`

## Welche Version?

Aktueller Community-Release fuer diese Anleitung:

- `v1.139.0`

Quellen:

- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)

Wichtig:

- VictoriaMetrics veroeffentlicht haeufig neue Versionen.
- Pruefe vor Installation immer die aktuelle Release-Seite.

## 1. Basispakete installieren

```bash
sudo apt update
sudo apt install -y curl wget tar ca-certificates
```

## 2. Passendes Release herunterladen

Fuer Debian 13 auf `amd64`:

```bash
cd /tmp
curl -fL -o victoria-metrics-linux-amd64-v1.139.0.tar.gz https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v1.139.0/victoria-metrics-linux-amd64-v1.139.0.tar.gz
```

Fuer `arm64` nutze:

- `victoria-metrics-linux-arm64-v1.139.0.tar.gz`

Systemarchitektur pruefen:

```bash
uname -m
```

Typische Werte:

- `x86_64` -> `amd64`
- `aarch64` -> `arm64`

## 3. Binary installieren

```bash
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-v1.139.0.tar.gz -C /usr/local/bin
```

Dann pruefen:

```bash
/usr/local/bin/victoria-metrics-prod --version
```

## 4. vmutils (`vmctl`) installieren

`vmctl` ist fuer Migrationen und Benchmarks nuetzlich. Fuer das normale Nicht-Docker-Setup installiere es zusammen mit VictoriaMetrics.

Fuer Debian 13 auf `amd64`:

```bash
cd /tmp
wget https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/v1.139.0/vmutils-linux-amd64-v1.139.0.tar.gz
tar xzf vmutils-linux-amd64-v1.139.0.tar.gz
sudo install -m 0755 vmctl-prod /usr/local/bin/vmctl
```

Fuer `arm64` nutze das passende Archiv:

- `vmutils-linux-arm64-v1.139.0.tar.gz`

Dann pruefen:

```bash
/usr/local/bin/vmctl --version
```

## 5. Systemnutzer und Datenverzeichnis anlegen

```bash
sudo useradd -r -s /usr/sbin/nologin victoriametrics
sudo mkdir -p /var/lib/victoria-metrics
sudo chown -R victoriametrics:victoriametrics /var/lib/victoria-metrics
```

## 6. systemd-Service erstellen

Service-Datei anlegen:

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

Hinweise:

- `-storageDataPath` ist der lokale Datenpfad.
- `-retentionPeriod=10y` haelt Daten zehn Jahre.
- `-selfScrapeInterval=10s` laesst VictoriaMetrics eigene interne Metriken von `/metrics` alle 10 Sekunden erfassen.

Das ist hilfreich, wenn du VictoriaMetrics-Interna schnell in `vmui` pruefen willst. Wenn du diese internen Metriken nicht brauchst, kannst du das Flag weglassen.

## 7. Service starten und aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victoriametrics.service
```

Status pruefen:

```bash
sudo systemctl status victoriametrics.service
```

## 8. Installation pruefen

Health Check:

```bash
curl -fsSL http://127.0.0.1:8428/health
```

Root-Seite:

```bash
curl -fsSL http://127.0.0.1:8428/
```

VMUI im Browser:

- `http://<dein-host>:8428/vmui`

## 9. Port optional im Netzwerk erreichbar machen

Wenn Grafana oder EVCC von einem anderen Host auf VictoriaMetrics zugreifen sollen, muss Port `8428` erreichbar sein.

Pruefen:

```bash
ss -ltnp | grep 8428
```

Wenn du eine Firewall nutzt, oeffne den Port auch dort.

## 10. Spaeter aktualisieren

Upgrade-Ablauf:

1. neues Release herunterladen
2. `victoria-metrics-prod`-Binary nach `/usr/local/bin` extrahieren
3. passendes `vmctl`-Binary nach `/usr/local/bin` extrahieren
4. Service neu starten

Beispiel:

```bash
sudo systemctl stop victoriametrics
sudo tar -xvf /tmp/victoria-metrics-linux-amd64-vX.Y.Z.tar.gz -C /usr/local/bin
sudo tar -xvf /tmp/vmutils-linux-amd64-vX.Y.Z.tar.gz -C /tmp
sudo install -m 0755 /tmp/vmctl-prod /usr/local/bin/vmctl
sudo systemctl start victoriametrics
```

Danach erneut pruefen:

```bash
/usr/local/bin/victoria-metrics-prod --version
/usr/local/bin/vmctl --version
sudo systemctl status victoriametrics
```

## 11. Fuer EVCC vorbereiten

Fuer EVCC und die Dashboards brauchst du nach dieser Installation normalerweise:

- VictoriaMetrics erreichbar unter `http://<host>:8428`
- `vmctl` lokal verfuegbar fuer optionale Import-Benchmarks und Migrationen
- eine aktuelle EVCC-Rohdatenpipeline nach VictoriaMetrics
- spaeter eine Grafana-Datasource auf diese VictoriaMetrics-URL

Richte als naechsten Schritt den Live-Ingest ein:

- [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md)

Wenn du von InfluxDB migrierst, pruefe zuerst, dass der Live-Ingest fuer neue Daten funktioniert. Importiere danach die Historie und erzeuge Rollups:

- [influx-to-vm-migration.md](./influx-to-vm-migration.md)

Wenn du ohne Historie neu startest, kannst du nach den ersten eingehenden Rohdaten direkt mit Grafana fortfahren.

## Haeufige Probleme

- falsche Architektur heruntergeladen (`amd64` vs. `arm64`)
- Datenpfad ist nicht beschreibbar
- Service-Nutzer hat keine Rechte auf `/var/lib/victoria-metrics`
- Port `8428` funktioniert lokal, ist extern aber blockiert
- Retention wurde zu kurz konfiguriert

## Quellen

- [VictoriaMetrics Quick Start](https://docs.victoriametrics.com/victoriametrics/quick-start/)
- [VictoriaMetrics Releases](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
