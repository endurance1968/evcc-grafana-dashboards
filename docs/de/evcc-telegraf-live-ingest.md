# EVCC/Telegraf Live-Ingest nach VictoriaMetrics

Englische Version: [evcc-telegraf-live-ingest.md](../en/evcc-telegraf-live-ingest.md).

Diese Anleitung beschreibt, wie aktuelle EVCC-Messwerte nach VictoriaMetrics geschrieben werden.

Bei einer neuen Installation wird der Schreibpfad sofort aktiviert. Bei einer InfluxDB-Migration wird er zuerst nur vorbereitet und erst nach dem finalen Delta-Import aktiviert. Dadurch kannst du die Konfiguration frueh testen und trotzdem vermeiden, dass derselbe Zeitraum gleichzeitig per Live-Ingest und per Import in VictoriaMetrics landet.

Kurz gesagt:

- neuer Stack: konfigurieren, aktivieren, pruefen, danach Grafana
- Migration: konfigurieren, VictoriaMetrics-Output noch deaktiviert lassen, Historie migrieren, finalen Delta-Import ausfuehren, dann aktivieren und pruefen

## Wann welcher Pfad?

### Neuer VictoriaMetrics-Stack ohne alte InfluxDB

Wenn du keinen alten InfluxDB-Pfad parallel behalten musst, kann EVCC direkt nach VictoriaMetrics schreiben.

Nutze diesen Pfad fuer neue Installationen.

### Migration von InfluxDB

Wenn vorhandene InfluxDB-Dashboards waehrend der Umstellung weiterlaufen sollen, nutze Telegraf als Fan-out:

```text
EVCC -> Telegraf -> InfluxDB v1 + VictoriaMetrics
```

Das ist der empfohlene Umsteigerpfad, weil EVCC nur ein Ziel beschreiben muss und Telegraf die Daten an alte und neue Backends verteilt.

Wichtig fuer Migrationen: Richte Telegraf frueh ein, aber aktiviere den VictoriaMetrics-Output erst am Cutover. Bis dahin schreibt Telegraf weiter nur nach InfluxDB. So bleibt die alte Umgebung stabil, und die VictoriaMetrics-Historie kommt kontrolliert aus dem InfluxDB-Import.

## Voraussetzungen

- VictoriaMetrics ist erreichbar, zum Beispiel `http://<victoriametrics-host>:8428`.
- EVCC kann den Zielhost erreichen.
- Bei Telegraf-Fan-out ist Telegraf installiert und kann InfluxDB und VictoriaMetrics erreichen.
- Nutze eine VictoriaMetrics-Instanz pro EVCC-Instanz. Kein synthetisches `db`-Label fuer mehrere EVCC-Systeme in einer gemeinsamen VM-Instanz.

## Pfad A: EVCC schreibt direkt nach VictoriaMetrics

EVCC nutzt seine `influx:`-Konfiguration. VictoriaMetrics stellt eine InfluxDB-kompatible API bereit.

In `evcc.yaml`:

```yaml
influx:
  url: http://<victoriametrics-host>:8428
```

Wenn VictoriaMetrics per Basic Auth geschuetzt ist, kann der Nutzername und das Passwort in der URL stehen:

```yaml
influx:
  url: http://<user>:<password>@<victoriametrics-host>:8428
```

Hinweise:

- In der EVCC-Web-Konfiguration gesetzte Werte koennen Dateiwerte aus `evcc.yaml` uebersteuern.
- Nutze diesen direkten Pfad nur, wenn EVCC nicht gleichzeitig eine alte InfluxDB-Instanz weiter beschreiben soll.
- Fuer die Dashboards muessen Rohmetriken wie `pvPower_value`, `gridPower_value`, `homePower_value` und `chargePower_value` in VictoriaMetrics ankommen.

EVCC danach neu laden oder neu starten, je nach Installationsart.

## Pfad B: EVCC schreibt nach Telegraf und Telegraf verteilt weiter

Dieser Pfad ist fuer Migrationen empfohlen.

### 1. EVCC auf Telegraf zeigen lassen

EVCC mit InfluxDB-v2-kompatibler Konfiguration auf den Telegraf-Listener zeigen lassen:

```yaml
influx:
  url: http://<telegraf-host>:8086
  database: evcc
  token: <listener-token>
  org: evcc
```

Die Werte `database`, `token` und `org` muessen zum Telegraf-Listener passen. `database` entspricht bei InfluxDB v2 dem Bucket-Namen, heisst in EVCC aus Kompatibilitaetsgruenden aber weiterhin `database`.

### 2. Telegraf-Listener konfigurieren

In der Telegraf-Konfiguration:

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

[[inputs.influxdb_v2_listener]]
  service_address = ":8086"
  read_timeout = "30s"
  write_timeout = "30s"
  token = "<listener-token>"
