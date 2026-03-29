# Installation README

Diese Anleitung ist für den ersten Deploy gedacht.

## Voraussetzungen

Benötigt werden:

- eine laufende Grafana-Instanz
- eine funktionierende VictoriaMetrics-Datasource in Grafana
- ein Grafana Service-Account-Token
- Internetzugriff auf GitHub

Unter Linux oder auf dem Raspberry Pi werden zusätzlich benötigt:

- `curl`
- `python3`

Falls etwas fehlt:

```bash
sudo apt update
sudo apt install curl python3
```

## 1. Installer und Beispiel-Config holen

### Linux / Raspberry Pi

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

### Windows / PowerShell

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

## 2. Datasource in Grafana prüfen

In Grafana prüfen:

1. `Connections` oder `Administration` öffnen
2. `Data sources` öffnen
3. prüfen, dass die VictoriaMetrics-Datasource existiert
4. ihre UID notieren

Wenn du die Standard-UID verwendest, ist das meist einfach:

```text
vm-evcc
```

## 3. Service-Account-Token in Grafana erzeugen

In Grafana:

1. `Administration` öffnen
2. `Users and access` öffnen
3. `Service accounts` öffnen
4. `Add service account` klicken
5. z. B. `evcc-dashboard-installer` anlegen
6. den Service Account öffnen
7. `Add service account token` klicken
8. einen Namen vergeben, z. B. `installer`
9. `Generate token` klicken
10. den Token sofort kopieren

Für einfache lokale Installationen reicht in der Regel:

- Rolle `Admin` in der Organisation

## 4. Schnellstart

Für den ersten Lauf reichen normalerweise nur URL und Token. Mit `purge` steuerst du, ob vorhandene EVCC-Dashboards vor dem Import gelöscht werden sollen.

### Linux / Raspberry Pi

```bash
./deploy-python.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
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

### Linux / Raspberry Pi

```bash
./deploy-python.sh
```

### Windows

```powershell
.\deploy.ps1
```

## 6. Ergebnis prüfen

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
- oder in den Übergabeparametern
- oder in der Umgebung

### 403 / Permission denied

Dann hat der Token nicht genug Rechte.

Prüfen:

- Service Account existiert noch
- Token ist gültig
- Rechte reichen für Dashboards und Library Panels

## Mehr Details

Die technische Doku liegt hier:

- `docs/vm-dashboard-install.md`




