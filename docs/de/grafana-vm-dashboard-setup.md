# Grafana mit VictoriaMetrics-Dashboards einrichten

Englische Version: [grafana-vm-dashboard-setup.md](../en/grafana-vm-dashboard-setup.md).

Pruefe vor den Befehlen die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Dies ist die kanonische Endnutzer-Anleitung fuer das Dashboard-Deployment. Sie beschreibt:

- Anlegen der VictoriaMetrics-Datasource in Grafana
- Erstellen eines Grafana-Service-Account-Tokens
- Deployment der EVCC-Dashboards
- spaetere Dashboard-Updates

Wenn du vorhandene InfluxDB-Historie uebernimmst, schliesse zuerst [influx-to-vm-migration.md](./influx-to-vm-migration.md) ab. Wenn aktuelle EVCC-Rohdaten noch nicht in VictoriaMetrics ankommen, richte danach [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md) ein.

## Zielzustand

Grafana sollte danach haben:

- eine VictoriaMetrics-Datasource mit UID `vm-evcc`
- einen Ordner `EVCC`
- die EVCC-Dashboards in diesem Ordner

`Today*`-Dashboards lesen VictoriaMetrics-Rohdaten. `Month`, `Year` und `All-time` benoetigen die erzeugten `evcc_*`-Rollups.

## Voraussetzungen

Erforderlich:

- laufende Grafana-Instanz
- laufende VictoriaMetrics-Instanz
- aktuelle EVCC-Rohdaten in VictoriaMetrics
- Grafana-Service-Account-Token
- Zugriff auf den gewaehlten Dashboard- und Skript-Raw-Endpunkt, zum Beispiel GitHub oder ein lokales Forgejo

Empfohlen:

- Grafana 13.0.1 oder neuer. Die Deploy-Skripte installieren immer die Tab-Navigation-Dashboards; Dashboard-Set-Auswahl wird nicht mehr unterstuetzt.
- Linux-Deployments verwenden `deploy-python.sh` als primaeren Pfad
- Windows-Deployments verwenden `deploy.ps1`

Linux-Paketminimum:

```bash
sudo apt update
sudo apt install -y curl python3
```

`deploy-bash.sh` bleibt fuer Systeme verfuegbar, die Bash + `jq` bevorzugen, ist aber nicht der primaere Einsteigerpfad.

## 1. VictoriaMetrics-Datasource anlegen

In Grafana:

1. `Connections` oder `Administration` oeffnen.
2. `Data sources` oeffnen.
3. VictoriaMetrics-Datasource hinzufuegen.
4. URL auf `http://<dein-vm-host>:8428` setzen.
5. Access auf `Server` oder `Proxy` setzen.
6. UID auf `vm-evcc` setzen.
7. `Save & test` ausfuehren.

Wenn das VictoriaMetrics-Datasource-Plugin nicht verfuegbar ist, installiere es zuerst und starte Grafana neu.

Bei einer Debian-Paketinstallation:

```bash
sudo grafana cli \
  --homepath=/usr/share/grafana \
  --pluginsDir /var/lib/grafana/plugins \
  plugins install victoriametrics-metrics-datasource
sudo systemctl restart grafana-server
```

Docker-Hinweis: Wenn Grafana und VictoriaMetrics als getrennte Docker-Container laufen, zeigt `localhost` innerhalb von Grafana auf den Grafana-Container, nicht auf VictoriaMetrics. Unter Docker Desktop nutze eine Datasource-URL wie `http://host.docker.internal:8428`. In einem benutzerdefinierten Docker-Netzwerk nutze den VictoriaMetrics-Containernamen, zum Beispiel `http://victoriametrics:8428`.

## 2. Service-Account-Token erstellen

In Grafana:

1. `Administration` oeffnen.
2. `Users and access` oeffnen.
3. `Service accounts` oeffnen.
4. `evcc-dashboard-deployer` erstellen.
5. Service-Account-Token hinzufuegen.
6. Token sofort kopieren.

