# Localization Workflow

- `languages.json`: defines source + target languages
- `../original/<sourceLanguage>`: source of truth (hand-edited dashboards)
- `../translation/<language>`: generated output per configured target language
- `<source>_to_<target>.json`: translation mapping per language pair

Generate localized dashboard files for all configured target languages:

```bash
node scripts/localization/generate-localized-dashboards.mjs --family=influx-legacy
```

Apply safe display-only translations on generated dashboard files:

```bash
node scripts/localization/apply-safe-display-translations.mjs --family=influx-legacy
```

Audit missing source-to-target mappings for all configured targets:

```bash
node scripts/localization/audit-localization.mjs --family=influx-legacy
```

Audit one specific target language:

```bash
node scripts/localization/audit-localization.mjs --family=influx-legacy --target=en
```

The audit writes `missing-<source>_to_<target>.exact.json` with candidate keys that still need translations.

For the full end-to-end Grafana validation workflow, see `../../docs/influx-legacy/grafana-localization-testing.md`.


