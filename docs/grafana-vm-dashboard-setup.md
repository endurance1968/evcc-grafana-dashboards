# Grafana VM Dashboard Setup

Englische Version: [grafana-vm-dashboard-setup_EN.md](./grafana-vm-dashboard-setup_EN.md).

Diese Anleitung installiert die EVCC-Dashboards in Grafana und verbindet sie mit einer VictoriaMetrics-Datasource.

Pruefe vor Beginn die zentralen Voraussetzungen: [system-requirements.md](./system-requirements.md).

## Voraussetzungen

- Grafana 13.0.1 oder neuer
- VictoriaMetrics Datasource Plugin
- eine erreichbare VictoriaMetrics-Instanz mit EVCC-Daten
- Datasource UID `vm-evcc` oder ein eigener UID-Wert in `GRAFANA_DS_VM_EVCC_UID`
- Service-Account-Token fuer Grafana oder Basic Auth

`deploy-python.sh` ist der empfohlene Linux-Pfad. `deploy-bash.sh` bleibt fuer Systeme mit Bash und `jq` verfuegbar. Windows nutzt `deploy.ps1`.

## 1. Datasource anlegen

In Grafana:

1. `Connections` / `Data sources` oeffnen.
2. VictoriaMetrics Datasource auswaehlen.
3. URL deiner VictoriaMetrics-Instanz setzen, z. B. `http://victoriametrics:8428`.
4. UID auf `vm-evcc` setzen oder spaeter `GRAFANA_DS_VM_EVCC_UID` anpassen.
5. `Save & test` ausfuehren.

## 2. Deploy-Dateien herunterladen

Linux:

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Optionaler Bash-Deployer:

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
chmod +x deploy-bash.sh
sudo apt install -y jq
```

Windows:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

## 3. Konfiguration bearbeiten

Minimal:

```env
GRAFANA_URL=http://<grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<service-account-token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
PURGE=false
PURGE_ONLY=false
```

Der Default importiert die generierten deutschen Dashboards. `DASHBOARD_VARIANT=orig` ist nur fuer die englischen Original-Quelldashboards gedacht und bleibt unabhaengig von `DASHBOARD_LANGUAGE` Englisch.

Persoenliche Dashboard-Overrides koennen in derselben Env-Datei stehen:

```env
DASHBOARD_INSTALLED_WATT_PEAK=22
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^Altherma-3$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_EVCC_URL=http://192.168.1.197:7070/#/
DASHBOARD_PORTAL_TITLE=VRM
DASHBOARD_PORTAL_URL=https://vrm.victronenergy.com/installation/795774/dashboard
```

Wenn die Dashboard-Dateien von einem selbst gehosteten Raw-Endpunkt statt GitHub kommen sollen:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Jeder Key darf nur einmal aktiv gesetzt sein. Kommentiere alte Alternativen aus.

## 4. Deployment ausfuehren

Linux:

```bash
./deploy-python.sh
```

Bash-Variante:

```bash
./deploy-bash.sh
```

Windows:

```powershell
.\deploy.ps1
```

Der Deployer zeigt zuerst eine Preflight-Zusammenfassung und fragt nach Bestaetigung.

## 5. Ergebnis pruefen

In Grafana:

- Ordner `EVCC` existiert.
- Dashboards `Today`, `Today - Details Tabs`, `Month Tabs`, `Year Tabs`, `All-time Tabs` sind vorhanden.
- `Today` zeigt aktuelle Rohdaten.
- Langzeit-Dashboards zeigen Daten, sobald `evcc_*` Rollups vorhanden sind.
- Keine Panels zeigen Datasource- oder Query-Fehler.

## 6. Update und Neuaufbau

Normales Update:

```bash
./deploy-python.sh --purge false
```

Bewusster Neuaufbau:

```bash
./deploy-python.sh --purge true
```

Nur loeschen, ohne Re-Import:

```bash
./deploy-python.sh --purge-only true
```

PowerShell verwendet entsprechend `-purge false`, `-purge true` oder `-purgeonly true`.

## Naechste Schritte

- Rollup einrichten: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Deployer-Optionen: [vm-dashboard-install.md](./vm-dashboard-install.md)
- Troubleshooting: [migration-troubleshooting.md](./migration-troubleshooting.md)