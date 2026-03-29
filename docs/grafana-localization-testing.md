# Grafana Localization Testing

This document describes the current end-to-end workflow for validating the default VictoriaMetrics dashboard family against a real Grafana test instance.

Legacy Influx validation still exists, but it now lives under `--family=influx-legacy`.

## Scope

Use this workflow when you want to:

- generate localized dashboard JSON files
- import them into a Grafana test folder
- smoke-check that imports succeeded
- create comparable desktop and mobile screenshots
- review remaining untranslated UI text

This workflow validates what is visible in Grafana. It does not blindly translate query internals.

## Prerequisites

- Node.js 20+
- a reachable Grafana test instance
- Grafana API token with dashboard write/delete permissions in the target org
- a configured VictoriaMetrics datasource for EVCC
- for screenshot automation:
  - project dependencies installed via `npm install`
  - Playwright Chromium installed via `npx playwright install chromium`
  - Grafana username/password available for browser login

## Required environment

Use `.env.local` or `.env`.

Required variables for VM:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_VM_EVCC_UID`

If `GRAFANA_DS_VM_EVCC_UID` is not set, the importer falls back to `vm-evcc`, which matches the current test instance described in `docs/victoriametrics-handoff-2026-03-21.md`.

Required for screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID` default: `evcc-test`
- `GRAFANA_TEST_FOLDER_TITLE` default: `EVCC Test`
- `GRAFANA_SCREENSHOT_WAIT_MS` default: `3500`
- `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` if you want to override the built-in time range logic

## Repository conventions

### Source and generated folders

- source dashboards: `dashboards/original/<sourceLanguage>`
- generated localized dashboards: `dashboards/translation/<language>`
- mapping files: `dashboards/localization/<source>_to_<target>.json`
- translation audit reports: `dashboards/localization/missing-<source>_to_<target>.exact.json`

### Import tags and manifests

Current VM import tags:

- source reference set: `vm-original-<sourceLanguage>`
- generated sets: `vm-<language>-gen`

Current manifest naming:

- `tests/artifacts/import-manifest-vm-original-en.json`
- `tests/artifacts/import-manifest-vm-de-gen.json`
- `tests/artifacts/import-manifest-vm-fr-gen.json`

## Step 1: Generate localized dashboards

```bash
node scripts/localization/generate-localized-dashboards.mjs --family=vm
```

This copies `dashboards/original/<sourceLanguage>` into every configured target folder under `dashboards/translation/` and applies mapping-based translation for safe text keys.

## Step 2: Apply safe display-only translations

```bash
node scripts/localization/apply-safe-display-translations.mjs --family=vm
```

Important: run Step 1 and Step 2 strictly in sequence. Do not run them in parallel.

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

## Step 3: Audit translation coverage

```bash
node scripts/localization/audit-localization.mjs --family=vm
```

This creates per-language candidate files under `dashboards/localization/missing-*.exact.json`.

## Step 4: Import one language set and smoke-check

Example for French:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=vm-fr-gen --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

Source reference example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/original/en --tag=vm-original-en --manifest=tests/artifacts/import-manifest-vm-original-en.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-original-en.json
```

## Step 5: Capture screenshots for one set

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

Outputs:

- `tests/artifacts/screenshots/vm/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/vm/<tag>/mobile/*.png`

## Step 6: Run the full suite

Without screenshots:

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local
```

With screenshots:

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true
```

To test the current generated files without rerunning preparation first:

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true --prepare=false
```

To finish with an empty Grafana test folder after the run:

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true --cleanup-final=true
```

### Full-suite behavior

For each configured set, the suite does:

1. regenerate localized dashboards unless `--prepare=false`
2. apply safe display-only translations unless `--prepare=false`
3. if screenshots are enabled, clean the whole Grafana test folder first
4. import the set
5. run smoke-check
6. capture screenshots

## Cleanup-only command

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```

Datasources are not touched.

## Current screenshot layout

VM screenshots are grouped under:

- `tests/artifacts/screenshots/vm/original-en`
- `tests/artifacts/screenshots/vm/en-gen`
- `tests/artifacts/screenshots/vm/de-gen`
- and so on

Legacy Influx screenshots are grouped separately under:

- `tests/artifacts/screenshots/influx-legacy/...`

## VM-specific note

The current upstream VM source is only a three-dashboard snapshot and still contains mixed-language internals.

That means:

- the current workflow is good enough for localization, smoke checks, and screenshot review
- some remaining source-language internals may still require source refactors later
