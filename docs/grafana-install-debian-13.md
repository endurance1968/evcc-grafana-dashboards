# Grafana auf Debian 13 installieren

Englische Version: [grafana-install-debian-13_EN.md](./grafana-install-debian-13_EN.md).

Diese Anleitung beschreibt eine frische Grafana-Installation auf Debian 13 / Trixie fuer die EVCC/VictoriaMetrics-Dashboards.

Pruefe vor Beginn die zentralen Voraussetzungen: [system-requirements.md](./system-requirements.md).

## Voraussetzungen

- Debian 13 System
- Root- oder sudo-Rechte
- Netzwerkzugriff auf VictoriaMetrics
- Grafana 13.0.1 oder neuer

## Grafana installieren

Folge der offiziellen Grafana-Paketinstallation fuer Debian. Danach den Dienst starten und aktivieren:

```bash
sudo systemctl enable --now grafana-server
sudo systemctl status grafana-server
```

Grafana ist standardmaessig unter `http://<host>:3000` erreichbar.

## Admin-Zugang absichern

Beim ersten Login das Standardpasswort aendern. Fuer automatisches Deployment einen Service Account statt eines persoenlichen Admin-Tokens verwenden.

## VictoriaMetrics Datasource Plugin installieren

Installiere das Plugin und starte Grafana neu:

```bash
sudo grafana-cli plugins install victoriametrics-metrics-datasource
sudo systemctl restart grafana-server
```

## Datasource konfigurieren

1. In Grafana `Connections` / `Data sources` oeffnen.
2. VictoriaMetrics Datasource auswaehlen.
3. URL setzen, z. B. `http://127.0.0.1:8428` oder die Adresse deines VM-Servers.
4. UID auf `vm-evcc` setzen.
5. `Save & test` ausfuehren.

## Service-Account-Token erzeugen

1. `Administration` / `Service accounts` oeffnen.
2. Service Account fuer Dashboard-Deployment anlegen.
3. Token erzeugen.
4. Token in `vm-dashboard-install.env` setzen:

```env
GRAFANA_API_TOKEN=<token>
```

## Firewall

Wenn Grafana von anderen Hosts erreichbar sein soll, Port `3000/tcp` freigeben. In produktiven Setups Reverse Proxy und TLS verwenden.

## Naechster Schritt

Weiter mit [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).