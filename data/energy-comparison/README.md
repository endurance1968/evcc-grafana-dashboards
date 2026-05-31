# Energievergleichsdaten

Englische Version: [README_EN.md](./README_EN.md).

Lokale externe Energievergleichsdaten liegen hier. Die Daten liegen bewusst ausserhalb von `tmp/`, weil sie fuer Migrations- und Rollup-Validierung wiederverwendet werden.

- `tibber/`: lokale Tibber-API-Exports oder Vergleichs-Snapshots.
- `vrm/`: lokale Victron-VRM-Tages-kWh-Cache-Dateien.

Die eigentlichen Cache-/Export-Dateien sind maschinenlokal und werden von Git ignoriert. Nur diese Dokumentation und `.gitkeep`-Dateien sollen getrackt bleiben.

## Validierungsworkflow

Externe Snapshots bei Bedarf aktualisieren:

```bash
python3 scripts/helper/compare_tibber_vm.py --start-day 2025-04-01 --end-day 2026-03-31 --json > data/energy-comparison/tibber/tibber-vm-cost-2025-04-01_2026-03-31.json
python3 scripts/helper/fetch_vrm_kwh_cache.py --start-day 2025-07-01 --end-day 2026-03-31
```

Gecachte Snapshots validieren, ohne Tibber oder VRM erneut zu kontaktieren:

```bash
python3 scripts/helper/validate_energy_comparison.py
```

Standardmaessig schliesst der Validator `2025-10` aus, weil die aktuellen Migrationsnotizen fuer diesen Monat unvollstaendige VM-Grid-Import-/Kosten-Rollups dokumentieren. Fuer weitere dokumentierte Anomalien wiederholt `--exclude-month YYYY-MM` uebergeben, zum Beispiel fuer April-Untersuchungen.

Wenn eine Live-VictoriaMetrics-Instanz verfuegbar ist, `--vm-base-url http://127.0.0.1:8428` hinzufuegen, um gecachte VRM-PV-/Grid-Import-Summen auch gegen die aktuellen VM-Rollups zu vergleichen.