```

Wichtig:

- `[[inputs.influxdb_v2_listener]]` ist fuer EVCCs `/api/v2/write`-Pfad geeignet.
- `omit_hostname = true` verhindert, dass Telegraf ein Infrastruktur-Label `host` hinzufuegt.
- Der alte `[[inputs.influxdb_listener]]` fuer `/write` ist nur noetig, wenn du explizit InfluxDB-v1-Schreibclients an Telegraf betreibst.

### 3. VictoriaMetrics-Output vorbereiten

VictoriaMetrics ueber `outputs.http` beschreiben:

```toml
[[outputs.http]]
  alias = "victoriametrics_evcc"
  url = "http://<victoriametrics-host>:8428/influx/write"
  method = "POST"
  data_format = "influx"
  timeout = "10s"
  non_retryable_statuscodes = [400]
```

Bei einer neuen Installation bleibt dieser Block aktiv. Bei einer Migration kommentierst du den Block bis zum Cutover aus oder legst ihn vorbereitet ab und aktivierst ihn erst nach dem finalen Delta-Import:

```toml
# [[outputs.http]]
#   alias = "victoriametrics_evcc"
#   url = "http://<victoriametrics-host>:8428/influx/write"
#   method = "POST"
#   data_format = "influx"
#   timeout = "10s"
#   non_retryable_statuscodes = [400]
```

Nicht `[[outputs.influxdb]]` fuer VictoriaMetrics verwenden. Dieses Plugin kann ein synthetisches `db`-Label erzeugen. Die Dashboards und Rollups erwarten stattdessen eine dedizierte VictoriaMetrics-Instanz ohne gemeinsames `db`-Multiplexing.

### 4. Legacy-InfluxDB optional weiter beschreiben

Wenn alte InfluxDB-Dashboards weiterlaufen sollen, bleibt InfluxDB als zusaetzlicher Output in Telegraf:

```toml
[[outputs.influxdb]]
  alias = "influx_legacy"
  urls = ["http://<influxdb-host>:8086"]
  database = "evcc"
  username = "<influxdb-user>"
  password = "<influxdb-password>"
  timeout = "10s"
```

Diesen `outputs.influxdb`-Block nur fuer die alte InfluxDB verwenden, nicht fuer VictoriaMetrics.

### 5. Telegraf neu starten

```bash
sudo systemctl restart telegraf
sudo systemctl status telegraf
```

Logs pruefen:

```bash
journalctl -u telegraf -n 100 --no-pager
```

Bei einer Migration ist dieser Neustart auch im Vorbereitungsmodus sinnvoll. Dann pruefst du, dass EVCC weiter ueber Telegraf nach InfluxDB schreibt. Der VictoriaMetrics-Output bleibt dabei noch deaktiviert.

## VictoriaMetrics-Schreibpfad bei einer Migration aktivieren

Fuehre diesen Abschnitt erst aus, wenn die InfluxDB-Historie importiert, geprueft und der finale Delta-Import abgeschlossen ist.

Ein einfacher Cutover fuer Nicht-Experten:

1. Merke dir den Umschaltzeitpunkt.
2. Importiere die letzten noch fehlenden InfluxDB-Daten bis zu diesem Zeitpunkt nach VictoriaMetrics.
3. Aktiviere den vorbereiteten `[[outputs.http]]`-Block in Telegraf.
4. Starte Telegraf neu.
5. Pruefe, dass aktuelle Serien in VictoriaMetrics ankommen.

Wenn du eine Datenluecke von wenigen Sekunden unbedingt vermeiden willst, plane ein kurzes Wartungsfenster: EVCC kurz anhalten, finalen Delta-Import ausfuehren, VictoriaMetrics-Output aktivieren, Telegraf starten, EVCC wieder starten. Das ist einfacher und sauberer als absichtlich ueberlappende Import- und Live-Zeitraeume.

## Live-Ingest pruefen

### VictoriaMetrics Healthcheck

```bash
curl -fsSL http://<victoriametrics-host>:8428/health
```

Erwartet:

```text
OK
```

### Aktuelle EVCC-Serie suchen

Nach einigen EVCC-Schreibintervallen:

```bash
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START=$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ)

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=gridPower_value' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END"
```

Erwartet:

- mindestens eine `gridPower_value`-Serie
- kein `db`-Label
- kein `host`-Label, wenn Telegraf mit `omit_hostname = true` genutzt wird

### EVCC-Fachlabels pruefen

Pruefe vor dem Dashboard-Deployment kurz, ob EVCC die fachlichen Labels mitsendet. Diese Labels steuern spaeter, welche PV-, Batterie-, AUX-/EXT-, Ladepunkt- und Fahrzeugserien Grafana trennt oder zusammenfasst:

```bash
curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'end=now'

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value' \
  --data-urlencode 'start=now-1h' \
  --data-urlencode 'end=now'
