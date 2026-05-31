# Telegraf fuer parallele Datenbank-Schreibzugriffe verwenden

Englische Version: [telegraf-parallel-pipeline-howto_EN.md](./telegraf-parallel-pipeline-howto_EN.md).

Dieses Dokument beschreibt das Telegraf-Fan-out-Muster fuer EVCC-Metriken, damit derselbe eingehende Schreibstream parallel an mehrere Backends gesendet werden kann.

Hinweis: Die kanonische Endnutzeranleitung fuer EVCC/Telegraf nach VictoriaMetrics ist [../evcc-telegraf-live-ingest.md](../evcc-telegraf-live-ingest.md). Diese Archivseite bleibt als fortgeschrittener Hintergrund fuer mehrere parallele Backends erhalten.

## Ziel

Telegraf als einzelnen Ingest-Punkt verwenden und eingehende EVCC-Metriken weiterleiten an:

- InfluxDB v1 fuer Legacy-Dashboards
- VictoriaMetrics fuer neue Dashboards
- PostgreSQL fuer SQL-basierte Analyse und historische Backfill-Ziele

## Warum Telegraf dazwischen sitzt

Telegraf gibt uns eine kontrollierte Pipeline:

`evcc -> Telegraf listener -> InfluxDB + VictoriaMetrics + PostgreSQL`

Das zentralisiert den Schreibpfad und vermeidet, dass jeder Produzent jedes Backend kennen muss.

## Wichtiges API-Detail

In diesem Setup schreibt EVCC mit dem InfluxDB-v2-Clientpfad:

- Request-Pfad: `/api/v2/write`
- Auth-Stil: `Authorization: Token ...`

Ein einfaches `[[inputs.influxdb_listener]]` behandelt nur den Influx-v1-Schreibpfad `/write`.

Deshalb sollte EVCC auf einen Telegraf-Endpoint `[[inputs.influxdb_v2_listener]]` zeigen.

## Empfohlenes Listener-Layout

Das aktuelle Setup nutzt den Influx-v2-Listener auf dem Standard-EVCC-Schreibport und laesst den v1-Listener deaktiviert.

Beispiel:

```toml
[agent]
  interval = "10s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  flush_interval = "10s"
  flush_jitter = "1s"
  precision = "1s"
  omit_hostname = true
  debug = true

#[[inputs.influxdb_listener]]
#  service_address = ":8086"
#  read_timeout = "30s"
#  write_timeout = "30s"
#  basic_username = "<listener-user>"
#  basic_password = "<listener-password>"

[[inputs.influxdb_v2_listener]]
  service_address = ":8086"
  read_timeout = "30s"
  write_timeout = "30s"
  token = "<listener-token>"
```

Praktische Bedeutung:

- `:8086` ist das aktive EVCC-Schreibziel ueber die Influx-v2-API.
- der v1-Listener bleibt auskommentiert, ausser `/write`-Kompatibilitaet wird explizit fuer manuelle Tests gebraucht.
- `omit_hostname = true` verhindert, dass Telegraf ein rein infrastrukturelles `host`-Label hinzufuegt.

## Beispiel fuer Output-Fan-out

```toml
[[outputs.http]]
  alias = "victoriametrics"
  url = "http://<victoriametrics-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]

[[outputs.postgresql]]
  connection = "host=<postgres-host> user=<postgres-user> password=<postgres-password> dbname=telemetry sslmode=disable"
  tags_as_foreign_keys = false

[[outputs.influxdb]]
  alias = "influx"
  urls = ["http://<influxdb-host>:8086"]
  database = "evcc"
  username = "<influxdb-user>"
  password = "<influxdb-password>"
  timeout = "10s"
```

Praktische Bedeutung:

- `alias` macht Telegraf-Logs lesbarer, wenn zwei Outputs denselben Plugin-Typ nutzen.
- VictoriaMetrics nutzt `outputs.http` mit `data_format = "influx"`, damit Telegraf Influx-Line-Protocol direkt an `/influx/write` sendet.
- Das vermeidet bewusst Telegrafs `outputs.influxdb`-Datenbankhandling, damit VictoriaMetrics kein synthetisches `db`-Label aus dem Schreibziel erzeugt.

Wichtig:

- `[[outputs.influxdb]]` in diesem Repository nicht fuer VictoriaMetrics verwenden.
- Wenn `database = "evcc"` gesetzt ist, nimmt VictoriaMetrics ein synthetisches `db="evcc"`-Label auf.
- Wenn `database` weggelassen wird, faellt Telegraf auf seinen Default-Datenbanknamen zurueck und VictoriaMetrics nimmt trotzdem ein synthetisches `db`-Label wie `db="telegraf"` auf.
- Das Repository nimmt eine VictoriaMetrics-Instanz pro EVCC-Instanz an, deshalb muss der Live-Telegraf-Pfad frei von gemeinsamem `db`-Multiplexing-Label bleiben.

## Betriebschecks nach Aenderungen

Nach jeder Listener- oder Output-Aenderung alles Folgende pruefen:

1. EVCC kann erfolgreich zum vorgesehenen Telegraf-Listener schreiben.
2. Ein frischer Probe-Punkt erscheint in InfluxDB.
3. Dieselbe Probe-Serie erscheint in VictoriaMetrics ohne `db`-Label.
4. Dieselben Probe-Daten erscheinen in PostgreSQL.
5. Telegraf-Logs zeigen keine dauerhaften Output-Fehler.

Schneller VictoriaMetrics-Check:

```bash
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)

curl -sG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=gridPower_value' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END"
```

Erwartetes Ergebnis fuer den Live-Telegraf-Pfad:

- eine frische Rohserie wie `{ "__name__": "gridPower_value" }`
- kein `db`-Feld in diesem Serienobjekt

## Warum InfluxDB waehrend der Migration bleibt

InfluxDB bleibt im Fan-out, solange die Legacy-Dashboards noch genutzt werden.

Das ermoeglicht:

- bestehende Dashboards ohne sofortige Rewrites erhalten
- VictoriaMetrics-Dashboards parallel bauen und testen
- historische Daten nach VictoriaMetrics und PostgreSQL backfillen, ohne EVCC-Schreibzugriffe zu unterbrechen

## Migrationshinweise

Empfohlene Reihenfolge:

1. Bestaetigen, dass die Live-Pipeline ueber Telegraf funktioniert.
2. InfluxDB im Output-Fan-out behalten, damit Legacy-Dashboards weiter funktionieren.
3. Historische Rohdaten aus InfluxDB nach VictoriaMetrics backfillen.
4. Erforderliche Aggregationen fuer das neue Dashboard-Set neu erzeugen oder neu bauen.
5. Historische Rohdaten aus InfluxDB nach PostgreSQL backfillen.
6. Legacy-Influx-Pfad erst entfernen, nachdem die neuen Dashboards akzeptiert wurden.
