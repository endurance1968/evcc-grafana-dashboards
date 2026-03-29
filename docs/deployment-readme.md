# Deployment README

Diese Anleitung ist fuer den ersten Dashboard-Deploy gedacht.

## Voraussetzungen

Benoetigt werden:

- eine laufende Grafana-Instanz
- eine funktionierende VictoriaMetrics-Datasource in Grafana
- ein Grafana Service-Account-Token
- Internetzugriff auf GitHub

Unter Linux oder auf dem Raspberry Pi werden je nach Deployer zusaetzlich benoetigt:

- fuer `deploy-python.sh`: `curl` und `python3`
- fuer `deploy-bash.sh`: `bash`, `curl` und `jq`

Falls etwas fehlt:

```bash
sudo apt update
sudo apt install curl python3 jq
```

## 1. Deployer und Beispiel-Config holen

### Linux / Raspberry Pi mit Python-Deployer

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

### Linux / Raspberry Pi mit Bash-Only-Deployer

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-bash.sh
```

### Windows / PowerShell

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

## 2. Datasource in Grafana pruefen

In Grafana pruefen:

1. `Connections` oder `Administration` oeffnen
2. `Data sources` oeffnen
3. pruefen, dass die VictoriaMetrics-Datasource existiert
4. ihre UID notieren

Wenn du die Standard-UID verwendest, ist das meist einfach:

```text
vm-evcc
```

## 3. Service-Account-Token in Grafana erzeugen

In Grafana:

1. `Administration` oeffnen
2. `Users and access` oeffnen
3. `Service accounts` oeffnen
4. `Add service account` klicken
5. z. B. `evcc-dashboard-installer` anlegen
6. den Service Account oeffnen
7. `Add service account token` klicken
8. einen Namen vergeben, z. B. `installer`
9. `Generate token` klicken
10. den Token sofort kopieren

Fuer einfache lokale Installationen reicht in der Regel:

- Rolle `Admin` in der Organisation

## 4. Schnellstart

Fuer den ersten Lauf reichen normalerweise nur URL und Token. Mit `purge` steuerst du, ob vorhandene EVCC-Dashboards vor dem Import geloescht werden sollen.

### Linux / Raspberry Pi mit Python-Deployer

```bash
./deploy-python.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
```

### Linux / Raspberry Pi mit Bash-Only-Deployer

```bash
./deploy-bash.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
```

### Windows

```powershell
./deploy.ps1 -url http://<deine-grafana-ip>:3000 -token <dein_token> -purge false
```

## 5. Optional: Config-Datei

Wenn du nicht jedes Mal URL und Token angeben willst, kopiere:

- `vm-dashboard-install.env.example`

nach:

- `vm-dashboard-install.env`

Minimalinhalt:

```env
GRAFANA_URL=http://<deine-grafana-ip>:3000
GRAFANA_API_TOKEN=<dein_token>
```

Wenn du alte EVCC-Dashboards und Library Panels vor dem Import bewusst entfernen willst, setze in der Config oder beim Aufruf `purge=true`. In der Config sieht das so aus:

```env
PURGE=true
```

Danach reicht:

### Linux / Raspberry Pi mit Python-Deployer

```bash
./deploy-python.sh
```

### Linux / Raspberry Pi mit Bash-Only-Deployer

```bash
./deploy-bash.sh
```

### Windows

```powershell
.\deploy.ps1
```

## 6. Ergebnis pruefen

Danach sollten im Grafana-Ordner `EVCC` diese Dashboards liegen:

- `VM: EVCC: Today`
- `VM: EVCC: Today - Details`
- `VM: EVCC: Today - Mobile`
- `VM: EVCC: Monat`
- `VM: EVCC: Year`
- `VM: EVCC: All-time`

## Typische Fehler

### `Missing GRAFANA_API_TOKEN`

Dann fehlt der Token:

- in `vm-dashboard-install.env`
- oder in den Uebergabeparametern
- oder in der Umgebung

### 403 / Permission denied

Dann hat der Token nicht genug Rechte.

Pruefen:

- Service Account existiert noch
- Token ist gueltig
- Rechte reichen fuer Dashboards und Library Panels

## Mehr Details

Die technische Doku liegt hier:

- `docs/vm-dashboard-install.md`
