# VictoriaMetrics-Rollup-Design

Englische Version: [victoriametrics-rollup-design.md](../../en/design/victoriametrics-rollup-design.md).

Dieses Dokument beschreibt das akzeptierte VictoriaMetrics-Rollup-Design fuer EVCC-Langzeitdashboards.

## Ziele

- Rohe EVCC-Daten in VictoriaMetrics unveraendert lassen.
- Monats-, Jahres- und All-time-Dashboards auf Single-Node-Setups schnell halten.
- Das Betriebsmodell einfach genug fuer Endnutzer halten.

## Aktueller Plattformzustand

Wichtiges historisches Detail:

- importierte Influx-Historie ist in VictoriaMetrics ohne stabiles `host`-Label verfuegbar
- Live-Telegraf-Schreibzugriffe koennen `host` enthalten
- dieses Repository nimmt an, dass eine VictoriaMetrics-Instanz exakt einer EVCC-Instanz dediziert ist
- deshalb duerfen VM-Historienqueries und Dashboards weder von `host` noch von einem kuenstlichen gemeinsamen `db`-Label abhaengen

## Akzeptierte Entscheidung

Ein VictoriaMetrics-Server wird sowohl fuer Rohdaten als auch fuer Rollups genutzt.

Dieses Repository nimmt an, dass dieser VictoriaMetrics-Server genau einer EVCC-Instanz gewidmet ist. Wenn mehrere EVCC-Instanzen betrieben werden, sollen mehrere VictoriaMetrics-Instanzen betrieben werden.

Keine separate VM-Instanz fuer Rollups anlegen.

Standardmaessig keine separate Grafana-Datasource fuer Rollups anlegen.

Rohmetriken nicht ueberschreiben.

Rollups als neue Metriken im Produktionsnamespace schreiben:

- `evcc_*`

## Warum nicht das Influx-Setup 1:1 kopieren

Der Legacy-Influx-Pfad materialisierte taegliche und monatliche Measurements, weil rohe Dashboardqueries in InfluxDB zu teuer wurden und die Zielhardware begrenzt war. Die verbleibende Referenz ist das originale deutsche Dashboard-Set unter `dashboards/influx-legacy/original/de`.

VictoriaMetrics veraendert den Tradeoff:

- Rohdatenqueries sind bereits ausreichend schnell
- taegliche Rollups sind deutlich schneller als rohe Neuberechnung
- taegliche Rollups halten das Datenvolumen auch bei langer Retention klein

Deshalb ist das akzeptierte Standarddesign:

- Rohmetriken fuer `Today*`
- taegliche Rollups fuer `Monat`, `Jahr`, `All-time`
- monatliche Rollups spaeter optional, aber nicht initial erforderlich

## Empfohlene Architektur

### Layer 1: Rohmetriken

Alle eingehenden EVCC-Metriken unveraendert behalten.

Diese bleiben Source of Truth fuer:

- `Today`
- `Today - Details`
- `Today - Mobile`
- Debugging
- spaetere Neuberechnung von Rollups

Beispiele:

- `pvPower_value`
- `homePower_value`
- `chargePower_value`
- `batterySoc_value`

### Layer 2: taegliche Rollups

Taegliche Rollup-Metriken fuer Langzeitdashboards erzeugen.

Beispiele:

- `evcc_pv_energy_daily_wh`
- `evcc_home_energy_daily_wh`
- `evcc_grid_import_daily_wh`
- `evcc_grid_export_daily_wh`
- `evcc_loadpoint_energy_daily_wh{loadpoint="..."}`
- `evcc_vehicle_energy_daily_wh{vehicle="..."}`
- `evcc_vehicle_distance_daily_km{vehicle="..."}`
- `evcc_consumer_energy_daily_wh{title="..."}`
- `evcc_ext_energy_daily_wh{title="..."}`
- `evcc_aux_energy_daily_wh{title="..."}`
- `evcc_battery_soc_daily_min_pct`
- `evcc_battery_soc_daily_max_pct`
- `evcc_green_share_home_daily_ratio`

### Layer 3: optionale monatliche Rollups

Monatliche Rollups nur hinzufuegen, wenn ein gemessener Dashboard-Flaschenhals sie erforderlich macht.

## Benennungs- und Labelregeln

- Prometheus-artige Metriknamen verwenden.
- VM-Historie direkt ueber Metriknamen und Fachlabels abfragen; kein kuenstliches `db`-Label wird vorausgesetzt.
- Fuer EVCC-Historie nicht von einem `host`-Label abhaengen.
- Einheiten in Metriknamen kodieren.
- Nur echte Dimensionen als Labels behalten.
- `local_year` und `local_month` auf taeglichen Rollups verwenden, wenn lokale Kalenderfilter Grafana-Queries deutlich vereinfachen.
- Keine Labels `local_day` oder `local_date` hinzufuegen.

## Grafana-Modell

Standardmaessig eine VM-Datasource in Grafana verwenden.

