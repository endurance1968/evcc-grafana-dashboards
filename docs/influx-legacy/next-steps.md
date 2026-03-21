# Next Steps

This file records the remaining work after the current localization and screenshot automation milestone.

It is intentionally short and should reflect the current repository state, not old intermediate steps.

## Current state

Implemented:

- source dashboards under `dashboards/influx-legacy/original/de`
- generated dashboards under `dashboards/influx-legacy/translation/<language>`
- mapping-based localization generator and audit scripts
- Grafana import, smoke-check, cleanup, and screenshot automation
- screenshot capture with panel-composition instead of naive full-page capture
- language-independent fixed time ranges for comparable screenshots
- per-language full-suite execution with cleanup before each screenshot run
- safe display-only translation patches in generated dashboards for multiple languages
- screenshot filename slugging now preserves Latin words with accents more cleanly
- latest review documented in `docs/influx-legacy/localization-review-2026-03-21.md`

## Remaining technical work

### 1. Reduce manual display-only patching

Current issue:

- after mapping-based generation, some visible labels still require safe manual follow-up in generated dashboards

Goal:

- move more of those safe cases into a reproducible scripted layer
- ideally cover more display-only override fields automatically

### 2. Refactor original dashboards for localization-friendly internals

Current issue:

- many visible labels are still coupled to internal dashboard logic through `alias`, `refId`, `matcher.options`, regexes, and formulas

Goal:

- separate internal technical identifiers from visible labels
- keep stable internal ids language-neutral
- localize only display properties

This is the main long-term maintainability task.

### 3. Review all remaining untranslated visible strings

Goal:

- inspect the latest screenshot sets under `tests/artifacts/screenshots`
- document any remaining visible source-language text
- classify each case as one of:
  - safe display-only fix
  - source dashboard refactor needed
  - data-driven text from InfluxDB or tags

Status: partially completed.

- latest review note: `docs/influx-legacy/localization-review-2026-03-21.md`
- the dominant remaining category is now `source dashboard refactor needed`

### 4. Consolidate non-Latin language handling

Goal:

- ensure all Hindi and Chinese display-only updates use a UTF-8-safe path
- keep documentation explicit about encoding risks during manual maintenance

### 5. Optional final cleanup improvement

Status: completed (2026-03-16).

- `run-suite.mjs` now supports `--cleanup-final=true` to run `cleanup-grafana.mjs` once after the final set.

## Maintainer reading order

If you are new to this workflow, start with:

1. `docs/influx-legacy/localization-maintainer-workflow.md`
2. `docs/influx-legacy/grafana-localization-testing.md`
3. `scripts/test/README.md`
4. any remaining language-specific review notes that are still actively maintained

