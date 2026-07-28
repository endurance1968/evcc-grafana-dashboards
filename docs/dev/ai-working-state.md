# AI Working State

Last updated: 2026-07-28

This file is an internal handoff note for Codex continuation work. It is not end-user documentation.

## Non-negotiable Rules

- Ole's production Grafana and production VictoriaMetrics are read-only for Codex. Do not deploy, write, delete, import, roll up, or mutate production. Provide commands for Ole to run manually when production changes are needed.
- Use the local Forgejo remote `origin` by default. Do not push to GitHub unless Ole explicitly asks.
- Edit dashboard sources only in `dashboards/original/`. Regenerate `dashboards/translation/` from sources; do not hand-edit generated dashboards.
- Keep German default documentation and English documentation in sync.
- Complex Grafana/dashboard changes must be visually verified in the disposable Docker test environment before being reported as ready.
- For full live-VM test imports, use Docker-network-local month-by-month export/import with `max_rows_per_line=1000`; avoid streaming a complete VM export through the Windows host port.
- Preferred install/tool path on Linux hosts is `/opt/evcc-vm-tools`, not `/opt/evcc-vm-migration`.
- Do not mark current release screenshots final before Ole has completed the manual GUI review.

## Current Repository State

Repository: `D:\AI-Workspaces\evcc-grafana-dashboards`

The July release candidate includes Consumer dashboards and rollups, Consumer/EXT migration mapping for both rollups and Today raw panels, Consumer title aliases, Today finance fixes, VRM energy-flow validation, scheduler/data-quality guards, deployer updates, and generated localizations.

Issues #20, #21, and #22 were technically completed on 2026-07-28. Their Forgejo closure comments must reference the final commit and the evidence below.

## Final Technical Evidence

- Fresh isolated Grafana 13.0.1 baseline: `http://127.0.0.1:13001`, login `admin` / `admin`.
- Fresh isolated Grafana 13.1.0 compatibility check: `http://127.0.0.1:13000`, login `admin` / `admin`; Grafana 13.1.0 is not required.
- Fresh isolated VictoriaMetrics 1.139.0: `http://127.0.0.1:18440`.
- Exactly six current German dashboards are deployed with the production filter overrides.
- Full livecopy rollup: 573 completed days, 36,625 samples, 1,388 series, 210.606 seconds, 1,264 MB peak Python memory.
- Data quality: overall `OK`, zero duplicate label/day combinations, zero `host` labels, zero `db` labels, two ignored counter resets, zero power spikes, 9,910 missing energy buckets.
- Consumer titles: 14 canonical long-range titles; `Trocker` is merged into `Trockner` before daily integration.
- VRM parity: 383 days, 2,298 samples, six metrics, zero missing/extra/duplicate days. June 2026 efficiency 85.260%, reference delta 0.040 percentage points.
- Mandatory release path: 190 Python tests, 76 dashboard JSON files, 382 live MetricsQL queries, 60 critical rendered panels plus 17 historical Today Details panels, repeated replace-range idempotence; result `OK` in 520.4 seconds on the final dashboard sources.
- EXT-to-Consumer raw migration: both Grafana 13.0.1 and 13.1.0 passed current, pre-cutover (2026-07-25), and cutover-day (2026-07-27) livecopy renders. The four Home panels stayed populated; the explicit mapping returned 14 historical and 14 current titles without identical duplicates or filtered parent/sum meters.
- The Month battery layout was visually checked at 1280 pixels after deployment; values and daily axis labels no longer overlap.

## Remaining Release Gate

- Ole manually reviews the disposable German Grafana dashboards.
- Curated screenshots are refreshed only after that approval.
- Issue #30 remains the overall release gate.
- Issue #35 remains excluded from this release.

## Known Endpoints And Constraints

Read-only production references:

- Production VictoriaMetrics: `http://192.168.1.160:8428`
- Production EVCC: `http://192.168.1.197:7070`
- Production Grafana: `http://192.168.1.189:3000`

Disposable test setup currently retained for review:

- Test Grafana 13.0.1: `http://127.0.0.1:13001`
- Test Grafana 13.1.0: `http://127.0.0.1:13000`
- Test VictoriaMetrics: `http://127.0.0.1:18440`
- Test Grafana credentials: `admin` / `admin`

## Release Notes Rules

For the next release, keep release notes concise and current-release-only:

- New Features
- Improvements
- Bug Fixes
- Breaking Changes / required user actions

Include relevant commit hashes, but do not list internal Forgejo issue references in GitHub-facing release notes. Do not repeat old release content or general documentation.
