# VM Dashboard Installer Referenz

Englische Version: [vm-dashboard-install_EN.md](./vm-dashboard-install_EN.md).

Fuer den ersten Durchlauf starte mit [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md). Fuer eine kurze Befehlsreferenz nutze [deployment-readme.md](./deployment-readme.md).

Dieses Dokument ist die Optionsreferenz fuer den Deployer.

## Ziele des Deployers

- kein Node.js fuer Endnutzer erforderlich
- Dashboards und eingebettete Grafana-Library-Panels importieren
- Windows PowerShell, portable POSIX-Shell mit Python und Bash + `jq` unterstuetzen
- `PURGE=false` und `PURGE_ONLY=false` als sicheren Default behalten

## Standardverhalten

Defaults:

- Quell-Repository: `endurance1968/evcc-grafana-dashboards`
- Ref: `main`
- Sprache: `de`
- Variante: `gen`
- Dashboards: feste Grafana-13-Tab-Navigation-Liste aus `dashboards/deploy-manifest.json`
- Ordner UID/Titel: `evcc` / `EVCC`
- Datasource UID: `vm-evcc`
- vor Import loeschen: `false`

Grafana 13.0.1 oder neuer ist erforderlich. Dashboard-Set-Auswahl wird nicht mehr unterstuetzt; die Deployer nutzen immer die feste Tab-Navigation-Dateiliste aus `dashboards/deploy-manifest.json`.

## Erforderliche Konfiguration

Kopiere `vm-dashboard-install.env.example` nach `vm-dashboard-install.env` und setze mindestens:

```env
GRAFANA_URL=http://<deine-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<service_account_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
```

`GRAFANA_API_TOKEN` ist die bevorzugte Einstellung fuer Grafana-13-Service-Account-Tokens. `GRAFANA_SERVICE_ACCOUNT_TOKEN` wird als Alias akzeptiert, wenn `GRAFANA_API_TOKEN` leer ist.

Lokaler Recovery-Fallback, wenn Basic Auth aktiviert ist:

```env
GRAFANA_AUTH_MODE=basic
GRAFANA_USER=admin
GRAFANA_PASSWORD=<admin_passwort>
```

## Dashboard-Auswahl

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Werte:

- `DASHBOARD_LANGUAGE`: `en`, `de`, `fr`, `es`, `it`, `nl`, `hi`, `zh`
- `DASHBOARD_VARIANT`: `gen` fuer generierte lokalisierte Dashboards, `orig` fuer die originalen englischen Quelldashboards. `orig` bleibt immer Englisch und nutzt unabhaengig von `DASHBOARD_LANGUAGE` `dashboards/original/en`.

Die deploybaren Dateilisten sind in `dashboards/deploy-manifest.json` definiert.

## Quellen-Auswahl

`DASHBOARD_SOURCE_MODE` bestimmt exakt, von wo Dashboard-JSON-Dateien geladen werden. Der Deployer validiert die fuer den gewaehlten Modus erforderlichen Variablen und ignoriert Quellenvariablen der anderen Modi. Definiere jeden Env-Key nur einmal; doppelte Keys werden abgelehnt, weil Shell-Env-Dateien sonst still den letzten Wert gewinnen lassen.

GitHub-Quelle:

```env
DASHBOARD_SOURCE_MODE=github
GITHUB_REPO=endurance1968/evcc-grafana-dashboards
GITHUB_REF=main
```

Raw-URL-Quelle. Der Wert muss auf den Repository-Root-Raw-Pfad zeigen, typischerweise `<server:port>/<reponame>/raw/branch/main`; der Deployer haengt Pfade wie `dashboards/deploy-manifest.json`, `dashboards/translation/de/...` oder fuer `DASHBOARD_VARIANT=orig` `dashboards/original/en/...` an:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Lokale Dashboard-Verzeichnisquelle. Das Verzeichnis muss die sechs deploybaren Dashboard-JSON-Dateien fuer die gewaehlte Sprache/Variante enthalten; der Deployer liest in diesem Modus kein Repository-Manifest:

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

