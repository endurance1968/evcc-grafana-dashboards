# Test Scripts (Grafana)

This folder contains the script-based Grafana validation workflow used to import dashboards, run smoke checks, and create review screenshots.

Default family:

- `vm`

## Script overview

- `deploy-dashboards.mjs`: high-level deploy workflow for a single language or variant
- `import-dashboards-raw.mjs`: import via Grafana's raw dashboard import endpoint
- `smoke-check.mjs`: post-import validation
- `capture-screenshots.mjs`: browser-based screenshot capture
- `run-suite.mjs`: batch import/smoke/screenshot workflow across all configured sets
- `cleanup-grafana.mjs`: full cleanup of dashboards and library panels in the Grafana test folder
- `_lib.mjs`: shared helpers

Localization preparation scripts used before test runs:

- `../localization/generate-localized-dashboards.mjs`
- `../localization/apply-safe-display-translations.mjs`

## Required environment

Use `--env=.env.local` or `.env`.

Always required:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_VM_EVCC_UID`

Required for screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID` default: `evcc-test`
- `GRAFANA_TEST_FOLDER_TITLE` default: `EVCC Test`
- `GRAFANA_SCREENSHOT_WAIT_MS` default: `3500`
- `GRAFANA_TIME_FROM` and `GRAFANA_TIME_TO` for a global screenshot time override

## Naming convention

VM tags:

- source reference set: `vm-original-<sourceLanguage>`
- generated localized set: `vm-<language>-gen`

Manifest examples:

- `tests/artifacts/import-manifest-vm-original-en.json`
- `tests/artifacts/import-manifest-vm-fr-gen.json`

## import-dashboards-raw.mjs

Behavior:

- resolves datasource inputs from env UIDs
- resolves expression datasource inputs to `__expr__`
- prefixes dashboard title with `[<TAG>]`
- rewrites dashboard UID using the tag
- writes an import manifest to `tests/artifacts/import-manifest-<tag>.json`

Example:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=vm-fr-gen --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

## smoke-check.mjs

Checks:

- dashboard exists
- title exists
- panel count greater than zero
- no unresolved import placeholders like `${VAR_*}` or `${DS_*}`

## capture-screenshots.mjs

Outputs:

- `tests/artifacts/screenshots/vm/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/vm/<tag>/mobile/*.png`

## run-suite.mjs

Behavior:

- runs localization preparation by default
- reads the active family's `languages.json`
- includes the source reference set as `<familyTagPrefix>-original-<sourceLanguage>`
- includes each generated target folder as `<familyTagPrefix>-<language>-gen`
- when `--screenshots=true`, runs `cleanup-grafana.mjs` before each set
- imports the set
- runs smoke-check
- optionally captures screenshots

Examples:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

## cleanup-grafana.mjs

Purpose: remove all dashboards and all library panels inside the configured Grafana test folder.

Datasources are not touched.

## Deploy defaults

`deploy-dashboards.mjs` supports these defaults for VM:

- default language: `en`
- default variant: `orig`
- default source mode: `github`
- default GitHub repo: the configured local `github` remote

Supported arguments:

- `--source-mode=local|github`
- `--source=<local path or repo-relative path>`
- `--github-repo=<owner/repo>`
- `--github-ref=<branch-or-tag>`
- `--language=<code>`
- `--variant=orig|generated`

Example local deploy:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --source-mode=local --purge=true --smoke=true
```

Example GitHub-based deploy:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --purge=true --smoke=true
```
