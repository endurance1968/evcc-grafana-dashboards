# Grafana mit VictoriaMetrics und EVCC-Dashboards einrichten

Diese Anleitung beschreibt den Enduser-Weg für:

- Grafana mit einer laufenden VictoriaMetrics-Instanz verbinden
- den ersten initialen Deploy der EVCC-Dashboards
- ein späteres Dashboard-Update

Diese Anleitung setzt voraus, dass VictoriaMetrics bereits läuft.

Falls noch nicht:

- Installation von VictoriaMetrics auf Debian 13:
  - `victoriametrics-install-debian-13.md`
- Migration der EVCC-Rohdaten und Rollups:
  - `influx-to-vm-migration.md`

## Zielbild

Am Ende hast du in Grafana:

- eine VictoriaMetrics-Datasource
- einen Ordner `EVCC`
- diese Dashboards:
  - `VM: EVCC: Today`
  - `VM: EVCC: Today - Details`
  - `VM: EVCC: Today - Mobile`
  - `VM: EVCC: Monat`
  - `VM: EVCC: Year`
  - `VM: EVCC: All-time`

Wichtig:

- `Today*` liest Rohdaten aus VictoriaMetrics
- `Monat`, `Year`, `All-time` lesen zusätzlich die erzeugten `evcc_*`-Rollups

## Voraussetzungen

Du brauchst:

- eine laufende Grafana-Instanz
- eine laufende VictoriaMetrics-Instanz
- einen Grafana Service-Account-Token
- Internetzugriff auf GitHub

Unter Linux zusätzlich:

- für `deploy-python.sh`: `curl` und `python3`
- für `deploy-bash.sh`: `bash`, `curl` und `jq`

Minimal unter Debian:

```bash
sudo apt update
sudo apt install -y curl python3 jq
```

## Schritt 1: VictoriaMetrics-Datasource in Grafana anlegen

In Grafana:

1. `Connections` oder `Administration` öffnen
2. `Data sources` öffnen
3. `Add data source` wählen
4. `VictoriaMetrics` auswählen

Falls das Plugin nicht angeboten wird:

- zuerst das VictoriaMetrics-Datasource-Plugin in Grafana installieren
- danach Grafana neu starten

Typische Datasource-Konfiguration:

- Name:
  - `VM-EVCC`
- URL:
  - `http://<dein-vm-host>:8428`
- Access:
  - `Server` oder `Proxy`

Empfohlene UID:

```text
vm-evcc
```

Warum diese UID wichtig ist:

- die Deploy-Skripte nutzen standardmäßig genau diese Datasource-UID
- wenn du eine andere UID nimmst, musst du sie im Deploy angeben

Danach:

1. `Save & test`
2. prüfen, dass die Datasource erfolgreich antwortet

## Schritt 2: Service-Account-Token in Grafana erzeugen

In Grafana:

1. `Administration` öffnen
2. `Users and access` öffnen
3. `Service accounts` öffnen
4. `Add service account` klicken
5. z. B. `evcc-dashboard-deployer` anlegen
6. den Service Account öffnen
7. `Add service account token` klicken
8. Namen vergeben, z. B. `default`
9. `Generate token` klicken
10. Token sofort kopieren

Für normale lokale Deployments reicht in der Regel:

- Rolle `Admin`

## Schritt 3: Deployer herunterladen

