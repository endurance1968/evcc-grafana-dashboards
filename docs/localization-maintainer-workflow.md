# Maintainer Workflow for Localization

This document is the maintainer-facing workflow for updating dashboard translations without any AI-specific tooling.

It is intended for someone with general software engineering experience who needs a reproducible process.

## Mental model

There are two translation layers in this repository.

### Layer 1: Mapping-driven generation

Source:

- `dashboards/original/<sourceLanguage>`

Mappings:

- `dashboards/localization/<source>_to_<target>.json`

Generated output:

- `dashboards/translation/<language>`

This layer is scriptable and should always run first.

### Layer 2: Safe display-only cleanup

After generation, some visible UI texts may still remain untranslated because they are stored in dashboard-specific display properties that are not fully covered by the generator.

Examples:

- display-name overrides in panel field config
- some panel titles
- some variable labels or descriptions

This layer is now a scripted follow-up step on the generated dashboards only.

Do not apply this step to `dashboards/original` unless you are intentionally refactoring the source dashboards.

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

- `dashboards/localization/de_to_en.json`
- `dashboards/localization/de_to_fr.json`
- `dashboards/localization/de_to_hi.json`

Use `exact` for full labels and stable phrases.

Use `contains` only for very stable token replacements that are safe across contexts.

### 3. Generate localized dashboards

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

### 4. Apply safe display-only translations

Important: run this step only after step 3 has fully finished. Do not run both scripts in parallel.

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

This step only touches user-visible fields in generated dashboards, for example:

- panel titles
- link titles
- variable labels and descriptions
- override `displayName` values

### 5. Audit missing mapping coverage

```bash
node scripts/localization/audit-localization.mjs
```

Review generated candidate files:

- `dashboards/localization/missing-<source>_to_<target>.exact.json`

Merge relevant entries into the real mapping file and regenerate.

### 6. Review generated dashboards for remaining visible source-language text

Review methods:

- inspect JSON directly
- or preferably run Grafana screenshots and inspect the rendered dashboards

### 7. Apply additional safe display-only fixes only if still needed

Allowed targets:

- panel titles
- link titles
- variable labels and descriptions
- override display labels stored in `fieldConfig.overrides[*].properties[*].value`
- query `alias` values, but only when no panel-internal wiring references those alias strings

Do not change blindly:

- `refId`
- `matcher.options`
- regexes
- transformations that match by field name
- formulas or expressions using those names

The scripted `alias` translation in `apply-safe-display-translations.mjs` performs a panel-level safety check and skips aliases that appear coupled to internal wiring.

### 8. Validate in Grafana

Use the full testing workflow from:

- `docs/grafana-localization-testing.md`

For the standard end-to-end path, `run-suite.mjs` now runs both preparation steps automatically unless disabled with `--prepare=false`.

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
- regex matchers like `^Kilometerstand: .*$`
- formulas referencing localized names

## Long-term maintainability rule

If a visible label is also used as an internal key, the panel design is not localization-friendly.

Preferred design:

- stable internal ids such as `gridImport`, `selfConsumption`, `batteryCharge`
- translated labels only in display properties

This is the main structural improvement maintainers should aim for in source dashboards and library panels.

## Non-Latin language rule

For Hindi, Chinese, and similar languages:

- edit JSON through a UTF-8-safe editor or Node.js script
- avoid console-based replacements that can degrade Unicode text to `?`

If a screenshot suddenly shows `????`, treat that as an encoding corruption issue in the edited JSON.

## Review checklist before commit

- source dashboards changed only if intentionally required
- mapping files updated where possible instead of patching generated JSON first
- generated dashboards regenerated after mapping changes
- safe display-only translations applied through `apply-safe-display-translations.mjs`
- any extra manual safe fixes limited to generated dashboards
- no accidental unsafe change to `refId`, `matcher.options`, regexes, or formulas
- full Grafana smoke-check and screenshot run completed
- remaining coupled or data-driven text documented separately

## Recommended commit structure

Suggested structure for a non-trivial localization update:

1. `chore: extend localization mappings`
2. `chore: regenerate localized dashboards`
3. `fix: translate safe display-only dashboard labels`
4. `test: refresh Grafana localization screenshots`
5. `docs: update localization maintainer workflow`