Fuer ein einfaches lokales Deployment reicht in der aktuellen Organisation normalerweise `Admin`. Grafana 13 unterstuetzt Service-Account-Tokens fuer diesen Deployment-Pfad.

## 3. Deployer herunterladen

Die Beispiele nutzen GitHub als `BASE`. Fuer ein lokales Forgejo-Repository setze `BASE` stattdessen auf den Raw-Root, typischerweise `http://<server:port>/<owner>/<repo>/raw/branch/main`.

Linux / Raspberry Pi:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-python.sh "$BASE/scripts/deploy-python.sh"
curl -fsSLo vm-dashboard-install.env.example "$BASE/scripts/vm-dashboard-install.env.example"
chmod +x deploy-python.sh
```

Windows / PowerShell:

```powershell
$Base = "https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# $Base = "http://<server:port>/<owner>/<repo>/raw/branch/main"

Invoke-WebRequest "$Base/scripts/deploy.ps1" -OutFile deploy.ps1
Invoke-WebRequest "$Base/scripts/vm-dashboard-install.env.example" -OutFile vm-dashboard-install.env.example
```

Optionaler Bash-Deployer:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Forgejo-Beispiel:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

curl -fsSLo deploy-bash.sh "$BASE/scripts/deploy-bash.sh"
chmod +x deploy-bash.sh
sudo apt install -y jq
```

## 4. Konfigurationsdatei erstellen

Linux:

```bash
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Windows:

```powershell
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimale Konfiguration:

```env
GRAFANA_URL=http://<deine-grafana-ip>:3000
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<dein_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
# optional, nur bei separater Audit-Datasource fuer EVCC-SmartMeterCtrl/§14a:
GRAFANA_DS_VM_EVCC_AUDIT_UID=
# optional: GRAFANA_THEME=dark oder GRAFANA_THEME=light
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
PURGE=false
PURGE_ONLY=false
```

Persoenliche Dashboard-Variablen koennen in derselben Env-Datei gepflegt werden. Das externe Portal ist optional; ohne `DASHBOARD_PORTAL_URL` wird kein Portal-Button angezeigt. Beispiel:

```env
DASHBOARD_INSTALLED_WATT_PEAK=22
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_FILTER_CONSUMER_BLOCKLIST=^none$
DASHBOARD_CONSUMER_LEGACY_EXT_REGEX="^(Spuelmaschine|Waschmaschine)$"
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
DASHBOARD_EVCC_URL=http://home:7070/#/
# Optionaler externer Portal-Button, z. B. fuer ein Wechselrichter- oder Energieportal.
# DASHBOARD_PORTAL_TITLE=Portal
# DASHBOARD_PORTAL_URL=https://example.invalid/portal
```

