# Maintainer Workflow for Localization

This document describes the current maintainer-facing workflow for the default VictoriaMetrics dashboard family.

Default family:

- `vm`

Legacy family:

- `influx-legacy`

The VM flow uses the short default paths under `dashboards/`.

## Mental model

There are two translation layers in this repository.

### Layer 1: Mapping-driven generation

Source:

- `dashboards/original/<sourceLanguage>`

Mappings:

- `dashboards/localization/<source>_to_<target>.json`

Generated output:

- `dashboards/translation/<language>`

This layer is scripted and should always run first.

### Layer 2: Safe display-only cleanup

After generation, some visible UI texts may still remain untranslated because they are stored in dashboard-specific display properties that are not fully covered by the generator.

Examples:

- display-name overrides in panel field config
- some panel titles
- some variable labels or descriptions

This layer is also scripted and runs only on generated dashboards.

Do not apply it to `dashboards/original` unless you are intentionally refactoring the VM source dashboards.

## Current VM scope

Current upstream VM source set:

- `dashboards/original/en/VM_ EVCC_ Today.json`
- `dashboards/original/en/VM_ EVCC_ Today - Mobile.json`
- `dashboards/original/en/VM_ EVCC_ Today - Details.json`

Important note:

- the imported upstream snapshot is mixed-language
- several visible labels are still German even though the source family is treated as `en`

## Repository scope

- language config: `dashboards/localization/languages.json`
- source of truth: `dashboards/original/<sourceLanguage>`
- per-language mapping: `dashboards/localization/<source>_to_<target>.json`
- generated outputs: `dashboards/translation/<language>`

## Prerequisites

- Node.js 20+
- ability to run commands from repository root
- for Grafana validation, see `docs/grafana-localization-testing.md`

## Standard update workflow

### 1. Update source dashboards if needed

Edit:

- `dashboards/original/<sourceLanguage>`

Only do this for real source changes or structural panel refactors.

### 2. Update mapping files

Edit the relevant mapping JSON files, for example:

- `dashboards/localization/en_to_de.json`
- `dashboards/localization/en_to_fr.json`
- `dashboards/localization/en_to_hi.json`

Use `exact` for full labels and stable phrases.

Use `contains` only for very stable token replacements that are safe across contexts.

### 3. Generate localized dashboards

```bash
node scripts/localization/generate-localized-dashboards.mjs --family=vm
```

### 4. Apply safe display-only translations

Important: run this step only after step 3 has fully finished. Do not run both scripts in parallel.

```bash
node scripts/localization/apply-safe-display-translations.mjs --family=vm
```

This step only touches user-visible fields in generated dashboards, for example:

- panel titles
- link titles
- variable labels and descriptions
- override `displayName` values

### 5. Audit missing mapping coverage

```bash
node scripts/localization/audit-localization.mjs --family=vm
```

Review generated candidate files:

- `dashboards/localization/missing-<source>_to_<target>.exact.json`

Merge relevant entries into the real mapping file and regenerate.

### 6. Review generated dashboards for remaining visible source-language text

Review methods:

- inspect JSON directly
- or preferably run Grafana screenshots and inspect the rendered dashboards

### 7. Validate in Grafana

Use the full testing workflow from:

- `docs/grafana-localization-testing.md`

For the standard end-to-end path, `run-suite.mjs` runs both preparation steps automatically unless disabled with `--prepare=false`.

## Safe vs unsafe translation rule

### Safe

A string is safe when it is only visible to the user and not used for internal wiring.

Common safe examples:

- `displayName` override values
- panel titles
- link titles
- variable labels and descriptions

### Unsafe until refactored

A string is unsafe when it is used to connect panel logic.

Common examples:

- `refId`
- `alias` values that are reused in matcher options, regexes, transformations, or formulas
- `matcher.options`
- regex matchers
- formulas referencing localized names

The scripted alias translation in `apply-safe-display-translations.mjs` performs a panel-level safety check and skips aliases that appear coupled to internal wiring.

## Long-term maintainability rule

If a visible label is also used as an internal key, the panel design is not localization-friendly.

Preferred design:

- stable internal ids such as `gridImport`, `selfConsumption`, `batteryCharge`
- translated labels only in display properties

This is the main structural improvement maintainers should aim for in VM source dashboards and library panels.

## Current VM milestone

As of 2026-03-21:

- default family config is in place
- target languages are `de`, `fr`, `nl`, `es`, `it`, `zh`, `hi`
- the current three-dashboards VM source set generates cleanly
- localization audit is clean for the current scripted key set

## Review checklist before commit

- source dashboards changed only if intentionally required
- mapping files updated where possible instead of patching generated JSON first
- generated dashboards regenerated after mapping changes
- safe display-only translations applied through `apply-safe-display-translations.mjs`
- no accidental unsafe change to `refId`, `matcher.options`, regexes, or formulas
- full Grafana smoke-check and screenshot run completed
- remaining coupled or data-driven text documented separately
