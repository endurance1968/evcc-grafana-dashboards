# Archiv: Telegraf Parallel Pipeline How-To

Englische Originalfassung: [telegraf-parallel-pipeline-howto_EN.md](./telegraf-parallel-pipeline-howto_EN.md).

Dieses Dokument ist archiviert. Der empfohlene aktuelle Pfad ist die direkte Schreibstrecke nach VictoriaMetrics und die Migrationsdokumentation unter [../influx-to-vm-migration.md](../influx-to-vm-migration.md).

## Historischer Zweck

Die parallele Telegraf-Pipeline war ein Weg, EVCC-Daten gleichzeitig in bestehende InfluxDB-Setups und in VictoriaMetrics zu schreiben. Damit konnte VictoriaMetrics aufgebaut werden, ohne bestehende Dashboards sofort abzuschalten.

## Grundidee

- bestehende EVCC/InfluxDB-Pipeline beibehalten
- zusaetzlichen Telegraf-Output nach VictoriaMetrics konfigurieren
- VictoriaMetrics unter `/influx/write` mit Influx-Line-Protocol befuellen
- Grafana-Dashboards schrittweise auf VictoriaMetrics umstellen

Beispiel:

```toml
[[outputs.http]]
  alias = "victoriametrics_evcc"
  url = "http://<vm-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]
```

## Heutige Empfehlung

Fuer neue Installationen:

- VictoriaMetrics installieren
- EVCC/Telegraf direkt nach VictoriaMetrics schreiben lassen
- Grafana-Dashboards deployen

Fuer Migrationen:

- historische InfluxDB-Daten importieren
- Rollups erzeugen
- neue Schreibstrecke erst nach erfolgreicher Pruefung aktivieren

## Risiken

- doppelte Schreibpfade koennen unterschiedliche Labelsets erzeugen
- Fehler in Telegraf-Konfiguration koennen Datenluecken verursachen
- produktive Quellen sollten in Tests nur gelesen werden

Details und historische Befehle stehen in der englischen Archivfassung.