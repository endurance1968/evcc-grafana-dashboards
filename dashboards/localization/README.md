# Localization Workflow

- `languages.json`: defines source + target languages for the default VM flow
- `../original/<sourceLanguage>`: source of truth for VM dashboards
- `../translation/<language>`: generated output per configured target language
- `<source>_to_<target>.json`: translation mapping per language pair
- `missing-<source>_to_<target>.exact.json`: audit report with open candidate texts

Important: the scripts do not perform the actual language translation. A human translator or AI must provide the final target-language text in `en_to_<language>.json`. The scripts only find missing mapping entries, optionally copy them as placeholders, and render generated dashboards from the mappings.

## Standard Flow

Remove mapping entries that no longer exist in the current source dashboards:

```bash
node scripts/localization/prune-mappings-to-source.mjs
```

This is a dry-run by default. If the output looks correct, write the pruned mappings explicitly:

```bash
node scripts/localization/prune-mappings-to-source.mjs --write
```

Audit missing source-to-target mappings for all configured targets:

```bash
node scripts/localization/audit-localization.mjs
```

Audit one specific target language:

```bash
node scripts/localization/audit-localization.mjs --target=fr
```

The audit writes `missing-<source>_to_<target>.exact.json` with candidate keys that still need mapping entries. `exactSources` lists the source dashboard file names that produced each candidate.

Manually translate relevant candidates into the real mapping file, for example `en_to_fr.json`. If all missing candidates should be accepted as intentional placeholders first, adopt them into the mappings:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all
```

This is a dry-run by default. If the output looks correct, write the placeholder entries explicitly:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all --write
```

`adopt-missing-into-mappings.mjs` writes `source -> source` entries only when `--write` is set. It is not a translation step; replace those values with real target-language text before expecting localized output.

Generate localized dashboard files for all configured target languages:

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

Apply safe display-only translations on generated dashboard files:

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

For the full end-to-end Grafana validation workflow, see `../../docs/design/grafana-localization-testing.md`.
