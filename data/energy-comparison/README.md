# Energievergleichsdaten

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt lokale Vergleichsdaten fuer Energie- und Kostenvalidierung, z. B. Tibber- oder Victron-VRM-Snapshots.

## Zweck

Die Daten helfen, Migrationen und Rollups gegen externe Referenzen zu plausibilisieren. Sie sind vor allem fuer private Validierung und Release-Sicherheit gedacht.

## Nutzung

Standardtest:

```bash
npm run test:energy-validation
```

Strenger privater Test mit vorhandenen Caches:

```bash
npm run test:energy-validation -- --require-cache data/energy-comparison/tibber --require-cache data/energy-comparison/vrm
```

## Hinweise

- Private Vergleichsdaten nicht ungeprueft veroeffentlichen.
- Bekannte Ausnahmen und ausgeschlossene Monate dokumentieren.
- Produktionsquellen fuer Validierung nur lesend verwenden.