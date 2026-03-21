# Localization Review 2026-03-21

This note records the current review state after a full Grafana import, smoke-check, and screenshot run across:

- `original-de`
- `de-gen`
- `en-gen`
- `fr-gen`
- `nl-gen`
- `es-gen`
- `it-gen`
- `zh-gen`
- `hi-gen`

The goal is to separate:

- safe display-only translation work
- source-dashboard refactors that are required before more strings can be localized safely
- site-specific or data-driven labels that should not be translated in shared mappings

## Safe display-only fixes applied in this round

Updated mapping-driven display strings:

- English: added a clean translation for `EVCC: Energieverteilung über Zeit`
- French: corrected visible library-panel names such as `Énergie`, `Coûts`, and `Bilan de puissance`
- Spanish: replaced weak panel names like `calibres métricos` and `equilibrio de poder`
- Italian: replaced weak panel names like `calibri metrici` and `equilibrio di potere`
- Chinese: replaced awkward panel names like `公制仪表` and `关键人物历史`

Screenshot export quality improvement:

- filename slugging now strips Latin diacritics before generating slugs
- this turns names like `Année`, `Año`, and `Détails` into readable filenames instead of degraded forms like `ann-e` or `a-o`
- non-Latin titles still fall back to UID-based names when needed

## Source refactor still required

These strings still appear in screenshots because they are coupled to dashboard internals such as:

- `alias`
- `refId`
- `matcher.options`
- expressions that reference those names

Representative examples are in the generated dashboards:

- [EVCC_ Today.json](D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/translation/en/EVCC_%20Today.json)
- [EVCC_ Today.json](D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/translation/fr/EVCC_%20Today.json)
- [EVCC_ Today (Mobile).json](D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/translation/es/EVCC_%20Today%20(Mobile).json)
- [EVCC_ Today.json](D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/translation/zh/EVCC_%20Today.json)
- [EVCC_ Today (Mobile).json](D:/AI-Workspaces/evcc-grafana-dashboards/dashboards/translation/hi/EVCC_%20Today%20(Mobile).json)

Recurring coupled strings:

- `Haus`
- `Netz`
- `Speicher`
- `Netzbezug`
- `Speicher laden`
- `Speicher entladen`
- `energieHaus`

These are not just labels. They are reused as internal wiring inputs, so they should not be mass-translated in generated JSON.

Required long-term fix in source dashboards:

- keep stable language-neutral internal ids
- move localized text into display-only properties
- avoid using visible labels as matcher keys, alias keys, regex targets, or formula inputs

## Site-specific or data-driven labels

The following visible names appear to come from the test data or installation-specific tags and should not be translated through shared repository mappings:

- `Carport_Ecke`
- `Carport_Treppe`
- `Daikin-WP`
- `Altherma-3`

Treat these as:

- datasource content
- installation naming
- user-configured labels

## Review outcome

Current state after this round:

- full suite runs successfully from the repository without VS Code
- import, smoke-check, screenshot capture, and final cleanup all succeed
- visible library-panel names improved in the affected language sets
- the main remaining localization gap is structural coupling inside the source dashboards, not missing tooling

## Recommended next technical task

Refactor the original `Today`, `Today (Mobile)`, `Monat`, `Jahr`, and `All-time` dashboards so the recurring internal names above are no longer used as visible labels.
