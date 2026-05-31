# VictoriaMetrics auf Debian 13 installieren

Englische Version: [victoriametrics-install-debian-13_EN.md](./victoriametrics-install-debian-13_EN.md).

Diese Anleitung beschreibt eine Single-Node-Installation von VictoriaMetrics auf Debian 13 / Trixie.

Pruefe vor Beginn die zentralen Voraussetzungen: [system-requirements.md](./system-requirements.md).

## Voraussetzungen

- Debian 13 System
- Root- oder sudo-Rechte
- ausreichend Speicher fuer EVCC-Rohdaten und Rollups
- Netzwerkzugriff fuer EVCC/Telegraf, Importwerkzeuge und Grafana

## Benutzer und Verzeichnisse

```bash
sudo useradd --system --home /var/lib/victoriametrics --shell /usr/sbin/nologin victoriametrics
sudo mkdir -p /var/lib/victoriametrics /etc/victoriametrics
sudo chown -R victoriametrics:victoriametrics /var/lib/victoriametrics
```

## Binary installieren

Lade ein passendes VictoriaMetrics-Release von GitHub, entpacke `victoria-metrics-prod` und installiere es nach `/usr/local/bin/victoria-metrics-prod`.

Pruefen:

```bash
/usr/local/bin/victoria-metrics-prod --version
```

## systemd Service

Beispiel `/etc/systemd/system/victoriametrics.service`:

```ini
[Unit]
Description=VictoriaMetrics single-node
After=network-online.target
Wants=network-online.target

[Service]
User=victoriametrics
Group=victoriametrics
ExecStart=/usr/local/bin/victoria-metrics-prod \
  -storageDataPath=/var/lib/victoriametrics \
  -retentionPeriod=10y \
  -httpListenAddr=:8428
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victoriametrics
sudo systemctl status victoriametrics
curl -fsSL http://localhost:8428/health
```

## Daten schreiben

EVCC-/Telegraf-Daten koennen per Influx-Line-Protocol geschrieben werden:

```text
http://<vm-host>:8428/influx/write
```

## Firewall

Oeffne Port `8428/tcp` nur fuer Hosts, die schreiben oder lesen muessen. Fuer oeffentliche Netze Reverse Proxy, Authentifizierung und TLS nutzen.

## Backup

Sichere `/var/lib/victoriametrics` regelmaessig. Bei Migrationen empfiehlt sich zusaetzlich eine temporaere Testinstanz, damit produktive Daten nur lesend verwendet werden.

## Naechste Schritte

- Grafana installieren: [grafana-install-debian-13.md](./grafana-install-debian-13.md)
- InfluxDB migrieren: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Dashboards deployen: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)