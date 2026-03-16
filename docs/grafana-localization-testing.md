# Grafana Localization Testing

This document describes the current end-to-end workflow for validating localized dashboards against a real Grafana test instance.

It reflects the actual scripts and conventions used in this repository as of 2026-03-15.

## Scope

Use this workflow when you want to:

- generate localized dashboard JSON files
- import them into a Grafana test folder
- smoke-check that imports succeeded
- create comparable desktop and mobile screenshots
- review remaining untranslated UI text

This workflow does not translate query internals automatically. It validates what is visible in Grafana.

## Prerequisites

- Node.js 20+
- a reachable Grafana test instance
- Grafana API token with dashboard write/delete permissions in the target org
- existing Grafana datasources for EVCC and aggregations, with known UIDs
- for screenshot automation:
  - project dependencies installed via `npm install`
  - Playwright Chromium installed via `npx playwright install chromium`
  - Grafana username/password available for browser login

## Node dependency files

This repository tracks Node dependencies through:

- `package.json`: declares required packages and project metadata
- `package-lock.json`: pins the exact resolved dependency tree for reproducible installs

Use `npm install` to install dependencies exactly as locked in `package-lock.json`.
## Required environment

Use `.env.local` or `.env`.

Required variables:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_EVCC_INFLUXDB_UID`
- `GRAFANA_DS_EVCC_AGGREGATIONS_UID`

Required for screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID` default: `evcc-l10n-test`
- `GRAFANA_TEST_FOLDER_TITLE` default: `EVCC Localization Test`
- `GRAFANA_SCREENSHOT_WAIT_MS` default: `3500`
- `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` if you want to override the built-in time range logic for all dashboards

## Repository conventions

### Source and generated folders

- source dashboards: `dashboards/original/<sourceLanguage>`
- generated localized dashboards: `dashboards/translation/<language>`
- mapping files: `dashboards/localization/<source>_to_<target>.json`
- translation audit reports: `dashboards/localization/missing-<source>_to_<target>.exact.json`

### Import tags and manifests

Current import tags are:

- source reference set: `original-<sourceLanguage>`
- generated sets: `<language>-gen`

Examples:

- `original-de`
- `en-gen`
- `fr-gen`

Current manifest naming:

- `tests/artifacts/import-manifest-original-de.json`
- `tests/artifacts/import-manifest-en-gen.json`
- `tests/artifacts/import-manifest-fr-gen.json`

Do not use old examples like `fr`, `de-orig`, or `import-manifest-fr.json`. Those belong to older intermediate states.

## Step 1: Generate localized dashboards

Run:

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

This copies `dashboards/original/<sourceLanguage>` into every configured target folder under `dashboards/translation/` and applies mapping-based translation for safe text keys.

The generator translates only a limited safe key set such as:

- `title`
- `description`
- `label`
- `name` only when it starts with `EVCC:`
- `displayName`
- `legendFormat`

It intentionally does not translate technical query internals.

## Step 2: Apply safe display-only translations

Run:

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

This second preparation step translates additional safe display-only fields in generated dashboards, especially values that live under generic `value` properties.

Important: run Step 1 and Step 2 strictly in sequence. Do not run them in parallel, otherwise Step 1 can overwrite Step 2 results.

Typical safe cases:

- panel titles
- link titles
- override display names stored in `fieldConfig.overrides[*].properties[*].value`
- variable labels and descriptions

Typical unsafe cases that must not be translated blindly:

- `refId`
- `matcher.options`
- regex matchers
- formulas or expressions that reference translated strings
- `alias` when reused by matcher options, regexes, transformations, or formulas

`apply-safe-display-translations.mjs` now translates `alias` only when a panel-level safety check finds no such coupling.

## Step 3: Audit translation coverage

Run:

```bash
node scripts/localization/audit-localization.mjs
```

This creates per-language candidate files under `dashboards/localization/missing-*.exact.json`.

Use these files to extend the matching `de_to_<lang>.json` mapping under `exact`.

