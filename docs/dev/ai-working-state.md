# AI Working State

Last updated: 2026-07-04

This file is an internal handoff note for Codex continuation work. It is not end-user documentation.

## Non-negotiable Rules

- Ole's production Grafana and production VictoriaMetrics are read-only for Codex. Do not deploy, write, delete, import, roll up, or mutate production. Provide commands for Ole to run manually when production changes are needed.
- Use the local Forgejo remote `origin` by default. Do not push to GitHub unless Ole explicitly asks.
- Edit dashboard sources only in `dashboards/original/`. Regenerate `dashboards/translation/` from sources; do not hand-edit generated dashboards.
- Keep German default documentation and English documentation in sync.
- Complex Grafana/dashboard changes must be visually verified in the disposable Docker test environment before being reported as ready.
- For full live-VM test imports, use Docker-network-local month-by-month export/import with `max_rows_per_line=1000`; avoid streaming a complete VM export through the Windows host port.
- Preferred install/tool path on Linux hosts is `/opt/evcc-vm-tools`, not `/opt/evcc-vm-migration`.

## Current Repository State

Repository: `D:\AI-Workspaces\evcc-grafana-dashboards`

There are uncommitted local changes related to:

- Optional VRM energy-flow import helper and tests.
- VRM storage panels/values for month, year, and all-time dashboards.
- Generated localized dashboard JSON updates.
- README and documentation updates for the VRM import work.
- Local check/test script updates.

Do not commit these changes until the Docker test path has been re-run and Ole has reviewed the German Grafana dashboards.

## Forgejo Tracking

Existing relevant open issues:

- #19 `Audit-Collector: Batterie-Netzladung nur bei tatsächlicher Ladeleistung zählen`
- #20 `Optionalen VRM-Energieflussimport fuer Speicherwirkungsgrad ergaenzen`
- #21 `Rollup: Performance-Timings auswerten und Backfill/Scheduler optimieren`
- #22 `Rollup: Datenqualitäts- und Scheduler-Schutz verbessern`
- Roadmap issues #8-#14 for future Grafana 13/visualization ideas.

Issues #19 and #20 contain `Arbeitsstand 2026-07-04` comments with the latest continuation notes.

## Immediate Continuation Plan

1. Cleanly rebuild the disposable Docker VictoriaMetrics/Grafana test environment.
2. Import live VM data read-only into the Docker test VM using the known month-by-month internal Docker-network path.
3. Import VRM daily energy-flow data from 2025-01-01 into the Docker test VM only.
4. Deploy German dashboards to the Docker test Grafana only.
5. Visually verify month, year, and all-time storage panels:
   - EVCC and VRM storage values must not be mixed in the same semantic panel unless intentionally labeled.
   - Units must be scaled correctly (Wh/kWh/MWh), with no raw Wh values shown as MWh.
   - All-time VRM values should be integrated into the storage panel layout as Ole requested, without leaving excessive height or misalignment.
   - Month and year VRM storage flow panels must show data where VRM data exists.
6. Run the smallest relevant checks first, then broader tests if dashboard JSON or helper behavior changed.
7. Ask Ole for manual German GUI review before commit/push.

## Known Endpoints And Constraints

Read-only production references:

- Production VictoriaMetrics: `http://192.168.1.160:8428`
- Production EVCC: `http://192.168.1.197:7070`
- Production Grafana: `http://192.168.1.189:3000`

Typical disposable test setup, verify before use:

- Test Grafana often runs at `http://127.0.0.1:13000`
- Test VictoriaMetrics often uses host port `18440`
- Typical Grafana test credentials have been `admin` / `admin`, but verify the current container configuration.

## Release Notes Rules

For the next release, keep release notes concise and current-release-only:

- New Features
- Improvements
- Bug Fixes
- Breaking Changes / required user actions

Include relevant commit hashes, but do not list internal Forgejo issue references in GitHub-facing release notes. Do not repeat old release content or general documentation.