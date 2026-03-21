# Next Steps

This file records the remaining work for the default VictoriaMetrics localization flow.

## Current state

Implemented:

- VM source dashboards under `dashboards/original/en`
- generated dashboards under `dashboards/translation/<language>`
- mapping-based localization for `de`, `fr`, `nl`, `es`, `it`, `zh`, `hi`
- localization audit with zero current missing candidates for the scripted key set
- Grafana import, smoke-check, cleanup, and screenshot automation for the default VM family
- family-separated screenshot output under `tests/artifacts/screenshots/vm`

## Remaining technical work

### 1. Reduce mixed-language source internals

Current issue:

- the imported VM upstream snapshot still contains German source strings in internal wiring and panel metadata

Goal:

- separate internal identifiers from user-visible labels
- keep stable internals language-neutral
- localize only display properties

### 2. Extend the VM source set

Current issue:

- upstream currently provides only three VM dashboards

Goal:

- add more VM-native dashboards once upstream provides them or the repo grows them locally in a maintainable way

### 3. Review screenshots after each mapping pass

Goal:

- inspect the latest screenshot sets under `tests/artifacts/screenshots/vm`
- document visible residual German or English text
- classify each case as:
  - safe display-only fix
  - source dashboard refactor needed
  - data-driven text from tags or measurements

### 4. Keep family separation strict

Goal:

- maintain VM as the short default path
- keep Influx only under `dashboards/influx-legacy`, `docs/influx-legacy`, and `scripts/influx-legacy`
- avoid cross-family assumptions in shared scripts

## Maintainer reading order

If you are new to the current default flow, start with:

1. `docs/vm-thread-restart-handoff-2026-03-21.md`
2. `docs/localization-maintainer-workflow.md`
3. `docs/grafana-localization-testing.md`
4. `scripts/test/README.md`
5. `docs/localization-review-2026-03-21.md`