```

Erwartung:

- PV-, Batterie-, AUX- und EXT-Serien haben stabile `title`-Werte, wenn die Geraete in EVCC benannt sind.
- Ladepunktserien haben ein `loadpoint`-Label.
- Fahrzeugserien haben ein `vehicle`-Label, sobald EVCC Fahrzeugdaten schreibt.
- Fehlende AUX-/EXT-Serien sind OK, wenn du keine solchen EVCC-Meter nutzt; die Dashboards sollen dann trotzdem nutzbar bleiben.

Wenn ein Name falsch ist, korrigiere zuerst EVCC. Neue Messwerte bekommen dann den neuen Namen; alte historische Labels bleiben unveraendert, bis du sie bewusst migrierst.


### PV-Forecast aus EVCC pruefen

Die Forecast-Panels der Dashboards rufen keine Forecast-Provider direkt auf. Sie zeigen nur die EVCC-Metrik `tariffSolar_value` an. Diese Metrik existiert nur, wenn in EVCC ein Solar-Forecast konfiguriert ist, zum Beispiel ueber EVCCs `solar`-Tarif-/Forecast-Konfiguration mit Forecast.Solar, Solcast oder Open-Meteo.

Wenn du keinen EVCC-Solar-Forecast nutzt, sind leere Forecast-Panels erwartbar und kein VictoriaMetrics- oder Dashboard-Fehler. PV-, Netz-, Haus- und Batteriepanels koennen trotzdem korrekt funktionieren.

Pruefe, ob EVCC Forecast-Werte nach VictoriaMetrics schreibt:

```bash
curl -fsG 'http://<victoriametrics-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=tariffSolar_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://<victoriametrics-host>:8428/api/v1/query' \
  --data-urlencode 'query=last_over_time(tariffSolar_value[24h])'
```

Erwartung:

- Mit EVCC-Solar-Forecast: mindestens eine `tariffSolar_value`-Serie und ein aktueller Wert.
- Ohne EVCC-Solar-Forecast: keine Serie oder leeres Ergebnis; das ist fuer Forecast-Panels ein tolerierter optionaler Zustand.

Konfiguriere oder korrigiere Forecast-Provider in EVCC, nicht im Grafana-Dashboard. Danach schreibt EVCC neue `tariffSolar_value`-Samples, und Grafana zeigt sie automatisch an.
### Optionaler Telegraf-Probe-Write

Nur auf einer Test- oder bewusst vorbereiteten Instanz ausfuehren:

```bash
curl -i -XPOST 'http://<telegraf-host>:8086/api/v2/write?org=evcc&bucket=evcc&precision=s' \
  -H 'Authorization: Token <listener-token>' \
  --data-binary "evcc_ingest_probe value=1 $(date +%s)"
```

Danach in VictoriaMetrics nach `evcc_ingest_probe` suchen. Diese Probe ist nicht fuer Produktionsdashboards relevant; sie prueft nur den Schreibpfad.

## Haeufige Fehler

- EVCC zeigt noch auf die alte InfluxDB statt auf Telegraf oder VictoriaMetrics.
- Telegraf nutzt `[[outputs.influxdb]]` fuer VictoriaMetrics und erzeugt dadurch ein `db`-Label.
- `omit_hostname = true` fehlt und Telegraf erzeugt ein `host`-Label.
- Grafana oder EVCC nutzt `localhost`, obwohl der Dienst in einem anderen Container oder auf einem anderen Host laeuft.
- Firewall oder Docker-Port-Mapping blockiert `8428` oder `8086`.
- EVCC-Web-Konfiguration uebersteuert den erwarteten `evcc.yaml`-Wert.
- Dashboard-Details zeigen nur Summen oder falsche Gruppen: EVCC-Labels wie `title`, `loadpoint` oder `vehicle` fehlen, wurden historisch umbenannt oder passen nicht zu den Blocklist-Regexes.

## Naechster Schritt

Wenn aktuelle EVCC-Rohdaten in VictoriaMetrics ankommen, kommt danach Grafana:

- Grafana installieren, falls noch keine passende Instanz vorhanden ist: [grafana-install-debian-13.md](./grafana-install-debian-13.md) oder [grafana-install-docker.md](./grafana-install-docker.md)
- Grafana-Datasource anlegen und Dashboards deployen: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

Wenn du diese Anleitung nur zur Vorbereitung einer InfluxDB-Migration genutzt hast, gehe jetzt zurueck zu [influx-to-vm-migration.md](./influx-to-vm-migration.md). Erst nach dem finalen Delta-Import wird der VictoriaMetrics-Schreibpfad aktiviert.

## Quellen

- [EVCC Influx-Konfiguration](https://docs.evcc.io/docs/reference/configuration/influx)
- [EVCC Tarife und Vorhersagen](https://docs.evcc.io/de/tariffs)
- [EVCC Forecast.Solar](https://docs.evcc.io/de/tariffs/forecast-solar)
- [Telegraf influxdb_v2_listener](https://docs.influxdata.com/telegraf/v1/input-plugins/influxdb_v2_listener/)
- [Telegraf HTTP output](https://docs.influxdata.com/telegraf/v1/output-plugins/http/)
- [Telegraf output data formats](https://docs.influxdata.com/telegraf/v1/data_formats/output/)
