# VictoriaMetrics Handoff

Stand: 2026-03-21

Diese Notiz ist die Uebergabe an den parallelen Grafana-Dashboard-Thread, in dem die Uebersetzung und Weiterentwicklung der VictoriaMetrics-Dashboards laeuft.

## Kontext

- Legacy-Dashboards auf InfluxDB sollen vorerst erhalten bleiben.
- Parallel dazu werden VictoriaMetrics-Dashboards aufgebaut.
- Die Datenpipeline laeuft ueber Telegraf im Fan-out-Modell nach:
  - InfluxDB
  - VictoriaMetrics
  - PostgreSQL

## Wichtige Betriebsdetails

- `evcc` schreibt per Influx-v2-API nach Telegraf, nicht per Influx-v1-API.
- Die praktische Ursache wurde per `tcpdump` bestaetigt:
  - `POST /api/v2/write?bucket=evcc&org=&precision=s`
- Fuer die Test-Grafana ist das VictoriaMetrics-Plugin inzwischen installiert und aktiv.

## VictoriaMetrics Test-Grafana

- Grafana URL: `http://192.168.1.189:3000`
- Datasource:
  - Name: `VM-EVCC`
  - UID: `vm-evcc`
  - Typ: `victoriametrics-metrics-datasource`
  - URL: `http://192.168.1.160:8428`
- Health-Check der Datasource: `OK`

## Importierte Test-Dashboards

Aktuell importiert und auf der Testinstanz sichtbar:

- `vm-en-adsmz7v` -> `[VM-EN] VM: EVCC: Today`
- `vm-en-adtcx74` -> `[VM-EN] VM: EVCC: Today - Mobile`
- `vm-en-adddvtj` -> `[VM-EN] VM: EVCC: Today - Details`

## Repo-Status

- Arbeitsbranch fuer den englischen VM-Stand:
  - `codex/victoriametrics-en`
- Bereits gepushte Commits auf diesem Branch:
  - `666cf7a` `feat: import victoria metrics dashboard sources`
  - `7b4dee3` `docs: add telegraf parallel pipeline howto`

## Wichtige Einschränkung des Upstreams

- Der Branch `upstream/victoria-metrics` liefert derzeit nur drei VM-Dashboards.
- Diese drei Dateien sind nicht vollstaendig englisch, sondern enthalten noch deutlich sichtbare deutsche Labels und Beschreibungen.
- Die importierten Dateien liegen im Repo unter:
  - `dashboards/original/en/`
- Sie sind dort bewusst als Upstream-Snapshot abgelegt und nicht als fertig lokalisierter Endstand zu verstehen.

## Historischer Datenstand in VM

- Historische Rohdaten aus Influx wurden erfolgreich testweise nach VictoriaMetrics importiert.
- Das problematische Measurement `batteryControllable` wurde vor dem Import geloescht.
- Ein Import fuer den Zeitraum `2026-03-20T00:00:00Z` bis `2026-03-21T00:00:00Z` lief erfolgreich.
- Historische Daten sind in den VM-Dashboards bereits sichtbar.

## Empfehlung fuer den Dashboard-Thread

1. Die drei vorhandenen VM-Dashboards als Arbeitsbasis nehmen.
2. Sichtbare deutsche Labels systematisch ins Englische ueberfuehren.
3. Den nativen Datasource-Typ `victoriametrics-metrics-datasource` beibehalten.
4. Keine Annahme treffen, dass `Monat`, `Jahr` und `All-time` bereits im Upstream fuer VM verfuegbar sind.
5. Aggregationsabhaengige Dashboards erst spaeter angehen, wenn das Aggregationsskript fuer VM sauber geklaert ist.
