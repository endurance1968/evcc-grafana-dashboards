# VM Dashboard Installer

Englische Version: [vm-dashboard-install_EN.md](./vm-dashboard-install_EN.md).

Diese Datei beschreibt die Optionen der Dashboard-Deployer fuer Grafana. Fuer den normalen Ablauf nutze zuerst [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).

## Unterstuetzte Deployer

- Windows PowerShell: `deploy.ps1`
- Portable Linux/POSIX mit Python: `deploy-python.sh`
- Bash + `jq`: `deploy-bash.sh`

Alle Deployer verwenden dieselbe Konfigurationsdatei `vm-dashboard-install.env`.

## Mindestanforderungen

- Grafana 13.0.1 oder neuer
- VictoriaMetrics Datasource Plugin
- Grafana Service-Account-Token oder Basic Auth
- Datasource UID fuer VictoriaMetrics, standardmaessig `vm-evcc`

Dashboard-Set-Auswahl wird nicht mehr unterstuetzt. Es wird immer die feste Tab-Navigation-Dateiliste aus `dashboards/deploy-manifest.json` verwendet.

## Sprache und Variante

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Werte:

- `DASHBOARD_LANGUAGE`: `en`, `de`, `fr`, `es`, `it`, `nl`, `hi`, `zh`
- `DASHBOARD_VARIANT`: `gen` fuer generierte lokalisierte Dashboards, `orig` fuer die englischen Original-Quelldashboards. `orig` bleibt immer Englisch und verwendet unabhaengig von `DASHBOARD_LANGUAGE` den Pfad `dashboards/original/en`.

## Source Selection

`DASHBOARD_SOURCE_MODE` entscheidet, woher Dashboard-JSON-Dateien geladen werden. Der Deployer validiert nur die Variablen des gewaehlten Modus und ignoriert Quellenvariablen der anderen Modi. Jeder Env-Key darf nur einmal aktiv gesetzt sein; doppelte Keys werden abgelehnt.

GitHub-Quelle:

```env
DASHBOARD_SOURCE_MODE=github
GITHUB_REPO=endurance1968/evcc-grafana-dashboards
GITHUB_REF=main
```

Raw-URL-Quelle. Der Wert muss auf den Repository-Root-Raw-Pfad zeigen, typischerweise `<server:port>/<reponame>/raw/branch/main`; der Deployer haengt Pfade wie `dashboards/deploy-manifest.json`, `dashboards/translation/de/...` oder bei `DASHBOARD_VARIANT=orig` `dashboards/original/en/...` an:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Lokales Dashboard-Verzeichnis. Das Verzeichnis muss die sechs deploybaren Dashboard-JSON-Dateien der gewaehlten Sprache/Variante enthalten; in diesem Modus wird kein Repository-Manifest gelesen:

```env
DASHBOARD_SOURCE_MODE=localdir
DASHBOARD_LOCAL_DIR=/path/to/evcc-grafana-dashboards/dashboards/translation/de
```

## Ordner und Datasource

```env
GRAFANA_FOLDER_UID=evcc
GRAFANA_FOLDER_TITLE=EVCC
GRAFANA_DS_VM_EVCC_UID=vm-evcc
```

Wenn deine Grafana-Datasource nicht `vm-evcc` heisst, setze `GRAFANA_DS_VM_EVCC_UID` vor dem Deployment.

## Update-Verhalten

```env
PURGE=false
PURGE_ONLY=false
```

`PURGE=false` ueberschreibt bekannte Dashboards per UID und aktualisiert referenzierte Library Panels. `PURGE_ONLY=false` ist der normale Importmodus.

```env
PURGE=true
```

`PURGE=true` loescht bekannte EVCC-Dashboards zuerst und erstellt Dashboards und eingebettete Library Panels danach neu. Nutze das nur fuer einen bewussten Neuaufbau.

```env
PURGE_ONLY=true
```

`PURGE_ONLY=true` loescht bekannte EVCC-Dashboards und referenzierte EVCC Library Panels und beendet danach ohne Import. Das ist die reine Aufraeumfunktion.

## Optionale Dashboard-Variablen

Diese Werte setzen versteckte Dashboard-Variablen und Header-Buttons, ohne Dashboard-JSON-Dateien manuell zu bearbeiten:

```env
DASHBOARD_FILTER_PEAK_POWER_LIMIT=30000
DASHBOARD_ENERGY_SAMPLE_INTERVAL=30s
DASHBOARD_TARIFF_PRICE_INTERVAL=15m
DASHBOARD_INSTALLED_WATT_PEAK=20
DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM=6
DASHBOARD_FUEL_COST_PER_L=1.75
DASHBOARD_PV_PURCHASE_PRICE=24884
DASHBOARD_BATTERY_PURCHASE_PRICE=5500
DASHBOARD_RUNNING_COSTS_YEARLY=100
DASHBOARD_STORAGE_CAPACITY_WH=9500
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_EVCC_URL=http://home:7070/#/
DASHBOARD_PORTAL_TITLE=Solarman
DASHBOARD_PORTAL_URL=https://globalhome.solarmanpv.com/plant/infos/data
```

Regex-Werte mit `|`, Klammern, Leerzeichen oder Nicht-ASCII-Zeichen sollten gequotet werden, damit der Bash-Deployer die Env-Datei sauber lesen kann.

Rueckwaertskompatible Alias-Namen werden weiterhin akzeptiert:

- `DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL`
- `DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL`
- `DASHBOARD_ICE_CONSUMPTION_L_PER_100KM` fuer `DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM`
- `DASHBOARD_FUEL_PRICE_PER_L` fuer `DASHBOARD_FUEL_COST_PER_L`
- `DASHBOARD_BATTERY_CAPACITY_WH` fuer `DASHBOARD_STORAGE_CAPACITY_WH`

Jedes deployte Dashboard enthaelt eine sichtbare `Build`-Variable im Header. Der Tooltip zeigt Deployment-Zeitpunkt, Sprache/Variante und Quelle.

## Laufzeitargumente

PowerShell:

```powershell
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purge false
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purgeonly true
```

Portable Shell mit Python:

```bash
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge false
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Bash + `jq`:

```bash
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge false
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Laufzeitargumente ueberschreiben die Konfigurationsdatei fuer diesen Lauf.

## Anpassungen

Der Deployer ist bewusst importorientiert. Empfohlene Anpassungswege:

- Dashboard-Variablen in Grafana aendern und Dashboard speichern
- Deploy-Time-Overrides in `vm-dashboard-install.env` setzen
- aus lokalem Dashboard-Verzeichnis mit `DASHBOARD_SOURCE_MODE=localdir` deployen

Der Deployer schreibt keine Farben oder beliebige Panel-Optionen um.