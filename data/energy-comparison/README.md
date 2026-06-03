# Energievergleichsdaten

Englische Version: [README_EN.md](./README_EN.md).

Dieses Verzeichnis ist ein Ablageort fuer private externe Energievergleichsdaten. Es ist nicht fuer den normalen Dashboard-Betrieb erforderlich und wird von Endnutzern nicht benoetigt.

Die Daten liegen bewusst ausserhalb von `tmp/`, weil sie bei privater Migrations-, Rollup- und Release-Validierung wiederverwendet werden koennen.

- `tibber/`: lokale Tibber-API-Exports oder Vergleichs-Snapshots.
- `vrm/`: lokale Victron-VRM-Tages-kWh-Cache-Dateien.

Die eigentlichen Cache-/Export-Dateien sind maschinenlokal und werden von Git ignoriert. Nur diese Dokumentation und `.gitkeep`-Dateien sollen getrackt bleiben. Private Snapshots koennen Installations-IDs, lokale Pfade, Energieverbraeuche oder Kosten enthalten und duerfen nicht ins oeffentliche Repository committed werden.

## Speicher-Effizienz

Die Dashboard-Kennzahl `Speicher-Effizienz` ist ein Energiefluss-Verhaeltnis, keine Herstellerangabe zur Zell- oder Wechselrichtereffizienz:

```text
Speicher-Effizienz = Speicher entladen / Speicher laden * 100
```

In VictoriaMetrics nutzt das Dashboard dafuer `evcc_battery_discharge_daily_wh` und `evcc_battery_charge_daily_wh`. Ein optionaler VRM-Vergleich kann die dazu naheliegenden VRM-Fluesse verwenden:

```text
VRM Speicher laden    = pv_to_battery_kwh + grid_to_battery_kwh
VRM Speicher entladen = battery_to_consumers_kwh + battery_to_grid_kwh
```

Kurzzeitraeume koennen wegen unterschiedlicher Bilanzgrenzen zwischen EVCC/VM und externen Portalen sichtbar abweichen. Fuer Release- und Migrationsvalidierung ist deshalb die Monats- und Gesamtsicht massgeblich. Konkrete lokale Auswertungen und Auffaelligkeiten gehoeren in private Notizen oder lokale Cache-Dateien, nicht in diese Repo-Dokumentation.

## Validierungsworkflow

Externe Snapshots bei Bedarf lokal aktualisieren:

```bash
python3 scripts/helper/compare_tibber_vm.py --start-day YYYY-MM-DD --end-day YYYY-MM-DD --json > data/energy-comparison/tibber/tibber-vm-cost-YYYY-MM-DD_YYYY-MM-DD.json
python3 scripts/helper/fetch_vrm_kwh_cache.py --start-day YYYY-MM-DD --end-day YYYY-MM-DD --site-id <vrm-site-id>
```

Gecachte Snapshots validieren, ohne Tibber oder VRM erneut zu kontaktieren:

```bash
python3 scripts/helper/validate_energy_comparison.py
```

Standardmaessig schliesst der Validator dokumentierte Anomaliemonate aus, soweit sie im Skript gepflegt sind. Fuer weitere dokumentierte Anomalien wiederholt `--exclude-month YYYY-MM` uebergeben.

Fuer private Validierung mit vorhandenem VRM-Cache kann die Speicher-Effizienz erzwungen werden:

```bash
python3 scripts/helper/validate_energy_comparison.py --require-cache vrm-battery
```

Wenn eine disposable oder ausdruecklich freigegebene VictoriaMetrics-Instanz verfuegbar ist, `--vm-base-url http://127.0.0.1:8428` hinzufuegen, um gecachte externe Summen auch gegen aktuelle VM-Rollups zu vergleichen. Niemals gegen eine produktive VictoriaMetrics-Instanz schreiben oder loeschen.
