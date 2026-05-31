# Migration Troubleshooting

Englische Version: [migration-troubleshooting_EN.md](./migration-troubleshooting_EN.md).

Diese Datei hilft bei typischen Problemen nach Import, Rollup und Dashboard-Deployment.

## Keine Daten in `Today`

Pruefe:

- Schreibt EVCC/Telegraf wirklich nach VictoriaMetrics?
- Ist die VictoriaMetrics URL korrekt?
- Nutzt Grafana die richtige Datasource UID (`vm-evcc` oder konfiguriert via `GRAFANA_DS_VM_EVCC_UID`)?
- Sind Zeitbereich und Zeitzone in Grafana korrekt?

Schnelltest:

```bash
curl -G http://<vm-host>:8428/api/v1/series --data-urlencode 'match[]=grid_power'
```

## Langzeit-Dashboards leer

`Month`, `Year` und `All-time` verwenden `evcc_*` Rollups. Wenn diese Dashboards leer sind, fehlen meist Rollup-Daten.

Pruefe:

```bash
curl -G http://<vm-host>:8428/api/v1/series --data-urlencode 'match[]=evcc_*'
```

Danach Rollup neu ausfuehren und Logs pruefen.

## PV, Batterie oder Ladepunkte fehlen

Moegliche Ursachen:

- EVCC liefert andere Labelnamen als erwartet.
- Blocklist-Variablen blenden Reihen aus.
- Import hat bestimmte Measurements nicht uebernommen.
- Der aktuelle Zeitraum enthaelt keine Daten.

Pruefe die Dashboard-Variablen in Grafana und die Overrides in `vm-dashboard-install.env`, besonders:

```env
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST
DASHBOARD_FILTER_VEHICLE_BLOCKLIST
DASHBOARD_FILTER_EXT_BLOCKLIST
DASHBOARD_FILTER_AUX_BLOCKLIST
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX
```

## Deployer liest falsche Quelle

`DASHBOARD_SOURCE_MODE` darf nur einmal aktiv gesetzt sein. Wenn derselbe Key mehrfach in der Env-Datei vorkommt, brechen die Deployer ab.

Gueltige Modi:

```env
DASHBOARD_SOURCE_MODE=github
DASHBOARD_SOURCE_MODE=rawurl
DASHBOARD_SOURCE_MODE=localdir
```

Nur eine dieser Zeilen darf aktiv sein.

## Grafana 401 Unauthorized

Grafana 13 unterstuetzt die alten API-Routen weiterhin, API Keys sind aber veraltet. Nutze einen Service-Account-Token:

```env
GRAFANA_AUTH_MODE=auto
GRAFANA_API_TOKEN=<service-account-token>
```

Alternativ fuer lokale Recovery:

```env
GRAFANA_AUTH_MODE=basic
GRAFANA_USER=admin
GRAFANA_PASSWORD=<passwort>
```

## Rollup-Werte wirken falsch

Pruefe:

- Start- und Enddatum des Rollups
- `--replace-range` bei Wiederholungslauf
- Zeitzone des Hosts
- Import-Abdeckung gegen InfluxDB
- bekannte Ausnahmen in [migration-validation-notes.md](./migration-validation-notes.md)

## Weitere Diagnose

- [migration-validation-notes.md](./migration-validation-notes.md)
- [migration-checklist.md](./migration-checklist.md)
- [vm-dashboard-install.md](./vm-dashboard-install.md)