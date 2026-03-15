# Test Scripts (Grafana)

This folder contains script-based deployment, validation, and cleanup workflows for Grafana dashboard testing.

## Script overview

- `deploy-dashboards.mjs`: High-level deploy workflow (optional purge, import, optional smoke check)
- `import-dashboards.mjs`: Low-level dashboard import primitive (manual-like Grafana import API)
- `smoke-check.mjs`: Post-import validation (metadata + unresolved `${VAR_*}` / `${DS_*}` placeholders)
- `capture-screenshots.mjs`: Screenshot capture for imported dashboards (desktop + mobile)
- `run-suite.mjs`: Bulk import/smoke/screenshot workflow across configured language sets
- `cleanup-grafana.mjs`: Full cleanup in test folder (dashboards + library panels), datasources remain untouched
- `_lib.mjs`: shared helpers (env loading, arg parsing, Grafana API, JSON I/O)

## Required environment

Use `--env=.env.local` (recommended) or `.env` with at least:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_EVCC_INFLUXDB_UID`
- `GRAFANA_DS_EVCC_AGGREGATIONS_UID`

Optional for screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional folder config:

- `GRAFANA_TEST_FOLDER_UID` (default: `evcc-l10n-test`)
- `GRAFANA_TEST_FOLDER_TITLE` (default: `EVCC Localization Test`)

## deploy-dashboards.mjs

Purpose: Deploy one language/variant end-to-end.

Defaults:

- `--variant=generated` (if omitted)
- language source path:
  - `generated` -> `dashboards/<language>`
  - `orig` -> `dashboards/original/<language>`
- default tag: `<language>-gen` or `<language>-orig`
- smoke check enabled unless `--smoke=false`

Parameters:

- `--env=<file>` env file path
- `--language=<code>` language code (for example `de`, `en`, `fr`, `nl`)
- `--variant=generated|orig`
- `--source=<path>` override source path
- `--tag=<tag>` override dashboard tag/prefix
- `--manifest=<path>` override manifest output path
- `--purge=true|false` delete dashboards of same tag first and remove orphan library panels
- `--smoke=true|false` run smoke check after import

Examples:

```bash
# Generated German dashboards
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=de --variant=generated --purge=true

# Original source dashboards from dashboards/original/de
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=de --variant=orig --purge=true

# French generated dashboards
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=fr --purge=true
```

## import-dashboards-raw.mjs

Purpose: Import JSON dashboards into Grafana using `/api/dashboards/import` (closest to manual UI import behavior).

Behavior:

- reads `__inputs` and resolves datasource inputs from env UIDs
- resolves `DS_EXPRESSION` to `__expr__`
- prefixes title with `[<TAG>]`
- rewrites dashboard `uid` with `<tag>-...`
- writes import manifest to `tests/artifacts/import-manifest-<tag>.json`

Parameters:

- `--env=<file>`
- `--source=<path>` dashboard folder
- `--tag=<tag>` import tag/prefix
- `--manifest=<path>` output manifest

Example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/original/de --tag=de-orig
```

## smoke-check.mjs

Purpose: Validate imported dashboards from manifest.

Checks:

- dashboard exists
- title exists
- panel count > 0
- no unresolved import placeholders `${VAR_*}` / `${DS_*}` remain

Parameters:

- `--env=<file>`
- `--manifest=<path>`

Example:

```bash
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-de-orig.json
```

## capture-screenshots.mjs

Purpose: Capture dashboard screenshots from manifest.

Outputs:

- `tests/artifacts/screenshots/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/<tag>/mobile/*.png`

Parameters:

- `--env=<file>`
- `--manifest=<path>`
- `--out=<dir>` optional output root

Example:

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-de-orig.json
```

## run-suite.mjs

Purpose: Run import + smoke (and optional screenshots) for all configured sets.

Behavior:

- reads `dashboards/localization/languages.json`
- includes source set `dashboards/original/<sourceLanguage>` (tag `original-<lang>`)
- includes each generated target folder `dashboards/<lang>`

Parameters:

- `--env=<file>`
- `--screenshots=true|false`

Example:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=false
```

## cleanup-grafana.mjs

Purpose: Remove all dashboards and all library panels inside the test folder.

Important:

- Datasources are NOT touched.

Parameters:

- `--env=<file>`
- `--folderUid=<uid>` optional override

Example:

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```

## Maintenance note

This README must be updated whenever script names, defaults, parameters, or behavior in `scripts/test/` change.

## Screenshot Notes

Current screenshot implementation uses a composed image instead of plain full-page screenshots:

- capture the global Grafana toolbar once at the top
- hide the toolbar before panel captures so it is not duplicated inside charts
- capture each `.react-grid-item` panel separately and place it at its absolute dashboard position
- trim transparent bottom rows from the final PNG
- only capture non-mobile dashboards in `desktop` and only mobile dashboards in `mobile`

Dashboard-specific time ranges currently enforced when no explicit `--from/--to` override is given:

- `EVCC: All-time` -> `now-1y/y` to `now`
- `EVCC: Jahr` -> `now-1y/y` to `now/y`
- `EVCC: Monat` -> `now-1M/M` to `now/M`
- `EVCC: Today - Details` -> `now-1d/d` to `now/d`

Known maintenance detail:

- Grafana CSS class names for the top toolbar can change between Grafana versions. If duplicate toolbars reappear in screenshots, inspect the current DOM and update the selector list in `capture-screenshots.mjs`.
