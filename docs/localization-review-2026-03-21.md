# VM Localization Review

Stand: 2026-03-21

This note records the review state after the first complete VictoriaMetrics localization flow for the current three-dashboard source set.

## Validation status

Completed successfully:

- mapping-driven generation for `en`, `de`, `fr`, `nl`, `es`, `it`, `zh`, `hi`
- safe display-only follow-up step
- localization audit with zero current missing candidates
- full Grafana import + smoke-check + screenshot suite
- final Grafana cleanup

Executed command:

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true --cleanup-final=true
```

Screenshot output:

- `tests/artifacts/screenshots/vm/original-en`
- `tests/artifacts/screenshots/vm/en-gen`
- `tests/artifacts/screenshots/vm/de-gen`
- `tests/artifacts/screenshots/vm/fr-gen`
- `tests/artifacts/screenshots/vm/nl-gen`
- `tests/artifacts/screenshots/vm/es-gen`
- `tests/artifacts/screenshots/vm/it-gen`
- `tests/artifacts/screenshots/vm/zh-gen`
- `tests/artifacts/screenshots/vm/hi-gen`

## Fixed during this milestone

### 1. VM datasource fallback

Problem:

- the VM flow initially depended on `GRAFANA_DS_VM_EVCC_UID` being present locally

Change:

- `scripts/test/import-dashboards-raw.mjs` now falls back to `vm-evcc` for the default VM test datasource UID

### 2. Mobile screenshot detection

Problem:

- translated VM mobile dashboards were partially captured as desktop screenshots because the source filename pattern `Today - Mobile` was not recognized

Change:

- `scripts/test/capture-screenshots.mjs` now recognizes both `Today (Mobile)` and `Today - Mobile`

### 3. Translated bar-chart regression

Problem:

- the `EVCC: VM: Energie` panel broke in translated dashboards because `legendFormat: Energie` was translated while internal `options.xField` still pointed to the old source label

Change:

- `scripts/localization/apply-safe-display-translations.mjs` now updates `options.xField` when it safely follows a translated `legendFormat` inside the same panel

Result:

- the translated bar chart renders again in the screenshot sets

## Remaining review findings

### 1. Source-coupled German internals still exist

These are not current translation misses. They are source-design coupling and must not be translated blindly.

Examples:

- `dashboards/translation/fr/VM_ EVCC_ Today.json`
  - matcher options like `Haus`, `Netz`, `Speicher`, `Netzbezug`, `Speicher laden`, `Speicher entladen`
  - refIds like `Autarkie` and `Eigenverbrauch`
- `dashboards/translation/fr/VM_ EVCC_ Today - Details.json`
  - matcher options like `Sonstige`, `Haus`, `Netzbezug`
  - refId `Ladeleistung`

Why this matters:

- these values are still used as internal selectors or expression anchors
- translating them directly would break panel logic

Required long-term fix:

- refactor VM source dashboards so internal ids are stable and language-neutral

### 2. Data-driven labels remain installation-specific

Visible examples in screenshots:

- `Carport_Ecke`
- `Carport_Treppe`
- `Daikin-WP`
- `Altherma-3`
- `BMW i3`

Classification:

- site-specific or datasource-driven labels
- not shared localization mapping errors

### 3. Grafana chrome remains outside dashboard localization scope

Visible examples in screenshots:

- `Today`
- `Refresh`
- `30s`

Classification:

- Grafana UI, not dashboard JSON content

## Practical conclusion

The first VM milestone is ready as a working localization/test pipeline:

- source under `dashboards/original/en`
- generated outputs under `dashboards/translation/<language>`
- clean audit
- real Grafana validation
- screenshot evidence

The next real engineering step is no longer pipeline setup. It is source refactoring of the VM dashboards so visible labels stop doubling as internal wiring keys.
