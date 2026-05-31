# Lokalisierungs-Maintainer-Workflow

Englische Originalfassung: [localization-maintainer-workflow_EN.md](./localization-maintainer-workflow_EN.md).

Dieser Workflow beschreibt die Pflege der generierten Dashboard-Uebersetzungen.

## Grundsatz

Manuell editiert werden nur Quelldashboards unter `dashboards/original/` und Mapping-Dateien unter `dashboards/localization/`. Dateien unter `dashboards/translation/` sind generiert.

## Ablauf

```bash
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm run test:localization-idempotency
npm test
```

## Bei neuen sichtbaren Texten

1. Original-Dashboard aendern.
2. Lokalisierung generieren.
3. Fehlende Mappings pruefen.
4. Mapping-Dateien ergaenzen.
5. Idempotenztest ausfuehren.

## Regeln

- Keine Query- oder UID-Aenderungen durch Uebersetzung.
- Keine manuellen Edits in generierten Dashboard-Dateien.
- Keine gemischten Sprachen in sichtbaren Labels, wenn Mapping vorhanden ist.
- Diffs klein und nachvollziehbar halten.