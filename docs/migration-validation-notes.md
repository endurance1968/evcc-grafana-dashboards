# Migrations-Validierungsnotizen

Englische Version: [migration-validation-notes_EN.md](./migration-validation-notes_EN.md).

Diese Notizen beschreiben, wie Import- und Rollup-Ergebnisse plausibilisiert werden.

## Ziele

- InfluxDB-Historie und VictoriaMetrics-Import sollen vergleichbare Datenabdeckung haben.
- Tages-Rollups sollen reproduzierbar und idempotent sein.
- Dashboards sollen Rohdaten und Rollups konsistent anzeigen.

## Wichtige Pruefungen

- Import-Abdeckung mit `compare_import_coverage.py`
- Datenpraesenz mit `check_data.py`
- Rollup-Wiederholung mit `--replace-range`
- Dashboard-Query-Readback fuer kritische Panels
- Render-Smoke-Test fuer sichtbare Panels

## Bekannte Besonderheiten

Einzelne Monate koennen wegen externer Vergleichsdaten ausgeschlossen sein. Fuer private Validierung koennen Tibber-, VRM- oder Influx-Snapshots als Referenz dienen.

## Strenger Testpfad

Fuer Maintainer und private Runner:

```bash
npm run test:rollup-path -- --strict-energy --vm-base-url http://<vm-host>:8428
```

Der Pfad kombiniert statische Checks, Energievalidierung, Query-Readback, Render-E2E und Rollup-E2E.

## Ergebnis dokumentieren

Bei einer Release-Freigabe sollten mindestens festgehalten werden:

- Datenquelle und Zeitraum
- VictoriaMetrics-Ziel
- Rollup-Konfiguration
- Dashboard-Sprache und Variante
- Testergebnis und bekannte Abweichungen