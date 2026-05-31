# TAB Dashboard Screenshots

This directory documents the recommended Grafana 13 TAB dashboard series for release notes and end-user documentation.

## Current Release Screenshots

The first public VictoriaMetrics release includes tab-aware screenshots for every active tab in the German generated TAB dashboards. These screenshots intentionally show the Grafana tab bar so users can recognize the navigation state shown in the documentation.

All-time dashboard:

- [all-time-energie.png](./all-time-energie.png)
- [all-time-anlagengesundheit.png](./all-time-anlagengesundheit.png)
- [all-time-finanzen.png](./all-time-finanzen.png)

Year dashboard:

- [year-pv.png](./year-pv.png)
- [year-haus.png](./year-haus.png)
- [year-speicher.png](./year-speicher.png)
- [year-verbraucher.png](./year-verbraucher.png)
- [year-fahrzeuge.png](./year-fahrzeuge.png)

Month dashboard:

- [month-pv.png](./month-pv.png)
- [month-haus.png](./month-haus.png)
- [month-verbraucher.png](./month-verbraucher.png)
- [month-speicher.png](./month-speicher.png)

Today - Details dashboard:

- [today-details-pv.png](./today-details-pv.png)
- [today-details-verbrauch.png](./today-details-verbrauch.png)
- [today-details-tarife.png](./today-details-tarife.png)
- [today-details-netz.png](./today-details-netz.png)
- [today-details-ladepunkte.png](./today-details-ladepunkte.png)

`Today` and `Today - Mobile` are shared dashboard files in the supported TAB deploy list and only need screenshots here if their visible behavior changes.

## Capture Source

Current screenshots were captured on 2026-05-30 from a Grafana 13.0.1 test instance using:

```env
DASHBOARD_LANGUAGE=de
DASHBOARD_VARIANT=gen
```

The datasource pointed read-only at a production-style VictoriaMetrics instance with complete raw data and `evcc_*` rollups. Raw render output stayed under `tests/artifacts/`; only the curated tab screenshots are committed here.

Recommended maintainer command after importing the TAB dashboards into a test Grafana:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

## Update Policy

- Delete old screenshot files first for dashboards that changed.
- Do not replace unchanged screenshots just because a test run recreated them.
- Keep filenames stable and descriptive.
- For TAB dashboards, capture each active tab with the Grafana tab bar visible.
- Prefer screenshots with complete raw data and `evcc_*` rollups so empty panels do not become release documentation.
