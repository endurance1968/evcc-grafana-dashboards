# VM Screenshot Index

This repository now keeps the generated VictoriaMetrics dashboard screenshots in version control.

Location:

- `tests/artifacts/screenshots/vm`

Covered dashboard sets:

- `original-en`
- `en-gen`
- `de-gen`
- `fr-gen`
- `nl-gen`
- `es-gen`
- `it-gen`
- `zh-gen`
- `hi-gen`

Each set contains the currently generated screenshots for:

- `Today`
- `Today - Details`
- `Today - Mobile`
- `Monat`
- `Jahr`
- `All-time`

Folder structure:

- `tests/artifacts/screenshots/vm/<set>/desktop`
- `tests/artifacts/screenshots/vm/<set>/mobile`

Examples:

- `tests/artifacts/screenshots/vm/original-en/desktop/vm-original-en-vm-evcc-today.png`
- `tests/artifacts/screenshots/vm/original-en/desktop/vm-original-en-vm-evcc-year.png`
- `tests/artifacts/screenshots/vm/de-gen/desktop/vm-de-gen-vm-evcc-heute.png`
- `tests/artifacts/screenshots/vm/fr-gen/desktop/vm-fr-gen-vm-evcc-aujourd-hui.png`
- `tests/artifacts/screenshots/vm/it-gen/desktop/vm-it-gen-vm-evcc-oggi.png`

Operational note:

- these screenshots are generated artifacts
- they should be refreshed after relevant dashboard translation or layout changes
- the current standard path is `node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true --prepare=false`
