# TAB Dashboard Screenshots

This directory documents the recommended Grafana 13 TAB dashboard series for release notes and end-user documentation.

## Current Release Screenshots

The first public VictoriaMetrics release includes these curated screenshots:

- [all-time.png](./all-time.png)
- [year.png](./year.png)
- [month.png](./month.png)
- [today-details.png](./today-details.png)

`Today` and `Today - Mobile` are shared with the default dashboard set and only need screenshots here if TAB-set deployment changes their visible behavior.

## Capture Source

Current screenshots were captured on 2026-05-30 from a Grafana 13.0.1 test instance using:

```env
DASHBOARD_SET=tabs
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

The datasource pointed read-only at a production-style VictoriaMetrics instance with complete raw data and `evcc_*` rollups. Raw render output stayed under `tests/artifacts/`; only the four curated PNG files are committed here.

Recommended maintainer command after importing the TAB set into a test Grafana:

```bash
DASHBOARD_SET=tabs node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

## Update Policy

- Delete old screenshot files first for dashboards that changed.
- Do not replace unchanged screenshots just because a test run recreated them.
- Keep filenames stable and descriptive.
- Prefer screenshots with complete raw data and `evcc_*` rollups so empty panels do not become release documentation.