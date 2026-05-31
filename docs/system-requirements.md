# Systemanforderungen

Englische Version: [system-requirements_EN.md](./system-requirements_EN.md).

Diese Liste beschreibt die Mindestanforderungen fuer die EVCC-Dashboards mit VictoriaMetrics und Grafana.

## Grafana

- Grafana 13.0.1 oder neuer
- VictoriaMetrics Datasource Plugin installiert
- Service-Account-Token fuer automatisches Deployment empfohlen
- Datasource UID fuer EVCC/VictoriaMetrics standardmaessig `vm-evcc`

Warum Grafana 13? Die aktuellen Dashboards verwenden die Tab-Navigation. Der alte Row-Modus wird nicht mehr als Deploy-Variante gepflegt.

## VictoriaMetrics

- VictoriaMetrics Single Node ist ausreichend
- HTTP-Endpunkte muessen fuer Import, Query und Telegraf erreichbar sein
- Empfohlene Ports:
  - `8428` fuer native VictoriaMetrics HTTP API
  - optional gemappt, z. B. `18440`, wenn mehrere Testinstanzen parallel laufen
- Telegraf oder ein anderer Influx-Line-Protocol-Writer kann an `/influx/write` schreiben

## EVCC und Datenquelle

- EVCC mit aktivierten Metriken
- Fuer Migration: lesbarer InfluxDB-v1-Bestand
- Fuer Neuaufbau: neuer VictoriaMetrics-Stream reicht aus
- Produktionsdaten sollten bei Tests nur lesend verwendet werden

## Betriebssystem

Unterstuetzte Zielumgebungen fuer Endnutzer:

- Debian 13 / Trixie
- Docker-basierte Installationen
- Raspberry-Pi-/Kleinserver-Klassen, sofern Speicher und I/O ausreichend sind
- Windows fuer lokale Pflege und PowerShell-Deployer

## Werkzeuge

Fuer Dashboard-Deployment:

- `deploy-python.sh`: POSIX-Shell plus Python 3, empfohlen fuer Linux
- `deploy-bash.sh`: Bash, `curl`, `jq`
- `deploy.ps1`: PowerShell fuer Windows

Fuer Migration und Rollup:

- Python 3
- `curl`
- `vmctl` fuer InfluxDB-Importe
- optional `systemd` Timer oder Cron fuer taegliche Rollups

## Ressourcen

Die genaue Groesse haengt von Datenmenge und Aufbewahrungszeit ab. Fuer typische EVCC-Heiminstallationen reicht ein kleiner Server. Plane ausreichend Speicher fuer historische Rohdaten und taegliche Rollups ein.

Empfehlung fuer produktiven Betrieb:

- persistentes Volume fuer VictoriaMetrics
- regelmaessige Backups
- getrennte Testinstanzen fuer Migrationsproben
- keine Schreibtests gegen produktive VictoriaMetrics-Instanzen, ausser der Zielstream ist bewusst dafuer angelegt

## Naechste Schritte

- Neuer Stack: [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) oder [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- Grafana: [grafana-install-debian-13.md](./grafana-install-debian-13.md) oder [grafana-install-docker.md](./grafana-install-docker.md)
- Migration: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Dashboard Deployment: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)