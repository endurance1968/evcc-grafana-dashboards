# Setup- und Filter-Statuspanel

Englische Version: [setup-filter-status-panel-decision_EN.md](./setup-filter-status-panel-decision_EN.md).

## Entscheidung

Es wird kein dauerhaft sichtbares Setup- oder Filter-Statuspanel in die Standard-Dashboards aufgenommen.

Die wichtigsten Deploy- und Filterwerte bleiben ueber diese Wege nachvollziehbar:

- `Build`-Variable im Dashboard-Header: zeigt Deployment-Zeitpunkt, Sprache/Variante und Source Ref im Tooltip.
- Dashboard-Variablen in Grafana: zeigen die wirksamen Werte wie `peakPowerLimit`, `energySampleInterval`, `tariffPriceInterval`, `loadpointBlocklist`, `extBlocklist`, `auxBlocklist`, `vehicleBlocklist` und `heatPumpLoadpointRegex`.
- `vm-dashboard-install.env`: bleibt die fuehrende Konfigurationsquelle fuer Deploy-Overrides.
- Troubleshooting-Doku: beschreibt, wie EVCC-Labels und Blocklists geprueft werden.

## Begruendung

Ein sichtbares Statuspanel wuerde auf jeder Anlage Platz verbrauchen, obwohl diese Werte nur bei Setup, Fehlersuche oder Review gebraucht werden. Fuer normale Nutzung sind Energie-, Leistungs-, Ladepunkt-, Fahrzeug- und Kostenwerte wichtiger als interne Filterkonfiguration.

Ein Panel wuerde ausserdem leicht den Eindruck erwecken, dass Blocklists Daten veraendern. Das stimmt nicht: Blocklists filtern nur die Dashboard-Anzeige und loeschen oder migrieren keine VictoriaMetrics-Serien.

## Wann neu bewerten?

Die Entscheidung kann neu bewertet werden, wenn ein eigener Diagnose- oder Setup-Tab entsteht, der nicht die normale Tages-, Monats-, Jahres- oder Gesamtansicht stoert. Dann sollte das Panel optional dort liegen und nur lesend folgende Werte anzeigen:

- Build-Info
- Datasource-UID
- wichtige Zeitintervalle
- Peak-Power-Limit
- aktive Blocklists
- Heat-Pump-Regex

## Verweise

- Deploy-Optionen: [../vm-dashboard-install.md](../vm-dashboard-install.md)
- EVCC-/Telegraf-Live-Ingest: [../evcc-telegraf-live-ingest.md](../evcc-telegraf-live-ingest.md)
- Troubleshooting fuer Labels und Blocklists: [../migration-troubleshooting.md#fachlabels-titles-und-blocklists](../migration-troubleshooting.md#fachlabels-titles-und-blocklists)