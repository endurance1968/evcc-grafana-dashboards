# Systemanforderungen

Englische Version: [system-requirements_EN.md](./system-requirements_EN.md).

Nutze diese Seite vor der Installation von VictoriaMetrics, Grafana oder den EVCC-Dashboards. Die Befehle bleiben in den jeweiligen Installations- und Migrationsanleitungen; diese Seite sammelt nur die Voraussetzungen an einer Stelle.

## Unterstuetztes Setup

Empfohlene produktive Zielstruktur:

- eine VictoriaMetrics-Instanz pro EVCC-Instanz
- eine Grafana-Instanz mit VictoriaMetrics-Datasource-Plugin
- EVCC-Rohmetriken werden direkt von EVCC oder ueber Telegraf im Influx-Line-Protocol nach VictoriaMetrics geschrieben
- taegliche `evcc_*`-Rollups werden durch `evcc-vm-rollup.py` erzeugt

Mehrere EVCC-Systeme sollten nicht ueber ein kuenstliches `db`-Label in eine gemeinsame VictoriaMetrics-Instanz gemultiplext werden. Dashboards und Rollup-Werkzeuge erwarten einen dedizierten VictoriaMetrics-Namespace pro EVCC-System.

## Mindestversionen zur Laufzeit

| Komponente | Anforderung | Hinweise |
| --- | --- | --- |
| VictoriaMetrics | aktuelle Single-Node-Version aus der Installationsanleitung | Die Debian-Anleitung validiert aktuell `v1.139.0`; die Docker-Anleitung kann einen eigenen getesteten Image-Tag pinnen. |
| `vmctl` | gleiche VictoriaMetrics-Release-Familie wie die Ziel-VictoriaMetrics-Version | Wird fuer die InfluxDB-Historienmigration benoetigt. |
| Grafana | 13.0.1 oder neuer | Erforderlich. Die deploybaren Dashboards nutzen Grafana-13-Tab-Navigation als Default. Nutzer koennen die Dashboard-Darstellung in Grafana bei Bedarf auf Rows umschalten; Row-Modus wird nur nicht mehr als separate Deploy-Variante gepflegt. |
| Grafana-Plugin | `victoriametrics-metrics-datasource` | Erforderlich fuer die Datasource `vm-evcc`. |
| Python | 3.11 oder neuer | Benoetigt fuer Migrationschecks, Label-Bereinigung und Rollups. |
| Docker | aktuelle Docker Engine oder Docker Desktop | Nur fuer den Docker-Installationspfad oder disposable Validierungscontainer benoetigt. |
| Debian | Debian 13 fuer die Debian-Installationsanleitungen | Debian 13 ist die validierte Linux-Basis fuer die aktuelle Release-Vorbereitung. |

## Hardware-Groesse

Kleine EVCC-Setups sind nicht stark CPU-lastig, aber der historische Rollup-Lauf kann speicherintensiv sein.

Empfohlenes Minimum fuer einen normalen Produktionshost:

- 2 CPU-Kerne
- 4 GB RAM
- persistente SSD oder zuverlaessiger Flash-Speicher
- ausreichend Plattenplatz fuer die importierte InfluxDB-Historie plus VictoriaMetrics-Retention

Fuer Raspberry-Pi-aehnliche Systeme:

- Raspberry Pi 4 mit 4 GB RAM oder vergleichbare Hardware ist das praktische Minimum
- Raspberry Pi 3 und Systeme mit 1-2 GB RAM werden fuer den monatlichen `--replace-range`-Rollup-Pfad nicht empfohlen

Beobachtete Referenz aus der realen Migrationsvalidierung:

- Rohdatenimport: etwa 5,3 GB von InfluxDB nach VictoriaMetrics uebertragen
- Rollup-Backfill: etwa 1,25 GB Spitzen-RAM des Python-Prozesses auf einer realen mehrjaehrigen EVCC-Historie

Plane zusaetzlichen Speicher fuer Betriebssystem, VictoriaMetrics, Grafana, Telegraf und weitere Dienste auf demselben Host ein.

## Netzwerk und Ports

| Dienst | Standard-Port | Zweck |
| --- | --- | --- |
| VictoriaMetrics | `8428` | API, Ingest, VMUI, Ziel der Grafana-Datasource |
| Grafana | `3000` | Dashboard-UI und API |
| InfluxDB-v1-Quelle | `8086` | Read-only-Quelle waehrend der Historienmigration |
| Telegraf-Listener | meist `8086` | Optionaler Live-Fan-out-Endpunkt fuer EVCC-Schreibzugriffe |
| EVCC UI/API | meist `7070` | Optionaler Dashboard-Link und manuelle Topologiepruefung |

Grafana muss VictoriaMetrics erreichen koennen. In Docker Desktop zeigt `localhost` innerhalb des Grafana-Containers auf Grafana selbst. Nutze `host.docker.internal` oder einen gemeinsamen Docker-Netzwerknamen fuer die VictoriaMetrics-Datasource-URL.

