# Dashboards

Englische Version: [README_EN.md](./README_EN.md).

Dieses Verzeichnis enthaelt die Grafana-Dashboard-JSON-Dateien fuer den aktuellen VictoriaMetrics-basierten EVCC-Dashboard-Satz und die zugehoerigen Lokalisierungsdaten.

Normale Nutzer muessen hier nichts manuell importieren oder bearbeiten. Der empfohlene Weg ist das Deployment ueber die Skripte in [`../scripts`](../scripts) und die Anleitung in [`../docs/de/grafana-vm-dashboard-setup.md`](../docs/de/grafana-vm-dashboard-setup.md).

## Aktueller Dashboard-Satz

Der aktuelle VM-Deploy importiert die Dateien aus [`deploy-manifest.json`](./deploy-manifest.json):

- `VM_EVCC_All-time.json`
- `VM_EVCC_Year.json`
- `VM_EVCC_Month.json`
- `VM_EVCC_Today-Details.json`
- `VM_EVCC_Today.json`
- `VM_EVCC_Today-Mobile.json`

Die Dateien werden je nach `DASHBOARD_LANGUAGE` aus `translation/<sprache>/` geladen. Mit `DASHBOARD_VARIANT=orig` werden die englischen Quelldashboards aus `original/en/` verwendet.

## Verzeichnisstruktur

- [`original/en/`](./original/en/): Source of Truth fuer die aktuellen VM-Dashboards. Manuelle Dashboard-Aenderungen gehoeren hier hinein.
- [`translation/`](./translation/): generierte lokalisierte Dashboards. Diese Dateien nicht direkt bearbeiten.
- [`localization/`](./localization/): Sprachkonfiguration und Mapping-Dateien fuer die Generierung der lokalen Varianten.
- [`influx-legacy/`](./influx-legacy/): archivierte alte InfluxDB-Dashboards. Sie gehoeren nicht zum aktuellen VM-Deployment.
- [`deploy-manifest.json`](./deploy-manifest.json): feste Liste der Dashboards, die von den Deploy-Skripten importiert werden.

## Bearbeitungsregel

Dashboard-JSON-Dateien werden nur unter `dashboards/original/` manuell bearbeitet. Nach jeder Aenderung muessen die generierten Varianten neu erzeugt werden:

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
```

Danach mindestens die lokalen Checks ausfuehren:

```bash
npm test
npm run test:localization-idempotency
```

## Deployment-Hinweise

Die Dashboards erwarten EVCC-Daten in VictoriaMetrics und die zugehoerigen Rollups. Externe Dienste wie Tibber, Victron VRM oder Solarman sind keine Laufzeit-Datenquellen fuer die Dashboards.

Optionale Header-Links wie EVCC-URL oder ein externes Portal werden beim Deployment ueber die Env-Datei gesetzt. Ohne `DASHBOARD_PORTAL_URL` wird kein Portal-Button angezeigt.
