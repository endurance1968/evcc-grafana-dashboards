# Migrations-Checkliste

Englische Version: [migration-checklist_EN.md](./migration-checklist_EN.md).

Nutze diese Checkliste nach [influx-to-vm-migration.md](./influx-to-vm-migration.md) und bevor du den alten InfluxDB-Dashboard-Pfad abschaltest.

## Laufzeit

- [ ] VictoriaMetrics antwortet:

```bash
curl -fsSL http://localhost:8428/health
```

Erwartet:

```text
OK
```

- [ ] Grafana kann die VictoriaMetrics-Datasource erreichen.
- [ ] Die Grafana-Datasource-UID ist `vm-evcc`, oder `GRAFANA_DS_VM_EVCC_UID` ist auf die tatsaechliche UID gesetzt.

## Rohimport

- [ ] `vmctl influx` ist fuer den vorgesehenen Zeitraum abgeschlossen.
- [ ] EVCC-Rohserien existieren in VictoriaMetrics:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

Erwartet: JSON-Antwort mit mindestens einer `pvPower_value`-Serie fuer einen Zeitraum, in dem InfluxDB PV-Daten hatte.

- [ ] VM-only-Rohdatencheck ist sauber:

```bash
python3 check_data.py --base-url http://localhost:8428 --phase raw
```

Erwartet: benoetigte Rohdatenfamilien sind vorhanden; Label-Hygiene meldet keinen offenen Blocker.

- [ ] Influx-zu-VM-Abdeckung hat keine Dashboard-Blocker:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Erwartet:

```text
Repo-relevant problems: 0
Critical energy problems: 0
OK FOR REPO
```

## Label-Hygiene

- [ ] `host`-Bereinigung wurde uebersprungen, weil keine `host`-Serien existieren, oder sie wurde gemaess Tool-Empfehlung abgeschlossen.
- [ ] Keine EVCC-Fachlabels wurden manuell entfernt: `loadpoint`, `vehicle`, `id`, `title`.

Optionaler finaler Check:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

Erwartet: leeres `data`-Array, ausser du hast `host` bewusst behalten.

## Rollups

- [ ] Produktionskonfiguration nutzt `metric_prefix = evcc`.
- [ ] `detect` findet die erwarteten Dimensionen:

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

- [ ] `plan` listet taegliche Rollups:

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

- [ ] Initialer Backfill wurde mit `--write` abgeschlossen.
- [ ] Taegliche Rollup-Serien existieren:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Erwartet: mindestens eine `evcc_pv_energy_daily_wh`-Serie fuer einen Zeitraum mit PV-Historie.

- [ ] Vollstaendiger Checker umfasst Rollups und meldet keinen Blocker:

```bash
python3 check_data.py --base-url http://localhost:8428 --end-time 2026-03-30T23:59:59Z
```

## Scheduler

- [ ] `/usr/local/bin/evcc-vm-rollup-daily.sh` existiert und ist ausfuehrbar.
- [ ] Cron oder ein gleichwertiger Scheduler laeuft einmal pro Tag, nachdem gestern abgeschlossen ist.
- [ ] Scheduler-Kommando nutzt `--replace-range --write`.
- [ ] Logdatei enthaelt erfolgreiche Laeufe:

```bash
tail -n 80 /var/log/evcc-vm-rollup.log
```

## Grafana

- [ ] Dashboards liegen im Ordner `EVCC`.
- [ ] `Today` zeigt aktuelle Rohdaten.
- [ ] `Today - Details` zeigt Rohdaten-Detailpanels ohne Datasource-Fehler.
- [ ] `Month`, `Year` und `All-time` zeigen Rollup-Werte.
- [ ] Grafana 13.0.1 oder neuer wird genutzt und das feste Tab-Navigation-Deployment wurde getestet.

## Umschalten

Entferne InfluxDB erst aus dem aktiven Dashboard-Pfad, wenn alle vorherigen Abschnitte abgehakt sind.

Sicherer Zielzustand:

- EVCC schreibt aktuelle Daten nach VictoriaMetrics.
- InfluxDB bleibt nur als Fallback/Referenz erhalten oder wird nach Backup abgeschaltet.
- Rollup-Scheduler ist aktiv.
- Grafana-Dashboards zeigen auf VictoriaMetrics, nicht auf InfluxDB.