# TAB Dashboard Screenshots

This directory documents the recommended Grafana 13 TAB dashboard series for release notes and end-user documentation.

## Required Release Screenshots

For a release that changes TAB layout or user-facing behavior, capture and curate:

- `all-time.png`
- `year.png`
- `month.png`
- `today-details.png`

`Today` and `Today - Mobile` are shared with the default dashboard set and only need screenshots here if TAB-set deployment changes their visible behavior.

## Capture Source

Capture from a deployed Grafana instance using:

```env
DASHBOARD_SET=tabs
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

Recommended maintainer command after importing the TAB set into a test Grafana:

```bash
DASHBOARD_SET=tabs node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

Keep raw render/test output in `tests/artifacts/`. Copy only selected release screenshots into this directory.

## Update Policy

- Delete old screenshot files first for dashboards that changed.
- Do not replace unchanged screenshots just because a test run recreated them.
- Keep filenames stable and descriptive.
- Prefer screenshots with complete raw data and `evcc_*` rollups so empty panels do not become release documentation.

## Current State

No curated TAB screenshots are committed yet. The first public release should add the four required files above after a final end-to-end deployment check.