Wenn Summen- oder Elternzaehler und ihre Unterzaehler gleichzeitig unter Consumer, EXT oder AUX vorhanden sind, muessen sie mit der jeweiligen Blocklist auf eine nicht ueberlappende Ebene reduziert werden. Die Filter wirken auf die sichtbaren Reihen und auf `Sonstiges`; ein konkretes Verteiler-, USV- und Waschraum-Beispiel steht unter [Summen- und Elternzaehler aus der Hausaufteilung entfernen](./migration-troubleshooting.md#summen--und-elternzaehler-aus-der-hausaufteilung-entfernen).

Bei einem EXT-zu-Consumer-Rollenwechsel muss `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` dieselben frueheren Endverbraucher wie `consumer_legacy_ext_regex` im Rollup enthalten. Damit bleiben historische Haus-Panels in `Today - Details` gefuellt. Consumer hat bei Ueberlappung Vorrang; Verteiler- und Summenzaehler duerfen nicht gemappt werden.

Wenn die Dashboard-Dateien von einem selbst gehosteten Raw-Endpunkt statt von GitHub kommen sollen, wechsle den Source Mode auf `rawurl`:

```env
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_RAW_BASE_URL=http://<server:port>/<reponame>/raw/branch/main
```

Der alte row-basierte Deploy-Pfad wurde entfernt. Nutze Grafana 13.0.1 oder neuer; die Deploy-Skripte installieren immer die Tab-Navigation-Dashboards. Standardmaessig werden generierte deutsche Dashboards importiert. `DASHBOARD_VARIANT=orig` ist nur fuer die originalen englischen Quelldashboards gedacht und bleibt unabhaengig von `DASHBOARD_LANGUAGE` Englisch.

## 5. Deployment ausfuehren

Linux:

```bash
./deploy-python.sh
```

Windows:

```powershell
.\deploy.ps1
```

Der Deployer zeigt eine Preflight-Zusammenfassung und fragt vor Schreibzugriffen nach Bestaetigung.

Direkte Einmal-Befehle werden ebenfalls unterstuetzt:

```bash
./deploy-python.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
```

```powershell
.\deploy.ps1 -url http://<deine-grafana-ip>:3000 -token <dein_token> -purge false
```

## Was der Deployer macht

- prueft Grafana-Zugriff
- loest die feste Dashboard-Dateiliste aus `dashboards/deploy-manifest.json` auf
- zeigt, welche Dashboards importiert werden
- importiert Dashboards mit Inline-Panels; es werden keine Grafana-Library-Panels erstellt
- importiert Dashboards in den Ordner `EVCC`

Mit `PURGE=false` werden vorhandene Dashboards per UID ueberschrieben. Die Dashboards nutzen Inline-Panels; Library Panels werden nicht erstellt oder aktualisiert.
Mit `PURGE_ONLY=false` bleibt der Deployer im normalen Importmodus.

Mit `PURGE=true` werden bekannte EVCC-Dashboards zuerst geloescht und danach neu erstellt. Nutze das nur, wenn du bewusst einen vollstaendigen Neuaufbau willst.
Mit `PURGE_ONLY=true` werden bekannte EVCC-Dashboards geloescht; danach endet der Deployer ohne Import.

## 6. Ergebnis pruefen

In Grafana:

- der Ordner `EVCC` existiert
- `Today` zeigt aktuelle Rohdaten
- `Today - Details` oeffnet ohne Datasource-Fehler
- `Month`, `Year` und `All-time` zeigen Rollup-Werte
- die Dashboard-Header-Build-Variable zeigt ausgewaehlte Sprache, Variante, Source Ref und Deployment-Zeit

Wenn `Today` funktioniert, Langzeit-Dashboards aber leer sind, fehlen Rollups. Gehe zurueck zu [influx-to-vm-migration.md](./influx-to-vm-migration.md).

## Spaeter aktualisieren

Normales Update:

```bash
./deploy-python.sh --purge false
```

Windows:

```powershell
.\deploy.ps1 -purge false
```

Vollstaendiger Neuaufbau:

```bash
./deploy-python.sh --purge true
```

Windows:

```powershell
.\deploy.ps1 -purge true
```

## Haeufige Fehler

### `Missing GRAFANA_API_TOKEN`

Setze `GRAFANA_API_TOKEN` in `vm-dashboard-install.env` oder uebergebe `--token` / `-token`.

### 403 / Permission denied

Dem Service Account fehlen Berechtigungen fuer Dashboards oder Ordner.

### 401 / `Invalid API key`

Erstelle ein frisches Grafana-Service-Account-Token und setze:

```env
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<neues_service_account_token>
```

### Dashboards importiert, aber leer

Pruefe:

- Datasource-URL zeigt auf VictoriaMetrics
- Datasource-UID passt zu `GRAFANA_DS_VM_EVCC_UID`
- Rohdaten sind fuer `Today*` vorhanden
- `evcc_*`-Rollups existieren fuer Langzeit-Dashboards

## Referenzen

- Kurzreferenz fuer Deployment: [deployment-readme.md](./deployment-readme.md)
- Vollstaendige Deployer-Optionsreferenz: [vm-dashboard-install.md](./vm-dashboard-install.md)
- Migrations-Checkliste: [migration-checklist.md](./migration-checklist.md)
