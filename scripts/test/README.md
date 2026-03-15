# Test Scripts (Grafana)

This folder contains the script-based Grafana test workflow used to import localized dashboards, validate them, and create review screenshots.

## Script overview

- `deploy-dashboards.mjs`: high-level deploy workflow for a single language or variant
- `import-dashboards.mjs`: low-level dashboard import primitive
- `import-dashboards-raw.mjs`: import via Grafana's raw dashboard import endpoint
- `smoke-check.mjs`: post-import validation
- `capture-screenshots.mjs`: browser-based screenshot capture
- `run-suite.mjs`: batch import/smoke/screenshot workflow across all configured sets
- `cleanup-grafana.mjs`: full cleanup of dashboards and library panels in the Grafana test folder
- `_lib.mjs`: shared helpers

Localization preparation scripts used before test runs:

- `../localization/generate-localized-dashboards.mjs`: regenerate `dashboards/translation/<language>`
- `../localization/apply-safe-display-translations.mjs`: apply safe display-only translations to generated dashboards

## Required environment

Use `--env=.env.local` or `.env`.

Required:

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
- `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` if you want a global override for screenshot time ranges

## Current naming convention

The suite currently uses these tags:

- source reference set: `original-<sourceLanguage>`
- generated localized set: `<language>-gen`

Examples:

- `original-de`
- `en-gen`
- `fr-gen`

Manifests are written to:

- `tests/artifacts/import-manifest-original-de.json`
- `tests/artifacts/import-manifest-en-gen.json`
- and so on

## import-dashboards-raw.mjs

Purpose: import JSON dashboards into Grafana using the raw import endpoint.

Behavior:

- resolves datasource inputs from env UIDs
- resolves `DS_EXPRESSION` to `__expr__`
- prefixes dashboard title with `[<TAG>]`
- rewrites dashboard UID using the tag
- writes an import manifest to `tests/artifacts/import-manifest-<tag>.json`

Typical example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=fr-gen --manifest=tests/artifacts/import-manifest-fr-gen.json
```

## smoke-check.mjs

Purpose: validate imported dashboards from a manifest.

Checks:

- dashboard exists
- title exists
- panel count greater than zero
- no unresolved import placeholders like `${VAR_*}` or `${DS_*}`

Example:

```bash
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-fr-gen.json
```

## capture-screenshots.mjs

Purpose: capture deterministic dashboard screenshots for review.

Outputs:

- `tests/artifacts/screenshots/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/<tag>/mobile/*.png`

Example:

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-fr-gen.json
```

## Screenshot implementation

This script does not use plain full-page screenshots.

Current implementation:

- log into Grafana with Playwright
- load the dashboard in kiosk mode
- capture the global toolbar once at the top
- hide the toolbar before panel capture so it is not duplicated
- capture each `.react-grid-item` separately
- place each panel image at its actual dashboard coordinates on a PNG canvas
- trim transparent bottom rows

This approach exists because long Grafana dashboards often render badly in naive full-page screenshots. Grafana also lazy-renders panels outside the viewport, so panel screenshots must scroll into view first or some panels can appear blank even though data is present in the live dashboard.

## Desktop/mobile split

- `desktop` captures only non-mobile dashboards
- `mobile` captures only the dashboard whose source file is `Today (Mobile)`

The detection is based on stable source-file/UID signals, not on translated dashboard titles.

## Screenshot filenames

Filenames are human-readable when possible.

Behavior:

- use a slug based on the dashboard title if it is stable enough
- fall back to UID-based slug when the title is too short or not useful
- this fallback is important for non-Latin titles to avoid filename collisions

## Time range behavior

If `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` are not set, the script applies built-in stable ranges based on dashboard identity:

- All-time: `now-1y/y` to `now`
- Jahr/Year: `now-1y/y` to `now/y`
- Monat/Month: `now-1M/M` to `now/M`
- Today - Details: `now-1d/d` to `now/d`

This matching is language-independent and uses stable dashboard identity instead of relying only on translated titles.

## run-suite.mjs

Purpose: run preparation + import + smoke + optional screenshot generation for all configured sets.

Behavior:

- by default runs localization preparation first:
  - `generate-localized-dashboards.mjs`
  - `apply-safe-display-translations.mjs`
- reads `dashboards/localization/languages.json`
- includes the source reference set as `original-<sourceLanguage>`
- includes each generated target folder as `<language>-gen`
- when `--screenshots=true`, runs `cleanup-grafana.mjs` before each set
- imports the set
- runs smoke-check
- optionally captures screenshots

Example:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
```

To test the current files without regenerating them first:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
```

Important operational detail:

- the suite cleans before each set, not after the last one
- the last imported language remains in the Grafana test folder after the suite finishes

## cleanup-grafana.mjs

Purpose: remove all dashboards and all library panels inside the configured Grafana test folder.

Important:

- datasources are not touched

Example:

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```

## UTF-8 warning

If you edit localized dashboard JSON for non-Latin languages such as Hindi or Chinese, use a UTF-8-safe path.

Recommended:

- UTF-8 editor
- Node.js script that reads and writes JSON as UTF-8

Avoid:

- ad-hoc console substitutions that can turn Unicode text into `?`

If screenshots suddenly show `????`, first inspect the JSON files for encoding corruption.

## Maintenance note

Update this README whenever script names, defaults, tags, screenshot behavior, or workflow assumptions change.
