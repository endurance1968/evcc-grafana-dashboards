# Englischer VM-Dashboard-Quellimport

Englische Version: [README_EN.md](./README_EN.md).

Diese Dateien basieren auf dem Maintainer-Branch `upstream/victoria-metrics`; `VM_EVCC_Today-Gauges.json` ist eine lokale Today-Variante mit zusaetzlichem Gauge-Kopfbereich.

Importierte Dateien:

- `VM_EVCC_Today.json`
- `VM_EVCC_Today-Gauges.json`
- `VM_EVCC_Today-Details.json`
- `VM_EVCC_Today-Mobile.json`
- `VM_EVCC_All-time.json`
- `VM_EVCC_Month.json`
- `VM_EVCC_Year.json`

Wichtiger Hinweis:

- Der Maintainer-Branch stellt diese Dateien aktuell nicht als vollstaendig englische Dashboards bereit.
- Sie enthalten gemischtsprachige Labels und Beschreibungen, mit einem merklichen Anteil deutscher UI-Texte.
- Sie werden hier als importierter Upstream-Quell-Snapshot fuer weitere Lokalisierung und Review auf diesem Branch gespeichert.

## Bearbeitungsregel

Dashboard-JSON-Dateien werden nur unter `dashboards/original/` manuell bearbeitet. Dateien unter `dashboards/translation/` werden generiert.

## Nach Aenderungen

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm test
```
