# Energievergleichsdaten

Englische Version: [README_EN.md](./README_EN.md).

Lokale externe Energievergleichsdaten liegen hier. Die Daten liegen bewusst ausserhalb von `tmp/`, weil sie fuer Migrations- und Rollup-Validierung wiederverwendet werden.

- `tibber/`: lokale Tibber-API-Exports oder Vergleichs-Snapshots.
- `vrm/`: lokale Victron-VRM-Tages-kWh-Cache-Dateien.

Die eigentlichen Cache-/Export-Dateien sind maschinenlokal und werden von Git ignoriert. Nur diese Dokumentation und `.gitkeep`-Dateien sollen getrackt bleiben.

## Speicher-Effizienz

Die Dashboard-Kennzahl `Speicher-Effizienz` ist ein Energiefluss-Verhaeltnis, keine Herstellerangabe zur Zell- oder Wechselrichtereffizienz:

```text
Speicher-Effizienz = Speicher entladen / Speicher laden * 100
```

In VictoriaMetrics nutzt das Dashboard dafuer `evcc_battery_discharge_daily_wh` und `evcc_battery_charge_daily_wh`. Der VRM-Vergleich nutzt die dazu naheliegenden VRM-Fluesse:

```text
VRM Speicher laden    = pv_to_battery_kwh + grid_to_battery_kwh
VRM Speicher entladen = battery_to_consumers_kwh + battery_to_grid_kwh
```

Kurzzeitraeume koennen wegen unterschiedlicher Bilanzgrenzen zwischen EVCC/VM und VRM sichtbar abweichen. Fuer Release- und Migrationsvalidierung ist deshalb die Monats- und Gesamtsicht massgeblich.

Aktueller lokaler VRM-Cache-Check mit Oles Daten nach den Standardausschluessen `2025-04` und `2025-10`: `2025-07..2026-03`, 243 Tage, 5102.02 kWh Speicherladung, 4604.82 kWh Speicherentladung, Gesamt-Effizienz `90.25%`. Der Monatswert `2025-08` liegt mit `105.73%` ueber 100%; das wird nicht automatisch als Rollup-Fehler bewertet, weil VRM-Flussgruppen und EVCC/VM-Batterieleistung unterschiedliche Bilanzgrenzen haben koennen. Solche Abweichungen muessen in der Monats-/Gesamtsicht interpretiert oder gegen eine Live-VM mit `--vm-base-url` weiter untersucht werden.

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

Standardmaessig schliesst der Validator `2025-04` und `2025-10` aus, weil diese Monate als Tibber-/EVCC-/Import-Anomalien dokumentiert sind. Fuer weitere dokumentierte Anomalien wiederholt `--exclude-month YYYY-MM` uebergeben.

Fuer private Validierung mit vorhandenem VRM-Cache kann die Speicher-Effizienz erzwungen werden:

```bash
python3 scripts/helper/validate_energy_comparison.py --require-cache vrm-battery
```

Wenn eine Live-VictoriaMetrics-Instanz verfuegbar ist, `--vm-base-url http://127.0.0.1:8428` hinzufuegen, um gecachte VRM-PV-/Grid-Import-Summen und die Batteriefluss-Effizienz auch gegen die aktuellen VM-Rollups zu vergleichen.