Wenn deine Datasource-UID nicht `vm-evcc` ist, setze `GRAFANA_DS_VM_EVCC_UID` vor dem Deployment.

### Grafana-Theme optional setzen

Der Deployer kann die Grafana-Organisations-Preference fuer das Theme setzen:

```env
GRAFANA_THEME=dark
# oder
GRAFANA_THEME=light
```

Akzeptierte Werte sind `dark`, `light`, `bright` als Alias fuer `light` und `default`, um wieder den Grafana-Default zu verwenden. Leer lassen bedeutet: keine Grafana-Preference aendern. Persoenliche User-Preferences in Grafana koennen die Organisations-Preference weiterhin uebersteuern. Im `PURGE_ONLY`-Modus wird das Theme nicht gesetzt.

## Update-Verhalten

```env
PURGE=false
PURGE_ONLY=false
```

`PURGE=false` ueberschreibt bekannte Dashboards per UID und aktualisiert referenzierte Library Panels in place.
`PURGE_ONLY=false` haelt den Deployer im normalen Importmodus.

```env
PURGE=true
```

`PURGE=true` loescht bekannte EVCC-Dashboards zuerst und erstellt Dashboards und eingebettete Library Panels danach neu. Nutze das fuer einen bewussten vollstaendigen Neuaufbau.

```env
PURGE_ONLY=true
```

`PURGE_ONLY=true` loescht bekannte EVCC-Dashboards und referenzierte EVCC-Library-Panels und beendet danach ohne Import. Nutze das nur, wenn du die deployten Dashboards absichtlich aus Grafana entfernen willst.

## Optionale Dashboard-Variablen-Overrides

Diese Werte setzen versteckte Dashboard-Variablen und Header-Buttons, ohne Dashboard-JSON-Dateien zu bearbeiten:

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

Quote Regex-Werte mit `|`, `(`, `)`, Leerzeichen oder Nicht-ASCII-Zeichen, damit der Bash-Deployer die Env-Datei sicher sourcen kann.

Rueckwaertskompatible Aliase werden weiterhin akzeptiert:

- `DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL`
- `DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL`
- `DASHBOARD_ICE_CONSUMPTION_L_PER_100KM` fuer `DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM`
- `DASHBOARD_FUEL_PRICE_PER_L` fuer `DASHBOARD_FUEL_COST_PER_L`
- `DASHBOARD_BATTERY_CAPACITY_WH` fuer `DASHBOARD_STORAGE_CAPACITY_WH`

Jedes deployte Dashboard enthaelt eine kleine sichtbare `Build`-Variable im Header. Beim Hover zeigt sie Deployment-Zeitpunkt, Sprache/Variante und Source Ref.

## Laufzeitargumente

PowerShell:

```powershell
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purge false
# Nur loeschen, kein Re-Import:
.\deploy.ps1 -url http://<grafana-host>:3000 -token <token> -purgeonly true
```

Portable Shell mit Python:

```bash
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge false
# Nur loeschen, kein Re-Import:
./deploy-python.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Bash + `jq`:

```bash
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge false
# Nur loeschen, kein Re-Import:
./deploy-bash.sh --url http://<grafana-host>:3000 --token <token> --purge-only true
```

Laufzeitargumente ueberschreiben die Konfigurationsdatei fuer diesen Lauf.

## Nutzeranpassungen

Der Deployer ist absichtlich import-only. Empfohlene Anpassungswege:

- Dashboard-Variablen in Grafana aendern und Dashboard speichern
- Deploy-time Dashboard-Variablen-Overrides in `vm-dashboard-install.env` setzen
- aus einem lokalen Dashboard-Verzeichnis mit `DASHBOARD_SOURCE_MODE=localdir` deployen

Der Deployer schreibt absichtlich keine Farben oder beliebigen Panel-Einstellungen um.
