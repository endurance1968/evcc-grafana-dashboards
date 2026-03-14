# Maintainer Workflow for Localization (No AI Required)

This workflow is designed so dashboard translations can be created and maintained with only Git + Node.js.

## Scope

- Language config: `dashboards/localization/languages.json`
- Source of truth: `dashboards/original/<sourceLanguage>`
- Per-language mapping: `dashboards/localization/<source>_to_<target>.json`
- Generated outputs: `dashboards/translation/<language>` for each configured target language

## Prerequisites

- Node.js 20+ available locally
- Ability to run scripts from repository root

## Configure languages

Edit `dashboards/localization/languages.json`:

```json
{
  "sourceLanguage": "de",
  "targetLanguages": ["de", "en", "fr"]
}
```

For each target language that differs from source, create or maintain:

- `dashboards/localization/de_to_en.json`
- `dashboards/localization/de_to_fr.json`

## Update workflow

1. Edit source dashboards in `dashboards/original/<sourceLanguage>`.
2. Run generation for all configured targets:
   ```bash
   node scripts/generate-localized-dashboards.mjs
   ```
3. Run localization audit for all targets:
   ```bash
   node scripts/audit-localization.mjs
   ```
4. Review generated suggestion files:
   - `dashboards/localization/missing-<source>_to_<target>.exact.json`
5. Copy relevant keys into `dashboards/localization/<source>_to_<target>.json` under `exact` and fill translations.
6. Re-run generation + audit until candidate lists are acceptable.
7. Validate in Grafana test instance (import, smoke check, screenshots), see `docs/grafana-localization-testing.md`.

## Mapping rules

- Prefer `exact` for full UI labels and longer texts.
- Use `contains` only for stable token replacements used in many places.
- Keep technical IDs and references unchanged (`refId`, query identifiers, datasource internals).
- `name` fields are translated only when prefixed with `EVCC:`.

## Review checklist

- No accidental translation of technical internals
- No broken panel titles or legend labels
- No untranslated source-language text in critical UI paths
- All configured target folders regenerated in the same change

## Recommended commit sequence

1. `feat: update source dashboards`
2. `chore: extend localization mappings`
3. `chore: regenerate localized dashboards`
4. `test: run Grafana localization smoke checks`
