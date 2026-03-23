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
- initial VM rollup CLI under `scripts/evcc-vm-rollup.py`
- operator guide under `docs/victoriametrics-aggregation-guide.md`
- test-only grid import price and cost rollups in `test_evcc_*`
- parallel clamp-based test rollups in `test_evcc_clamp_*` with a separate month review dashboard
- VM month review dashboard with working energy, battery, metric, price, and cost panels

## Remaining technical work

### 0. VM rollup baseline for long-range dashboards

Current issue:

- the repository now has a validated VM rollup direction, and a reviewable VM month test dashboard exists; year and all-time still need to be finalized on top of it

Goal:

- use the accepted VM daily-rollup baseline for long-range dashboards
- avoid copying the Influx legacy monthly model unless measured VM performance later requires it

Primary references:

- `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`
- `docs/victoriametrics-rollup-design.md`

Additional current concerns:

- the repository currently uses `test_evcc_*` and `test_evcc_clamp_*` for reviewed daily rollup families; production `evcc_*` rollups are still outstanding
- VM-side `host` labels were cleaned up, but ingest hygiene still needs to be watched so those labels do not reappear later
- if relevant historical host-only samples turn out to matter, a targeted reimport strategy may still be needed

### 0a. Finish VM month review pass

Current issue:

- the VM month dashboard is now close to the legacy reference, and a parallel clamp-based comparison dashboard now exists for direct review before production decisions

Goal:

- close the remaining visual and semantic deltas in the month dashboard
- then use the month dashboard as the template for VM year and all-time work

Primary references:

- `dashboards/vm-month-test/original/en/VM_ EVCC_ Monat - Rollup Test.json`
- `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`

### 0b. Validate and tune VM price and cost rollups

Current issue:

- import-side daily price and cost rollups now exist in `test_evcc_*`, but they still need tighter validation against Influx legacy and Tibber reality
- the remaining drift is mainly in imported grid energy, not in the tariff series itself
- export credit rollups are still not finalized

Goal:

- keep the current test-only import price/cost rollups as the baseline
- tune and validate them before any promotion to `evcc_*`
- then add export credit rollups on the same validated quarter-hour path

Primary references:

- `docs/victoriametrics-price-rollup-plan.md`
- `docs/victoriametrics-rollup-design.md`

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

1. `docs/victoriametrics-dashboard-rollup-handoff-2026-03-22.md`
2. `docs/victoriametrics-rollup-design.md`
3. `docs/victoriametrics-aggregation-guide.md`
4. `docs/vm-thread-restart-handoff-2026-03-21.md`
5. `docs/localization-maintainer-workflow.md`
6. `docs/grafana-localization-testing.md`
7. `scripts/test/README.md`
8. `docs/localization-review-2026-03-21.md`
