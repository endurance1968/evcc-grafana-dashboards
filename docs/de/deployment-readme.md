# Dashboard Deployment Kurzstart

Dies ist die kurze Deployment-Referenz. Vor dem Dashboard-Deployment muessen aktuelle EVCC-Rohdaten in VictoriaMetrics ankommen; siehe [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md). Fuer die vollstaendige Anleitung nutze [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). Fuer alle Konfigurationsoptionen nutze [vm-dashboard-install.md](./vm-dashboard-install.md).

Englische Version: [deployment-readme.md](../en/deployment-readme.md).

## Empfohlener Pfad

Die Beispiele nutzen GitHub als `BASE`. Fuer ein lokales Forgejo-Repository setze `BASE` stattdessen auf den Raw-Root, typischerweise `http://<server:port>/<owner>/<repo>/raw/branch/main`.

Linux / Raspberry Pi:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-python.sh "$BASE/scripts/deploy-python.sh"
curl -fsSLo vm-dashboard-install.env.example "$BASE/scripts/vm-dashboard-install.env.example"
chmod +x deploy-python.sh
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Windows / PowerShell:

```powershell
$Base = "https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# $Base = "http://<server:port>/<owner>/<repo>/raw/branch/main"

Invoke-WebRequest "$Base/scripts/deploy.ps1" -OutFile deploy.ps1
Invoke-WebRequest "$Base/scripts/vm-dashboard-install.env.example" -OutFile vm-dashboard-install.env.example
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimale `vm-dashboard-install.env`:

```env
GRAFANA_URL=http://<deine-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<dein_service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
GRAFANA_DS_VM_EVCC_AUDIT_UID=   # optional: separate EVCC-SmartMeterCtrl/§14a-Audit-Datasource
# optional: GRAFANA_THEME=dark oder GRAFANA_THEME=light
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
PURGE=false
PURGE_ONLY=false
```

Grafana 13.0.1 oder neuer ist erforderlich. Die Deployer installieren immer die Tab-Navigation-Dashboards; der alte Row-Modus und Dashboard-Set-Auswahl sind entfernt. Der Default ist `DASHBOARD_LANGUAGE=de` mit `DASHBOARD_VARIANT=gen`; `DASHBOARD_VARIANT=orig` bleibt bewusst Englisch.

## Quelle und Einstellungen

`DASHBOARD_SOURCE_MODE` entscheidet, woher Dashboard-JSON-Dateien importiert werden:

```env
DASHBOARD_SOURCE_MODE=github
# oder: DASHBOARD_SOURCE_MODE=rawurl
# oder: DASHBOARD_SOURCE_MODE=localdir
```

Fuer einen selbst gehosteten Raw-Endpunkt nutze das Repository-Root-Raw-URL-Muster:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Wichtige Dashboard-Variablen koennen ebenfalls in `vm-dashboard-install.env` gesetzt werden:

```env
DASHBOARD_INSTALLED_WATT_PEAK=22
DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM=6
DASHBOARD_FUEL_COST_PER_L=1.75
DASHBOARD_STORAGE_CAPACITY_WH=9500
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_FILTER_CONSUMER_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_CONSUMER_LEGACY_EXT_REGEX="^(Spuelmaschine|Waschmaschine)$"
DASHBOARD_FILTER_EXT_BLOCKLIST=^none$
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_EVCC_URL=http://home:7070/#/
# Optionaler externer Portal-Button. Ohne DASHBOARD_PORTAL_URL wird kein Portal-Button angezeigt.
# DASHBOARD_PORTAL_TITLE=Portal
# DASHBOARD_PORTAL_URL=https://example.invalid/portal
```

Summen- oder Elternzaehler lassen sich mit der Blocklist ihrer Consumer-, EXT- oder AUX-Rolle aus Anzeige und `Sonstiges` entfernen. Verwende je Messhierarchie nur eine Ebene; ein konkretes Beispiel steht unter [Summen- und Elternzaehler aus der Hausaufteilung entfernen](./migration-troubleshooting.md#summen--und-elternzaehler-aus-der-hausaufteilung-entfernen).

Nach einem Rollenwechsel von EXT zu Consumer muss `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` exakt dieselben frueheren Endverbraucher enthalten wie `consumer_legacy_ext_regex` in der Rollup-Konfiguration. Dadurch zeigt `Today - Details` auch historische Rohdaten vor dem Wechsel; aktuelle Consumer-Samples haben bei Ueberlappung Vorrang. Der Standard `^$` deaktiviert den Fallback. Verteiler- und Summenzaehler duerfen nie enthalten sein.

Die vollstaendige Liste steht in [vm-dashboard-install.md](./vm-dashboard-install.md) und in `vm-dashboard-install.env.example`. Jeder Env-Key darf nur einmal aktiv gesetzt sein; doppelte Keys werden abgelehnt.

## Ausfuehren

Linux:

```bash
./deploy-python.sh
```

Windows:

```powershell
.\deploy.ps1
```

Der Deployer zeigt eine Preflight-Zusammenfassung und fragt vor dem Import nach Bestaetigung.

## Pruefen

Nach dem Deployment:

- Der Grafana-Ordner `EVCC` existiert.
- `Today` zeigt Rohdaten.
- `Month`, `Year` und `All-time` zeigen `evcc_*` Rollup-Daten.
- Kein Panel zeigt Datasource- oder Query-Fehler.

## Optionaler Bash-Deployer

`deploy-bash.sh` bleibt fuer Linux-Systeme unterstuetzt, die Bash und `jq` bevorzugen:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-bash.sh "$BASE/scripts/deploy-bash.sh"
chmod +x deploy-bash.sh
sudo apt install -y jq
./deploy-bash.sh
```

Fuer Einsteiger ist `deploy-python.sh` der bevorzugte Pfad, weil Migration und Rollup ohnehin Python nutzen.
