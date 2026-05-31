# Migrations-Checkliste

Englische Version: [migration-checklist_EN.md](./migration-checklist_EN.md).

Diese Checkliste fasst die Migration von EVCC/InfluxDB nach VictoriaMetrics zusammen.

## Vorbereitungen

- [ ] InfluxDB-Quelle ist erreichbar und wird nur lesend verwendet.
- [ ] Ziel-VictoriaMetrics ist angelegt und fuer Tests beschreibbar.
- [ ] Grafana 13.0.1 oder neuer ist verfuegbar.
- [ ] VictoriaMetrics Datasource Plugin ist installiert.
- [ ] Backup der bestehenden InfluxDB-Daten ist vorhanden.

## Import

- [ ] Importwerkzeug vorbereitet, z. B. `vmctl influx`.
- [ ] InfluxDB-Datenbank `evcc` oder eigener Name bestaetigt.
- [ ] Import gegen Test-/Ziel-VictoriaMetrics ausgefuehrt.
- [ ] Datenabdeckung mit `compare_import_coverage.py` geprueft.
- [ ] Auffaellige Label oder Messreihen dokumentiert.

## Rollup

- [ ] `evcc-vm-rollup.py` und Konfiguration vorbereitet.
- [ ] Zeitraum fuer historische Rollups festgelegt.
- [ ] Dry Run erfolgreich.
- [ ] Rollup-Lauf erfolgreich.
- [ ] `evcc_*` Metriken in VictoriaMetrics vorhanden.
- [ ] Taeglicher Refresh geplant.

## Grafana

- [ ] Datasource UID `vm-evcc` oder passende Env-Konfiguration gesetzt.
- [ ] Service-Account-Token erzeugt.
- [ ] Dashboards mit `deploy-python.sh`, `deploy-bash.sh` oder `deploy.ps1` importiert.
- [ ] `Today` zeigt Rohdaten.
- [ ] `Month`, `Year`, `All-time` zeigen Rollup-Daten.
- [ ] Keine Panels zeigen Query- oder Datasource-Fehler.

## Abschluss

- [ ] Alte InfluxDB-Dashboards nicht mehr als primaerer Pfad benoetigt.
- [ ] Backup- und Restore-Strategie fuer VictoriaMetrics dokumentiert.
- [ ] Rollup-Log und Fehlerpfad bekannt.
- [ ] Produktivschreibpfad auf VictoriaMetrics bewusst aktiviert.