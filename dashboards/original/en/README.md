# Englische Original-Dashboards

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt die englischen Quelldashboards. Sie sind die Basis fuer generierte lokalisierte Varianten.

## Bearbeitungsregel

Dashboard-JSON-Dateien werden nur unter `dashboards/original/` manuell bearbeitet. Dateien unter `dashboards/translation/` werden generiert.

## Nach Aenderungen

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm test
```