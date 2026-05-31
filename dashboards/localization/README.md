# Dashboard-Lokalisierung

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt Mapping-Dateien fuer generierte Dashboard-Uebersetzungen.

## Grundprinzip

- Quelldashboards liegen unter `dashboards/original/`.
- Generierte Uebersetzungen liegen unter `dashboards/translation/`.
- Uebersetzungs-Mappings liegen in diesem Ordner.
- Generierte Dateien werden nicht manuell editiert.

## Workflow

Nach Aenderungen an Original-Dashboards:

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm run test:localization-idempotency
```

## Regeln

- Nur sichtbare Texte uebersetzen.
- Query-Logik, Metriknamen, Labels, UIDs und Datasource-Verweise nicht uebersetzen.
- Aenderungen muessen idempotent sein.
- Neue sichtbare Texte in den Mapping-Dateien pflegen.