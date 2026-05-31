# Migration Troubleshooting

Englische Version: [migration-troubleshooting_EN.md](./migration-troubleshooting_EN.md).

Nutze dieses Dokument nur, wenn der normale Pfad in [influx-to-vm-migration.md](./influx-to-vm-migration.md) ein Problem meldet.

## Erste Regel: Rohdaten vor Rollups pruefen

Die meisten Probleme in Langzeit-Dashboards entstehen an einer von zwei Stellen:

- Rohdaten wurden nicht vollstaendig importiert.
- Rollups wurden aus bereits defekten Rohdaten gebaut.

Pruefe in dieser Reihenfolge:

1. VictoriaMetrics Health
2. Rohmetriken vorhanden
3. Influx-zu-VM-Abdeckung
4. `host`-Label-Hygiene
5. Rollup-Ausgabe
6. Grafana-Datasource und Dashboard-Variablen

## Rohmetriken vorhanden?

Beispiel fuer eine Rohserienpruefung:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

Wenn fuer einen Zeitraum mit InfluxDB-Daten keine Serie zurueckkommt, pruefe `vmctl influx`, Datenbankname, Zeitraum und Zugangsdaten erneut.

## Coverage-Check meldet Probleme

Fuehre den Coverage-Check direkt nach `vmctl` und vor jeder Bereinigung aus:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Interpretation:

- `Repo-relevant problems: 0` bedeutet, dass das aktive Dashboard-Schema nicht blockiert ist.
- `Additional`-Funde koennen zusaetzliche EVCC-Metadaten oder Nicht-Dashboard-Messungen sein.
- `Critical energy problems` muessen geloest werden, bevor Rollups vertrauenswuerdig sind.

Eine einzelne Measurement-Familie untersuchen:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --measurement-regex '^batterySoc$' \
  --only-problems
```

## PV-Importdrift oder fehlendes `pvPower`

Wenn der kritische PV-Paritaetscheck fehlschlaegt, repariere rohe `pvPower`-Daten vor dem Neuaufbau der Rollups.

1. Betroffene rohe `pvPower_value`-Familie in VictoriaMetrics loeschen.
2. Nur `pvPower` mit `vmctl influx --influx-filter-series` erneut importieren.
3. Coverage fuer `pvPower` erneut pruefen.
4. `evcc_*` Rollups neu bauen.

Beispiel:

```bash
curl -fsS -X POST 'http://localhost:8428/api/v1/admin/tsdb/delete_series' \
  --data-urlencode 'match[]=pvPower_value'

yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-series "on evcc from pvPower" \
  --influx-filter-time-start='2025-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-31T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

## `host`-Bereinigung meldet Konflikte

Pruefen, ob `host` existiert:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

Dry-Run:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Folge exakt der Empfehlung, die das Tool ausgibt.

Sauberer Fall:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --reset-cache \
  --write
```

Wenn das Tool meldet, dass ein Ziel-Delete nicht verwaltete hostlose Geschwisterserien loeschen wuerde, stoppe. Re-importiere oder validiere zuerst die betroffene Measurement-Familie; sonst koennen Detail-Dashboards PV-String- oder Batterie-Detailserien verlieren, obwohl aggregierte Panels weiter Werte zeigen.

Konfliktbewahrender Fall, wenn hostlose Zielwerte autoritativ bleiben sollen:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --keep-target-values-on-conflict \
  --reset-cache \
  --write
```

Diese Labels niemals blind entfernen:

- `loadpoint`
- `vehicle`
- `id`
- `title`

Sie tragen EVCC-Fachbedeutung.

## Historische Fachlabel-Umbenennung

Nutze `vm-rewrite-label-value.py` nur fuer bewusste Fachlabel-Umbenennungen, zum Beispiel nachdem ein PV-Titel in EVCC geaendert wurde. Aendere zuerst die Live-EVCC-Konfiguration, sonst schreiben neue Samples weiter das alte Label.

Dry-Run:

```bash
python3 vm-rewrite-label-value.py \
  --base-url http://localhost:8428 \
  --matcher '{title="Balkon PV"}' \
  --label title \
  --from "Balkon PV" \
  --to "Balkon Sued" \
  --backup-jsonl backups/rename-balkon-pv.jsonl \
  --rewritten-jsonl backups/rename-balkon-sued.jsonl
```

Fuer PV-Geraete ist `title` normalerweise der stabilere Fachschluessel. EVCC kann PV-`id`-Werte neu nummerieren, wenn Geraete hinzugefuegt, entfernt oder umsortiert werden.

## Leere Grafana-Dashboards

`Today` leer bedeutet meist Rohdaten- oder Datasource-Probleme:

- Grafana-Datasource zeigt auf den falschen Host.
- Datasource-UID passt nicht zu `vm-evcc` oder zum Deploy-Override.
- EVCC schreibt keine aktuellen Rohdaten nach VictoriaMetrics.

`Month`, `Year` oder `All-time` leer bedeutet meist fehlende Rollups:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Wenn keine `evcc_*`-Serien existieren, fuehre Rollup-Backfill und Scheduler-Setup aus [influx-to-vm-migration.md](./influx-to-vm-migration.md) erneut aus.