Wenn EVCC oder Telegraf von einem anderen Host schreibt, nutze die Host-IP oder den DNS-Namen von VictoriaMetrics, nicht `localhost`.

## Anforderungen an Datenpfade

VictoriaMetrics benoetigt persistenten Speicher:

- Debian-Anleitung: `/var/lib/victoria-metrics`
- Docker-Anleitung: ein Host-gemountetes Volume wie `/opt/victoriametrics/data` oder `C:\evcc\victoriametrics\data`

Grafana benoetigt ebenfalls persistenten Speicher fuer Nutzer, Datasources, Ordner und Dashboards:

- Debian-Paket: durch die Grafana-Paketpfade verwaltet
- Docker-Anleitung: ein Host-gemountetes Volume wie `/opt/grafana/data` oder `C:\evcc\grafana\data`

Produktionsdaten sollten nicht auf disposable Container-Storage liegen, ausser sie koennen bewusst und vollstaendig neu erzeugt werden.

## Anforderungen an Label-Hygiene

Live- und migrierte VictoriaMetrics-Daten duerfen keine Infrastruktur-Labels enthalten, die Dashboard-Gruppierungen veraendern.

Erforderlich:

- EVCC-Fachlabels wie `loadpoint`, `vehicle`, `id` und `title` behalten
- kuenstliche `db`-Labels in VictoriaMetrics vermeiden
- von Telegraf hinzugefuegte `host`-Labels vermeiden, indem in der Telegraf-Section `[agent]` `omit_hostname = true` gesetzt wird
- fuer Telegraf-zu-VictoriaMetrics `[[outputs.http]]` mit `data_format = "influx"` verwenden

Nutze in diesem Dashboard-Stack nicht `[[outputs.influxdb]]` fuer VictoriaMetrics. Das kann ein `db`-Label erzeugen und das erwartete Modell eine EVCC-Instanz pro VictoriaMetrics-Instanz brechen.

## Migrationsanforderungen

Fuer eine InfluxDB-zu-VictoriaMetrics-Migration brauchst du:

- Lesezugriff auf die vorhandene InfluxDB-v1-Query-API
- Schreibzugriff auf die neue VictoriaMetrics-Instanz
- `vmctl`
- Python 3.11 oder neuer
- ausreichend Zeit und Plattenplatz fuer den vollstaendigen ausgewaehlten Historienzeitraum

Nutze ein geschlossenes Import- und Vergleichsfenster. Wenn EVCC waehrend des Imports weiter nach InfluxDB schreibt, vergleiche bis zu einem abgeschlossenen Zeitpunkt, nicht gegen die laufende aktuelle Stunde.

## Grafana-Anforderungen

Grafana sollte haben:

- VictoriaMetrics-Datasource-UID `vm-evcc` oder der Deployer muss mit der tatsaechlichen UID konfiguriert werden
- Datasource-URL zeigt aus Grafanas Sicht auf VictoriaMetrics
- Service-Account-Token oder lokale Admin-Zugangsdaten fuer das Dashboard-Deployment
- Ordner `EVCC` fuer die deployten Dashboards

Die Deployer installieren immer die Grafana-13-Tab-Navigation-Dashboards aus der festen Manifest-Dateiliste. Nutzer koennen die Dashboard-Darstellung in Grafana bei Bedarf auf Rows umschalten; Row-Modus wird nur nicht mehr als separate Deploy-Variante gepflegt. Dashboard-Set-Auswahl wird nicht mehr unterstuetzt.

Grafana-Versionen vor 13.0.1 werden vom Deploy-Manifest nicht mehr unterstuetzt.

## Validierung nach der Installation

Mindestens pruefen:

- VictoriaMetrics `/health` liefert `OK`
- Grafana `/api/health` liefert `database: ok`
- Grafana-Datasource-Healthcheck liefert `Data source is working`
- EVCC/Telegraf Live-Ingest liefert aktuelle Rohmetriken nach VictoriaMetrics
- `check_data.py` meldet erforderliche Rohmetriken und keine `host`- oder `db`-Label-Probleme
- `compare_import_coverage.py` meldet keine fuer dieses Repository relevanten Importprobleme
- Rollup-Backfill-Dry-run liefert `GO`, bevor `--write` ausgefuehrt wird
- Dashboards sind im Ordner `EVCC` sichtbar

## Naechste Schritte

- VictoriaMetrics: [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) oder [victoriametrics-install-docker.md](./victoriametrics-install-docker.md)
- bei vorhandener InfluxDB-Historie: [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- Live-Ingest als Abschluss der VictoriaMetrics-Installation oder Migration: [evcc-telegraf-live-ingest.md](./evcc-telegraf-live-ingest.md)
- Grafana: [grafana-install-debian-13.md](./grafana-install-debian-13.md) oder [grafana-install-docker.md](./grafana-install-docker.md)
- Dashboard-Deployment: [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)
