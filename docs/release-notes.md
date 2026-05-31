# Release Notes

Englische Version: [release-notes_EN.md](./release-notes_EN.md).

## Erste EVCC VictoriaMetrics Dashboard Version

Diese Version stellt den Grafana-13-Tab-Dashboardpfad fuer EVCC auf VictoriaMetrics bereit.

## Highlights

- VictoriaMetrics-basierte EVCC-Dashboards
- Migration von InfluxDB-Historie nach VictoriaMetrics
- taegliche `evcc_*` Rollups fuer Monats-, Jahres- und All-Time-Ansichten
- lokalisierte Dashboard-Varianten
- Grafana 13 Tab Navigation als Standard
- Deploy-Skripte fuer Linux, Bash + `jq` und Windows PowerShell
- Dashboard-Variable-Overrides per Env-Datei
- `PURGE_ONLY` zum reinen Entfernen bekannter Dashboards und Library Panels

## Deployment

Unterstuetzte Deployer:

- `scripts/deploy-python.sh` fuer Linux und Raspberry-Pi-aehnliche Systeme
- `scripts/deploy-bash.sh` fuer Bash + `jq`
- `scripts/deploy.ps1` fuer Windows PowerShell

Die Deployer verwenden eine gemeinsame `vm-dashboard-install.env`.

## Wichtige Anforderungen

- Grafana 13.0.1 oder neuer
- VictoriaMetrics Datasource Plugin
- VictoriaMetrics mit EVCC-Rohdaten
- `evcc_*` Rollups fuer Langzeit-Dashboards

## Bekannte Hinweise

- Dashboard-Set-Auswahl ist entfernt.
- Der Row-basierte alte Deploypfad ist entfernt.
- Jeder Env-Key darf nur einmal aktiv gesetzt sein.
- Produktionsdaten sollten in Tests nur lesend verwendet werden.

## Screenshots

Die Release-Screenshots liegen direkt unter [screenshots](./screenshots/README.md) und zeigen bei Tab-Dashboards die aktive Grafana-Tab-Leiste.

## Einstieg

- [README.md](../README.md)
- [docs/README.md](./README.md)
- [deployment-readme.md](./deployment-readme.md)
