# TAB Dashboard Screenshots

This directory documents the Grafana 13 TAB dashboard series.

Expected screenshots for a release that changes TAB dashboard layout or user-facing behavior:

- `all-time.png`
- `year.png`
- `month.png`
- `today-details.png`

`Today` and `Today - Mobile` are shared with the default dashboard set and only need screenshots here if TAB-set deployment changes their visible behavior.

Update policy:

- Regenerate screenshots from the deployed `DASHBOARD_SET=tabs` dashboard set.
- Delete old files for changed dashboards before adding replacements.
- Do not commit screenshots for unchanged dashboards just because a test run recreated them.
- Keep raw render/test screenshots in `tests/artifacts/`; copy only the selected release screenshots into this directory.
