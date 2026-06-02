# Lokalisierungsworkflow

Englische Version: [README_EN.md](./README_EN.md).

- `languages.json`: definiert Quell- und Zielsprachen fuer den Standard-VM-Flow
- `../original/<sourceLanguage>`: Source of Truth fuer VM-Dashboards
- `../translation/<language>`: generierte Ausgabe pro konfigurierter Zielsprache
- `<source>_to_<target>.json`: Uebersetzungsmapping pro Sprachpaar
- `missing-<source>_to_<target>.exact.json`: Audit-Bericht mit offenen Kandidatentexten

Wichtig: Die Skripte fuehren keine eigentliche Sprachuebersetzung aus. Ein menschlicher Uebersetzer oder eine KI muss den finalen Zielsprachentext in `en_to_<language>.json` liefern. Die Skripte finden nur fehlende Mapping-Eintraege, koennen sie optional als Platzhalter uebernehmen und erzeugen Dashboards aus den Mappings.

## Standardablauf

Mapping-Eintraege entfernen, die in den aktuellen Quelldashboards nicht mehr vorkommen:

```bash
node scripts/localization/prune-mappings-to-source.mjs
```

Das ist standardmaessig ein Dry-run. Wenn die Ausgabe korrekt aussieht, die bereinigten Mappings explizit schreiben:

```bash
node scripts/localization/prune-mappings-to-source.mjs --write
```

Fehlende Source-to-Target-Mappings fuer alle konfigurierten Ziele auditieren:

```bash
node scripts/localization/audit-localization.mjs
```

Nur eine bestimmte Zielsprache auditieren:

```bash
node scripts/localization/audit-localization.mjs --target=fr
```

Der Audit schreibt `missing-<source>_to_<target>.exact.json` mit Kandidatenschluesseln, fuer die noch Mapping-Eintraege fehlen. `exactSources` listet die Quelldashboard-Dateinamen, die jeden Kandidaten erzeugt haben.

Uebersetze relevante Kandidaten manuell in die echte Mapping-Datei, zum Beispiel `en_to_fr.json`. Wenn alle fehlenden Kandidaten zunaechst bewusst als Platzhalter akzeptiert werden sollen, uebernimm sie in die Mappings:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all
```

Das ist standardmaessig ein Dry-run. Wenn die Ausgabe korrekt aussieht, schreibe die Platzhalter-Eintraege explizit:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all --write
```

`adopt-missing-into-mappings.mjs` schreibt nur mit `--write` Eintraege der Form `source -> source`. Das ist kein Uebersetzungsschritt; ersetze diese Werte durch echte Zielsprachentexte, bevor du lokalisierte Ausgabe erwartest.

Lokalisierte Dashboard-Dateien fuer alle konfigurierten Zielsprachen erzeugen:

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

Sichere Display-only-Uebersetzungen auf die generierten Dashboard-Dateien anwenden:

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

Den vollstaendigen End-to-End-Grafana-Validierungsworkflow beschreibt [grafana-localization-testing.md](../../docs/de/design/grafana-localization-testing.md).
