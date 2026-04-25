# Screenshots

This directory is for curated release documentation screenshots only.

Test runs, render-smoke screenshots, temporary dashboard imports, performance traces, and debugging captures belong under `tests/artifacts/` and are intentionally ignored by Git.

Rules for adding screenshots here:

- Add only screenshots that document the current released dashboard state.
- Prefer the TAB dashboard set when documenting Grafana 13 navigation.
- Update only screenshots for dashboards that visibly changed in the release.
- Avoid committing full test screenshot batches or language matrix output.
- Keep filenames stable and descriptive so diffs remain reviewable.

Current release screenshot set:

- [TAB dashboards](./tabs/README.md)
