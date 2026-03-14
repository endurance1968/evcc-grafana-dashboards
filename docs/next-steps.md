# Next Steps (Localization Milestone)

## Repo policy (important)

- `origin` = Forgejo (working remote, push allowed during implementation)
- `github` = GitHub fork (push only when milestone is complete)
- `upstream` = original project `ha-puzzles/evcc-grafana-dashboards`

Current rule: work locally + push to Forgejo only until milestone "Dashboards translated" is reached.

## Current branch

- `feat/en-localization-test`

## What was completed today

1. Remote setup and sync baseline
- Local repo initialized in `D:\AI-Workspaces\evcc-grafana-dashboards`
- `upstream`, `origin`, `github` configured
- `main` aligned to `upstream/main`
- `origin/main` force-with-lease aligned to upstream history
- `github/main` was also aligned once, but from now on no more GitHub pushes until milestone complete

2. Localization structure
- Source dashboards moved from `dashboards/dashboards` to `dashboards/original/de`
- Generated output folders introduced:
  - `dashboards/translation/de`
  - `dashboards/translation/en`
- Localization mapping file created:
  - `dashboards/localization/de_to_en.json`
- Generator created:
  - `scripts/generate-localized-dashboards.mjs`
- `dashboards/README.md` updated with localization workflow section

3. Translation quality improvements
- EN mapping extended significantly for visible UI texts
- Safe translation logic for `name` keys added only for `EVCC:` prefixed names
- Internal references (`refId`, internal options) intentionally kept unchanged
- Examples fixed:
  - `EVCC: Energien aufsummiert über die Zeit` -> `EVCC: Cumulative energy over time`
  - `Hausspeicherkapazität / Wh` -> `Home battery capacity / Wh`
  - `EVCC: Kennzahlen Gauges` -> `EVCC: Metric gauges`
  - `EVCC: Speicher Effizenz` -> `EVCC: Battery efficiency`

4. Grafana test automation scaffold
- Test scripts added:
  - `scripts/test/_lib.mjs`
  - `scripts/test/import-dashboards-raw.mjs`
  - `scripts/test/smoke-check.mjs`
  - `scripts/test/capture-screenshots.mjs`
  - `scripts/test/run-suite.mjs`
- Docs added:
  - `docs/grafana-localization-testing.md`
- Env template added:
  - `.env.example`
- `.gitignore` extended for `.env` and test artifacts

## Next session start plan

1. Generate dashboards fresh:
- `node scripts/generate-localized-dashboards.mjs`

2. Run on Grafana test instance (after `.env` setup):
- `node scripts/test/run-suite.mjs --screenshots=true`

3. Fix remaining EN text edge cases from screenshot/API review.

4. Once milestone "Dashboards translated" is complete:
- then push branch to `github`
- create PR to `upstream`
