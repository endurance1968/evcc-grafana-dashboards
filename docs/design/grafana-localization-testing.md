# Grafana Lokalisierungs-Testing

Englische Originalfassung: [grafana-localization-testing_EN.md](./grafana-localization-testing_EN.md).

Dieses Dokument beschreibt, wie generierte Dashboard-Uebersetzungen getestet werden.

## Ziele

- Uebersetzungen duerfen Query-Logik nicht veraendern.
- UIDs, Datasource-Verweise und Metriknamen muessen stabil bleiben.
- Generierte Dateien muessen idempotent sein.
- Grafana muss die lokalisierten Dashboards importieren und rendern koennen.

## Standardchecks

```bash
npm test
npm run test:localization-idempotency
npm run test:render-e2e
```

## Was geprueft wird

- JSON-Syntax
- Dashboard-Semantik
- reproduzierbare Generierung
- sichere Display-only-Uebersetzungen
- Render-Smoke fuer kritische Panels

## Regeln fuer neue Texte

- Sichtbare Texte in Mappings pflegen.
- Technische Tokens nicht uebersetzen.
- Query-Ausdruecke nicht veraendern.
- Panel- und Variablen-IDs stabil halten.