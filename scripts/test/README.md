# Test Scripts (Grafana)

This folder contains the script-based Grafana validation workflow used to import dashboards, run smoke checks, and create review screenshots.

Default family:

- `vm`

## Script overview

- `deploy-dashboards.mjs`: high-level deploy workflow for a single language or variant
- `import-dashboards-raw.mjs`: import via Grafana's raw dashboard import endpoint
- `smoke-check.mjs`: post-import validation
- `dashboard-semantic-check.mjs`: static semantic checks for dashboard time ranges, critical panels, bar chart axes, and known Grafana error regressions
- `render-smoke-check.mjs`: browser-based rendered dashboard and critical solo-panel smoke checks
- `rollup-path-check.mjs`: complete deterministic rollup path orchestrator (`npm run test:rollup-path`)
- `rollup-e2e.py`: optional disposable VictoriaMetrics rollup read/write/replace end-to-end test
- `capture-screenshots.mjs`: browser-based screenshot capture
- `run-suite.mjs`: batch import/smoke/screenshot workflow across all configured sets
- `local-checks.mjs`: portable deterministic check runner used by `npm test` and CI
- `cross-platform-audit.mjs`: guard against Windows-only npm entrypoints and unsafe child-process shell usage
- `powershell-deployer-compat.mjs`: Windows PowerShell 5.1 deployer regression check for JSON parsing, datasource replacement, and single-item-array preservation
- `local-checks.ps1`: optional Windows compatibility wrapper; not used by the portable npm entrypoints
- `cleanup-grafana.mjs`: full cleanup of dashboards and library panels in the Grafana test folder
- `_lib.mjs`: shared helpers

Localization preparation scripts used before test runs:

- `../localization/generate-localized-dashboards.mjs`
- `../localization/apply-safe-display-translations.mjs`

## Cross-platform test entrypoints

Use these commands on Windows, Linux, and Forgejo runners:

```bash
npm test
npm run test:ci
npm run test:cross-platform
npm run test:powershell-compat
npm run test:rollup-path
```

`npm test` and `npm run test:ci` both use the Node-based runner. They do not require PowerShell as an entrypoint, but on Windows they now execute an internal compatibility check against `powershell.exe` so the native deployer stays compatible with Windows PowerShell 5.1. The PowerShell wrapper remains available only for users who intentionally want a Windows-native entrypoint.

Required local tooling for the full validation surface:

- Node.js 22 or newer for the script-based test runners.
- Python 3.12 or newer, or `PYTHON=/path/to/python`, for helper compile checks and rollup tests.
- Docker with local port publishing for query readback, render E2E, and rollup E2E.
- Playwright Chromium browser dependencies for render smoke checks; `npx playwright install --with-deps chromium` is used in Linux CI.
- Bash or Git Bash for deploy shell syntax checks. On Windows this check is skipped if Bash is not available.

## Required environment

Use `--env=.env.local` or `.env`.

Always required:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_VM_EVCC_UID`

Required for render smoke checks and screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID` default: `evcc-test`
- `GRAFANA_TEST_FOLDER_TITLE` default: `EVCC Test`
- `GRAFANA_SCREENSHOT_WAIT_MS` default: `3500`
- `GRAFANA_RENDER_SMOKE_WAIT_MS` default: `GRAFANA_SCREENSHOT_WAIT_MS` or `3500`
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

## render-smoke-check.mjs

Checks:

- imported dashboard page renders at least one panel grid item
- known Grafana error texts are not visible
- critical panels are opened via `/d-solo/...&panelId=...`
- critical panels do not render `No data` unless `--fail-no-data=false` is passed

## rollup-e2e.py

Purpose: validate the real rollup write path against a disposable VictoriaMetrics instance.

Checks:

- imports a tiny raw EVCC fixture into an isolated VM
- runs `evcc-vm-rollup.py backfill --replace-range --write` twice
- verifies expected daily PV, home, grid import, and loadpoint rollup values
- verifies the repeated replace run does not leave duplicate daily samples

Docker mode starts and stops a temporary VM container:

```bash
python scripts/test/rollup-e2e.py --docker
```

External disposable VM mode is deliberately guarded:

```bash
python scripts/test/rollup-e2e.py --base-url=http://127.0.0.1:8428 --confirm-disposable
```

Do not point this at production. The test writes raw fixture data and deletes all `e2e_evcc_*` rollup series plus its own `e2e_fixture` raw series.

## rollup-path-check.mjs

Purpose: run the complete deterministic rollup validation path from one command after rollup, query, or dashboard changes.

```bash
npm run test:rollup-path
```

The command runs static/unit/dashboard checks, external Tibber/Influx/VRM cache validation, MetricsQL query readback against disposable VictoriaMetrics, Grafana render E2E with fixture data, and the disposable rollup replace E2E. It intentionally takes longer than `npm run test:ci` because it covers the full rollup-to-dashboard path.

Useful options:

- `-- --skip-render` skips only the browser render E2E when you need a faster local precheck.
- `-- --strict-energy` requires private Tibber/Influx/VRM cache snapshots instead of treating missing caches as non-blocking skips.
- `-- --vm-base-url http://127.0.0.1:8428` adds live VM rollup comparison to the energy validation step.

## run-suite.mjs

Behavior:

- runs localization preparation by default
- reads the active family's `languages.json`
- includes the source reference set as `<familyTagPrefix>-original-<sourceLanguage>`
- includes each generated target folder as `<familyTagPrefix>-<language>-gen`
- when `--screenshots=true`, runs `cleanup-grafana.mjs` before each set
- by default, runs `cleanup-grafana.mjs` before each set even without screenshots so library panel UIDs cannot collide across languages; pass `--cleanup-between=false` only when you intentionally want all imported sets to remain side by side
- imports the set
- runs smoke-check
- optionally runs render-smoke-check with `--render-smoke=true`
- optionally captures screenshots

Examples:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
node scripts/test/run-suite.mjs --env=.env.local --render-smoke=true
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
