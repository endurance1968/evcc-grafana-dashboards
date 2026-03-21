# Test Scripts (Grafana)

This folder contains the script-based Grafana validation workflow used to import dashboards, run smoke checks, and create review screenshots.

Default family:

- `vm`

Legacy family:

- `influx-legacy`

Without `--family=...`, the scripts use the default VM path.

## Script overview

- `deploy-dashboards.mjs`: high-level deploy workflow for a single language or variant
- `import-dashboards-raw.mjs`: import via Grafana's raw dashboard import endpoint
- `smoke-check.mjs`: post-import validation
- `capture-screenshots.mjs`: browser-based screenshot capture
- `run-suite.mjs`: batch import/smoke/screenshot workflow across all configured sets
- `cleanup-grafana.mjs`: full cleanup of dashboards and library panels in the Grafana test folder
- `_lib.mjs`: shared helpers

Localization preparation scripts used before test runs:

- `../localization/generate-localized-dashboards.mjs`: regenerate `dashboards/translation/<language>` for VM
- `../localization/apply-safe-display-translations.mjs`: apply safe display-only translations to generated dashboards

For legacy Influx, run the same commands with `--family=influx-legacy`.

## Required environment

Use `--env=.env.local` or `.env`.

Always required:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`

Required for VM imports:

- `GRAFANA_DS_VM_EVCC_UID`

If this variable is not set, the importer falls back to `vm-evcc`, which matches the current VM test datasource UID from the handoff docs.

Required for Influx legacy imports:

- `GRAFANA_DS_EVCC_INFLUXDB_UID`
- `GRAFANA_DS_EVCC_AGGREGATIONS_UID`

Required for screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID` default: `evcc-l10n-test`
- `GRAFANA_TEST_FOLDER_TITLE` default: `EVCC Localization Test`
- `GRAFANA_SCREENSHOT_WAIT_MS` default: `3500`
- `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` for a global screenshot time override

## Naming convention

VM tags:

- source reference set: `vm-original-<sourceLanguage>`
- generated localized set: `vm-<language>-gen`

Legacy Influx tags:

- source reference set: `influx-original-<sourceLanguage>`
- generated localized set: `influx-<language>-gen`

Manifest examples:

- `tests/artifacts/import-manifest-vm-original-en.json`
- `tests/artifacts/import-manifest-vm-fr-gen.json`
- `tests/artifacts/import-manifest-influx-fr-gen.json`

## import-dashboards-raw.mjs

Purpose: import JSON dashboards into Grafana using the raw import endpoint.

Behavior:

- resolves datasource inputs from family-specific env UIDs
- resolves expression datasource inputs to `__expr__`
- prefixes dashboard title with `[<TAG>]`
- rewrites dashboard UID using the tag
- writes an import manifest to `tests/artifacts/import-manifest-<tag>.json`

VM example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=vm-fr-gen --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

Legacy example:

```bash
node scripts/test/import-dashboards-raw.mjs --family=influx-legacy --env=.env.local --source=dashboards/influx-legacy/translation/fr --tag=influx-fr-gen --manifest=tests/artifacts/import-manifest-influx-fr-gen.json
```

## smoke-check.mjs

Purpose: validate imported dashboards from a manifest.

Checks:

- dashboard exists
- title exists
- panel count greater than zero
- no unresolved import placeholders like `${VAR_*}` or `${DS_*}`

VM example:

```bash
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

## capture-screenshots.mjs

Purpose: capture deterministic dashboard screenshots for review.

Outputs:

- `tests/artifacts/screenshots/vm/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/vm/<tag>/mobile/*.png`
- `tests/artifacts/screenshots/influx-legacy/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/influx-legacy/<tag>/mobile/*.png`

VM example:

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
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

This avoids the usual Grafana issue where long dashboards render incompletely below the fold.

## Desktop/mobile split

- `desktop` captures only non-mobile dashboards
- `mobile` captures only the dashboard whose source file or title marks it as mobile

The detection is based on stable source-file and UID signals, not on translated dashboard titles.

## Screenshot filenames

Filenames are human-readable when possible.

Behavior:

- use a slug based on the dashboard title if it is stable enough
- fall back to UID-based slug when the title is too short or not useful
- keep family and set separation in the directory path, not in each filename

## Time range behavior

If `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` are not set, the script applies built-in stable ranges based on dashboard identity:

- All-time: `now-1y/y` to `now`
- Jahr/Year: `now-1y/y` to `now/y`
- Monat/Month: `now-1M/M` to `now/M`
- Today - Details: `now-1d/d` to `now/d`

## run-suite.mjs

Purpose: run preparation + import + smoke + optional screenshot generation for all configured sets of a family.

Behavior:

- by default runs localization preparation first:
  - `generate-localized-dashboards.mjs`
  - `apply-safe-display-translations.mjs`
- reads the active family's `languages.json`
- includes the source reference set as `<familyTagPrefix>-original-<sourceLanguage>`
- includes each generated target folder as `<familyTagPrefix>-<language>-gen`
- when `--screenshots=true`, runs `cleanup-grafana.mjs` before each set
- imports the set
- runs smoke-check
- optionally captures screenshots

VM examples:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

Legacy example:

```bash
node scripts/test/run-suite.mjs --family=influx-legacy --env=.env.local --screenshots=true --cleanup-final=true
```

Important operational detail:

- the suite cleans before each set, not after the last one by default
- use `--cleanup-final=true` to clean once more after the final set
- without `--cleanup-final=true`, the last imported set remains in the Grafana test folder

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

## Maintenance note

Update this README whenever script defaults, family handling, tags, screenshot layout, or workflow assumptions change.
