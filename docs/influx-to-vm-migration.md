# Migration von InfluxDB nach VictoriaMetrics

Englische Version: [influx-to-vm-migration_EN.md](./influx-to-vm-migration_EN.md).

Diese Anleitung beschreibt den Wechsel einer bestehenden EVCC/InfluxDB-Historie auf VictoriaMetrics. Produktionsquellen sollten dabei nur lesend verwendet werden; schreibe Migrationstests in eine bewusst angelegte VictoriaMetrics-Testinstanz.

## Zielbild

1. VictoriaMetrics ist installiert und erreichbar.
2. Historische InfluxDB-Daten sind nach VictoriaMetrics importiert.
3. `evcc-vm-rollup.py` erzeugt taegliche `evcc_*` Rollups.
4. Grafana nutzt VictoriaMetrics mit Datasource UID `vm-evcc`.
5. Die Dashboards zeigen Rohdaten fuer `Today` und Rollups fuer Langzeitansichten.

## 1. Werkzeuge herunterladen

Empfohlene GitHub-Quelle:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"

curl -fsSLo evcc-vm-rollup.py "$BASE/scripts/rollup/evcc-vm-rollup.py"
curl -fsSLo evcc-vm-rollup-prod.conf.example "$BASE/scripts/rollup/evcc-vm-rollup-prod.conf.example"
curl -fsSLo check_data.py "$BASE/scripts/helper/check_data.py"
curl -fsSLo compare_import_coverage.py "$BASE/scripts/helper/compare_import_coverage.py"
curl -fsSLo vm-rewrite-drop-label.py "$BASE/scripts/helper/vm-rewrite-drop-label.py"
```

Fuer selbst gehostete Raw-Endpunkte gilt das Muster:

```bash
BASE="http://<server:port>/<reponame>/raw/branch/main"
```

## 2. VictoriaMetrics pruefen

```bash
curl -fsSL http://localhost:8428/health
```

## 3. InfluxDB lesen

Pruefe, dass die InfluxDB-v1-Quelle erreichbar ist und die EVCC-Datenbank vorhanden ist. Beispiel:

```bash
curl -G 'http://<influx-host>:8086/query' --data-urlencode 'db=evcc' --data-urlencode 'q=SHOW MEASUREMENTS'
```

## 4. Historie importieren

Nutze `vmctl influx` oder den bestehenden Importpfad deiner Umgebung. Importiere in die Ziel-VictoriaMetrics-Instanz. Danach sollte VictoriaMetrics EVCC-Metriken enthalten.

Pruefung:

```bash
python3 check_data.py --vm-url http://localhost:8428
python3 compare_import_coverage.py --influx-url http://<influx-host>:8086 --influx-db evcc --vm-url http://localhost:8428
```

## 5. Label bereinigen falls noetig

Wenn nach dem Import unnoetige oder stoerende Labels vorhanden sind, nutze die Rewrite-Helfer nur gegen eine Test- oder bewusst vorbereitete Zielinstanz.

Beispiel:

```bash
python3 vm-rewrite-drop-label.py --vm-url http://localhost:8428 --label unwanted_label --dry-run
```

## 6. Rollups erzeugen

Konfiguration kopieren:

```bash
cp evcc-vm-rollup-prod.conf.example evcc-vm-rollup-prod.conf
```

Wichtige Werte setzen:

```ini
VM_BASE_URL=http://localhost:8428
ROLLUP_START=2023-01-01
ROLLUP_END=2026-12-31
```

Rollup testen:

```bash
python3 evcc-vm-rollup.py --config evcc-vm-rollup-prod.conf --dry-run
python3 evcc-vm-rollup.py --config evcc-vm-rollup-prod.conf
```

## 7. Rollup planen

Fuer dauerhaften Betrieb taeglich per systemd Timer oder Cron ausfuehren. Der geplante Lauf sollte `--replace-range` fuer den zu aktualisierenden Zeitraum verwenden, damit Wiederholungen idempotent bleiben.

## 8. Grafana deployen

Weiter mit [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).

## Fehleranalyse

- [migration-troubleshooting.md](./migration-troubleshooting.md)
- [migration-validation-notes.md](./migration-validation-notes.md)
- [migration-checklist.md](./migration-checklist.md)