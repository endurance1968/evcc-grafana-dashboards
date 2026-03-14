# Grafana Localization Test Workflow

This setup validates localized dashboards against a real Grafana test instance.

## Prerequisites

- Node.js 20+ (tested with Node 24)
- A reachable Grafana test instance with API access
- Grafana service account token with dashboard write access in the target org
- Existing Grafana datasources for EVCC + aggregations, with known UIDs
- For screenshot automation: Chromium via Playwright (`npm i -D playwright` then `npx playwright install chromium`)

## 1) Configure environment

Copy `.env.example` to `.env` and fill values:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_EVCC_INFLUXDB_UID`
- `GRAFANA_DS_EVCC_AGGREGRATIONS_UID`
- optional screenshot login: `GRAFANA_USERNAME` + `GRAFANA_PASSWORD`

## 2) Generate localized output

```bash
node scripts/generate-localized-dashboards.mjs
```

## 2b) Audit translation coverage (recommended)

```bash
node scripts/audit-localization.mjs
```

Review `dashboards/localization/missing-<source>_to_<target>.exact.json` and update the matching `dashboards/localization/<source>_to_<target>.json` file before importing dashboards.
## 3) Import one set and smoke-check

Example for a target language set (example: fr):

```bash
node scripts/test/import-dashboards-raw.mjs --source=dashboards/translation/fr --tag=fr
node scripts/test/smoke-check.mjs --manifest=tests/artifacts/import-manifest-fr.json
```

## 4) Capture screenshots (optional)

```bash
node scripts/test/capture-screenshots.mjs --manifest=tests/artifacts/import-manifest-fr.json
```

Outputs go to:

- `tests/artifacts/screenshots/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/<tag>/mobile/*.png`

## 5) Full suite for source + all configured target languages

Without screenshots:

```bash
node scripts/test/run-suite.mjs
```

With screenshots:

```bash
node scripts/test/run-suite.mjs --screenshots=true
```

## Notes

- The importer rewrites dashboard UID per set tag (e.g. `fr-...`) to prevent collisions.
- `refId` and other technical references are intentionally not translated.
- This is a smoke/layout test harness. Data-quality validation still depends on the underlying real dataset.

## 6) Scripted language deployment

Deploy a language set with automatic import + smoke-check:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=de --purge=true
```

Examples:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=en --purge=true
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=fr --purge=true
node scripts/test/deploy-dashboards.mjs --env=.env.local --language=nl --purge=true
```

- `--language=<code>` selects source (`--variant=orig` uses `dashboards/original/<code>`, `--variant=generated` uses `dashboards/translation/<code>`)
- dashboards are tagged as `<language>-orig` (for example `de-orig`, `fr-orig`)
- `--purge=true` removes dashboards of that language tag first and then orphaned library panels in the test folder

## 7) Full Grafana cleanup (test folder)

Delete all dashboards and library panels in the configured test folder (datasources stay untouched):

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```