Dashboard-Nutzung:

- `Today*`-Dashboards fragen Rohmetriken ab
- `Monat`, `Jahr`, `All-time` fragen taegliche Rollups ab

## Tooling-Entscheidung

### Standardpfad fuer Endnutzer

Eine kleine Python-CLI direkt in `scripts/` bereitstellen.

Warum:

- einfach auf jedem Linux-Host mit Python zu installieren
- einfacher zu dokumentieren
- einfacher remote auszufuehren, wenn VictoriaMetrics nicht auf demselben Host laeuft
- einfacher fuer lange einmalige Backfills in sichtbaren Monatsbloecken mit Shell-Fortschritt

## Sicherheitsregeln

1. Rohe EVCC-Metriken niemals loeschen oder veraendern.
2. Rollups niemals in bestehende Rohmetriknamen schreiben.
3. Tests read-only halten, ausser der Nutzer genehmigt explizit das Schreiben von Rollups.
4. Kandidatenqueries vor groesseren Dashboard-Umverdrahtungen benchmarken.

## Umsetzungshinweise fuer das Dashboard-Projekt

### Erforderliche Baseline

- produktive VM-Dashboards nutzen eine Datasource: `VM-EVCC`
- Historienqueries nutzen direkte Metrikselektoren und Fachlabels
- kein produktives Dashboard darf von `host` abhaengen
- Langzeitdashboards sollen gegen taegliche Rollups implementiert werden

### Migrationsstrategie fuer Dashboards

1. `Today*`-Dashboards auf Rohmetriken belassen.
2. VM-Versionen von `Monat`, `Jahr` und `All-time` gegen taegliche Rollups bauen.
3. Monatliche Rollups nur nach gemessener Dashboard-Regression einfuehren.

### Legacy-Kompatibilitaetshinweis

Die Influx-Legacy-Dashboards bleiben nur als statische deutsche Referenz-JSON erhalten. VM-Dashboards sollten ihre Struktur nicht blind kopieren.

## Performance- und Scheduler-Validierung

Der Release-Kandidat wurde am 2026-07-28 in einer isolierten VictoriaMetrics-Kopie mit vollstaendigen read-only Live-Rohdaten von 2025-01-01 bis 2026-07-27 geprüft:

- Der Voll-Backfill verarbeitete 573 Tage, 36.625 Samples und 1.388 Serien in 210,606 Sekunden bei 1.264 MB Python-Spitzenspeicher.
- Die Consumer-Quellenzuordnung war mit 90,737 Sekunden beziehungsweise 43,08% die langsamste Familie; die Fahrzeugkosten folgten mit 68,47 Sekunden.
- Eine fachlich korrekte Python-Matrix-Kanonisierung wurde verworfen, weil sie 258,392 Sekunden und 1.751 MB benötigte. Die endgültige Query-Kanonisierung spart gegenüber diesem Zwischenstand rund 18% Laufzeit und 28% Speicher.
- Ein Juli-Ersatzlauf mit 27 Tagen lief in etwa 13 Sekunden. Dieser Monatsbereich entspricht dem normalen Scheduler-Pfad wesentlich besser als der einmalige Voll-Backfill.
- Weitere Parallelisierung oder zusätzliche Caches sind kein Release-Gate: Der tägliche Lauf bleibt kurz, und zusätzliche Nebenläufigkeit würde Locking, Reihenfolge und Reproduzierbarkeit unnötig riskieren.

Der Scheduler bleibt bei `--replace-range --write` und darf standardmaessig nur abgeschlossene Tage verarbeiten. Ein gleichzeitig gestarteter zweiter Schreiblauf wurde im Livecopy-Test durch die Lock-Datei abgewiesen. Der Voll-Backfill meldete zwei ignorierte Counter-Resets, keine Leistungsspitzen und 9.910 fehlende Energie-Buckets. Die anschliessende Datenpruefung fand keine doppelten Label-/Tageskombinationen.

## Bekannte offene Punkte

- Eine optionale monatliche Rollup-Schicht wird erst nach einem erneut gemessenen Dashboard-Flaschenhals eingefuehrt.
- Weitere Performance-Arbeit beginnt nur mit einem reproduzierbaren Profil, das den normalen Scheduler-Zeitraum und die Zielhardware abbildet.

## Verbraucher-Quellenzuordnung

Die Quellenzuordnung fuer Consumer, AUX, EXT und Ladepunkte ist implementiert. Sie teilt die modellierte Tagesenergie in `PV`, `Battery` und `Grid` auf und verwendet 60-Sekunden-Buckets. Historische EXT-Verbraucher koennen per `consumer_legacy_ext_regex` fortgefuehrt werden; `consumer_title_aliases_json` vereinheitlicht umbenannte Consumer-Titel vor der Tagesintegration.

Die fachlichen Grenzen und Bilanzregeln stehen in:

- [Consumer Energy Attribution Design](./consumer-energy-attribution-design.md)