Important:

- this audit only covers the keys handled by the generator
- it does not fully solve texts hidden inside panel override properties or other display-only dashboard fields

## Step 4: Import one language set and smoke-check

Example for French:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=fr-gen --manifest=tests/artifacts/import-manifest-fr-gen.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-fr-gen.json
```

Source reference example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/original/de --tag=original-de --manifest=tests/artifacts/import-manifest-original-de.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-original-de.json
```

## Step 5: Capture screenshots for one set

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-fr-gen.json
```

Outputs:

- `tests/artifacts/screenshots/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/<tag>/mobile/*.png`

### Current screenshot behavior

The screenshot script does not use plain full-page screenshots.

Instead it:

- logs into Grafana with Playwright
- captures the top Grafana toolbar once
- hides the toolbar before panel capture so it is not duplicated
- captures each `.react-grid-item` panel individually
- places the panels onto a PNG canvas at their real dashboard positions
- trims transparent bottom rows
- writes one composed image per dashboard

Why this matters:

- Grafana does not reliably render every panel below the fold on initial load
- without the scroll-and-wait step, some panels can look empty in screenshots even though the live dashboard shows data
- this was especially visible in Today - Details energy-distribution pie charts

### Desktop vs mobile behavior

- desktop screenshots include only non-mobile dashboards
- mobile screenshots include only the dashboard whose source file is `Today (Mobile)`

### Built-in time range behavior

If `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` are not provided, the screenshot script enforces stable comparison ranges based on the dashboard source file or stable dashboard identity:

- All-time: `now-1y/y` to `now`
- Jahr/Year dashboard: `now-1y/y` to `now/y`
- Monat/Month dashboard: `now-1M/M` to `now/M`
- Today - Details: `now-1d/d` to `now/d`

This logic is language-independent.

## Step 6: Run the full suite

Without screenshots:

```bash
node scripts/test/run-suite.mjs --env=.env.local
```

With screenshots:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
```

To test the current generated files without rerunning preparation first:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
```

To finish with an empty Grafana test folder after the run:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

### Full-suite behavior

For each configured set, the suite does:

1. by default regenerate localized dashboards
2. by default apply safe display-only translations
3. if screenshots are enabled, clean the whole Grafana test folder first
4. import the set
5. run smoke-check
6. capture screenshots

This cleanup is important because dashboards and library panels from one language can otherwise leak into the next language run.

### Important operational note

The full suite cleans before each set, not after the last set by default.

Use `--cleanup-final=true` if you want one additional cleanup after the final set.

Without `--cleanup-final=true`, the last processed language remains imported in the Grafana test folder after the suite finishes.

## Cleanup-only command

To remove all dashboards and library panels from the configured test folder:

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```

Datasources are not touched.

## UTF-8 and non-Latin languages

For Hindi, Chinese, or any other non-Latin output, use a UTF-8-safe editing path.

Safe approaches:

- edit the JSON files in a proper UTF-8 editor
- use repository scripts that read/write JSON with Node.js and UTF-8

Risky approaches:

- ad-hoc shell replacements that pass Unicode text through a console/host that is not reliably UTF-8
- PowerShell or command-prompt substitutions that can silently degrade text to `?`

If you see `????` in dashboard JSON or screenshots, assume an encoding failure during file editing, not a Grafana rendering problem.

## Recommended review order

1. run generator
2. run safe display-only translation step
3. run localization audit
4. update mapping JSONs
5. regenerate
6. rerun safe display-only translation step
7. run full suite with screenshots
8. inspect screenshots for each language
9. document remaining coupled or data-driven cases separately

## When to refactor original dashboards instead of patching translations

Patch generated dashboards only for clearly safe display-only fields.

Refactor the original dashboards when untranslated text is tied to:

- `alias` values that are used as internal wiring inputs
- `refId`
- `matcher.options`
- regex matchers
- formulas that refer to localized strings

Long-term maintainability depends on separating internal technical identifiers from visible user-facing labels.