Für Windows / PowerShell:

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy.ps1 -OutFile deploy.ps1
Invoke-WebRequest https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example -OutFile vm-dashboard-install.env.example
```

Für Linux / Raspberry Pi mit Python-Deployer:

```bash
curl -fsSLo deploy-python.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-python.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-python.sh
```

Für Linux / Raspberry Pi mit Bash-Deployer:

```bash
curl -fsSLo deploy-bash.sh https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/deploy-bash.sh
curl -fsSLo vm-dashboard-install.env.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/vm-dashboard-install.env.example
chmod +x deploy-bash.sh
```

## Schritt 4: Config-Datei anlegen

Beispiel-Config kopieren:

Windows:

```powershell
Copy-Item vm-dashboard-install.env.example vm-dashboard-install.env
```

Linux:

```bash
cp vm-dashboard-install.env.example vm-dashboard-install.env
```

Minimal anpassen:

```env
GRAFANA_URL=http://<deine-grafana-ip>:3000
GRAFANA_API_TOKEN=<dein_token>
GRAFANA_DS_VM_EVCC_UID=vm-evcc
PURGE=false
```

Standardmäßig werden außerdem genutzt:

- Folder UID: `evcc`
- Folder Title: `EVCC`
- Source: `github`
- Repo: `endurance1968/evcc-grafana-dashboards`
- Branch: `main`
- Sprache: `en`
- Variant: `gen`

Wichtig:

- `PURGE=false` ist absichtlich der sichere Default
- beim ersten Lauf ist das meist die richtige Wahl

## Schritt 5: Erstes Initial-Deployment

### Windows

```powershell
.\deploy.ps1
```

Oder direkt mit Parametern:

```powershell
.\deploy.ps1 -url http://<deine-grafana-ip>:3000 -token <dein_token> -purge false
```

### Linux mit Python-Deployer

```bash
./deploy-python.sh
```

Oder direkt mit Parametern:

```bash
./deploy-python.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
```

### Linux mit Bash-Deployer

```bash
./deploy-bash.sh
```

Oder direkt mit Parametern:

```bash
./deploy-bash.sh --url http://<deine-grafana-ip>:3000 --token <dein_token> --purge false
```

## Was beim ersten Deploy passiert

Der Deployer:

- prüft den Grafana-Zugriff
- zeigt an, welche Dashboards importiert werden
- zeigt an, welche Library Panels eingebettet sind
- fragt vor dem eigentlichen Schreiben nach Bestätigung
- importiert danach den kompletten EVCC-Dashboard-Satz in den Ordner `EVCC`

Bei `purge=false`:

- bestehende EVCC-Dashboards und Libraries werden nicht vorher gelöscht
- das ist der sichere Startmodus

Bei `purge=true`:

- die bekannten EVCC-Dashboards und ihre Library Panels werden vor dem Import gelöscht
- danach werden sie frisch neu angelegt

## Schritt 6: Ergebnis prüfen

Danach sollten im Grafana-Ordner `EVCC` diese Dashboards liegen:

- `VM: EVCC: Today`
- `VM: EVCC: Today - Details`
- `VM: EVCC: Today - Mobile`
- `VM: EVCC: Monat`
- `VM: EVCC: Year`
- `VM: EVCC: All-time`

Zusätzlich prüfen:

- `Today` zeigt aktuelle Rohdaten
- `Monat`, `Year`, `All-time` zeigen Rollup-Werte
- Forecast im `Today`-Hauptpanel ist sichtbar

## Beispiel: späteres Dashboard-Update

Der normale Update-Fall ist einfach:

1. aktuelle Deploy-Skripte erneut von GitHub laden oder die vorhandenen weiterverwenden
2. denselben Deploy nochmal ausführen

### Schonender Update-Lauf

Wenn du nur auf einen neueren Dashboard-Stand aktualisieren willst und nichts bewusst löschen möchtest:

Windows:

```powershell
.\deploy.ps1 -purge false
```

Linux:

```bash
./deploy-python.sh --purge false
```

Das ist der Standardfall für normale Updates.

### Vollständiger Neuaufbau

Wenn du den EVCC-Ordner bewusst komplett frisch aufbauen willst:

Windows:

```powershell
.\deploy.ps1 -purge true
```

Linux:

```bash
./deploy-python.sh --purge true
```

Das ist sinnvoll, wenn:

- Library Panels sichtbar kaputt sind
- ein Importzustand inkonsistent wirkt
- du bewusst ganz sauber neu aufsetzen willst

## Sprache ändern

Wenn du statt Englisch z. B. Deutsch willst, setze in `vm-dashboard-install.env`:

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Danach denselben Deploy nochmal ausführen.

Typische Werte:

- `en` + `gen`
- `de` + `gen`
- `fr` + `gen`
- `en` + `orig`

`orig` bedeutet:

- Original-Dashboards

`gen` bedeutet:

- generierter Sprachsatz

## Wenn du eine andere Datasource-UID nutzt

Dann in `vm-dashboard-install.env` anpassen:

```env
GRAFANA_DS_VM_EVCC_UID=<deine_uid>
```

Ohne diese Anpassung erwarten die Deploy-Skripte standardmäßig:

```text
vm-evcc
```

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
- Rechte reichen für Dashboards, Ordner und Library Panels

### Dashboards importiert, aber leer

Dann meist zuerst prüfen:

- Datasource zeigt wirklich auf VictoriaMetrics
- URL ist korrekt
- Rohdaten und Rollups existieren bereits in VM

### `Today` ok, aber `Monat/Year/All-time` leer

Dann fehlen meistens noch die Rollups.

Dafür siehe:

- `influx-to-vm-migration.md`

## Verweise

Für mehr Details nicht doppelt lesen, sondern direkt hier weiter:

- allgemeiner Deployer-Einstieg:
  - `deployment-readme.md`
- technische Deploy-Details:
  - `vm-dashboard-install.md`
- VictoriaMetrics auf Debian 13:
  - `victoriametrics-install-debian-13.md`
- InfluxDB -> VictoriaMetrics Migration und Rollups:
  - `influx-to-vm-migration.md`

