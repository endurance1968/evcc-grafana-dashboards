# VictoriaMetrics-Aggregationsanleitung

Englische Version: [victoriametrics-aggregation-guide.md](../../en/archive/victoriametrics-aggregation-guide.md).

Diese Anleitung beschreibt den Default-Rollup-Workflow fuer EVCC-Langzeitdashboards auf VictoriaMetrics.

Sie nimmt das aktuelle Repository-Layout an:

- VM ist der Default-Pfad
- die alten Influx-Dashboards bleiben nur als statische deutsche Referenz-JSON unter `dashboards/influx-legacy/original/de` erhalten

## Zweck

Die Rollup-CLI verwenden, um taegliche Rollup-Metriken vorzubereiten fuer:

- `Monat`
- `Jahr`
- `All-time`

Nicht fuer `Today*`-Dashboards verwenden. Diese lesen weiterhin rohe VM-Metriken.

## Dateien

- Skript: `scripts/rollup/evcc-vm-rollup.py`
- Beispielkonfiguration: `scripts/rollup/evcc-vm-rollup.conf.example`
- Design-Baseline: [victoriametrics-rollup-design.md](../design/victoriametrics-rollup-design.md)

## Aktueller Rollout-Umfang

Implementiert:

- taegliche PV-Energie
- taegliche Home-Energie
- taegliche Loadpoint-Energie
- taegliche Vehicle-Energie
- taegliche Vehicle-Distanz
- taegliche Ext-Energie
- taegliche Aux-Energie
- Batterie-Min-/Max-SOC pro Tag
- Grid-Import-/Export-Split
- Batterie-Lade-/Entlade-Split
- Tarif- und Finanzrollups, die von den aktuellen Dashboards benoetigt werden

Spaeter weiterhin optional:

- monatliche Rollups

## Installation

Das Tool auf jedem Linux-Host ausfuehren mit:

- Python 3.11 oder neuer
- HTTP-Zugriff auf VictoriaMetrics

Das Tool muss nicht auf dem VictoriaMetrics-Host selbst laufen.

## Konfiguration

Startpunkt:

```bash
cp scripts/rollup/evcc-vm-rollup.conf.example /etc/evcc-vm-rollup.conf
```

Wichtige Einstellungen:

- `base_url`
- eine VictoriaMetrics-Instanz ist einer EVCC-Instanz dediziert
- `timezone`
- `metric_prefix`: `evcc` verwenden
- `max_fetch_points_per_series`

Wichtige Regel:

- Workflow nicht um `host` herum bauen
- Historie und Live-Daten koennen sich bei Infrastruktur-Labels unterscheiden
- dieses Repository nimmt kein kuenstliches `db`-Label an
- wenn mehrere EVCC-Instanzen betrieben werden, mehrere VictoriaMetrics-Instanzen betreiben

## Erster Lauf

### 1. Dimensionen erkennen

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

### 2. Rollup-Plan pruefen

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

### 3. Rohdaten-Baseline benchmarken

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

## Backfill

### Dry-run

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress
```

### Echtes Schreiben

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress --write
```

### Default-Langzeitverhalten

`backfill` flusht standardmaessig monatsweise.

Das bedeutet:

- lange Laeufe zeigen sichtbaren Shell-Fortschritt
- Speichernutzung bleibt begrenzt
- Teillaeufe sind einfacher zu verstehen
- Fahrzeug-Odometer-Zustand wird ueber Monatsgrenzen hinweg mitgefuehrt

### Chunking

Die aktuelle Implementierung verarbeitet und flusht Backfills monatlich.

Normalen Backfill-Befehl verwenden:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day 2025-01-01 --end-day 2026-03-21 --progress --write
```

### Sicherheitsregeln

- nur `evcc_*`-Rollups schreiben
- Rohmetriken niemals ueberschreiben
- `backfill --write` schreibt nur abgeschlossene lokale Tage; heute und zukuenftige Tage werden abgelehnt, ausser der aktuelle Tag wird explizit fuer Diagnostik erlaubt
- Dashboards nach groesseren Rollup-Aenderungen validieren

## Produktionsrollout

1. Erforderlichen Produktionsbereich backfillen.
2. `Monat`, `Jahr` und `All-time`-Dashboards auf Produktions-Rollup-Metriken umstellen.
3. `Today*`-Dashboards auf Rohmetriken belassen.

## Empfohlenes Scheduler-Setup

Rollups sind Tageswerte. Den Refresh einmal pro Tag planen, nachdem `yesterday` abgeschlossen ist. Fuer Produktion `--replace-range` bevorzugen: den monatlichen Rollup-Bereich loeschen, der `yesterday` enthaelt, und danach diesen Monat bis `yesterday` neu aufbauen. Das macht den Refresh idempotent und vermeidet doppelte Samples mit denselben Serienlabels und Timestamps in VictoriaMetrics.

Schreibende `backfill`- und `delete`-Laeufe nehmen automatisch einen Lock. Ohne weitere Konfiguration liegt er bei `<config>.lock`; alternativ kann `[scheduler] lock_file = /var/lock/evcc-vm-rollup.lock` gesetzt oder `--lock-file ...` uebergeben werden. `--no-lock` ist nur fuer manuelle Wiederherstellung gedacht, wenn sicher kein anderer Rollup-Prozess laeuft.

Die Backfill-Zusammenfassung meldet die langsamsten Rollup-Familien, eine Optimierungsempfehlung und Datenqualitaetszaehler fuer ignorierte Counter-Resets, gefilterte Power-Spikes und fehlende Energie-Buckets. Der Scheduler-Pfad bleibt `--replace-range --write`; die Zaehlwerte gehoeren in das Rollup-Log und sollten nach Aenderungen oder auffaelligen Datenluecken geprueft werden.

Der Replace-Matcher schliesst optionale `evcc_vrm_*`-Hilfsmetriken aus. VRM-Energieflussimporte werden separat ueber ihren eigenen `--replace-range` gepflegt und nicht durch den Rollup-Scheduler geloescht.

Fuer Raspberry-Pi-aehnliche Deployments den Rollup-Job mindestens auf Raspberry Pi 4 mit 4 GB RAM oder vergleichbarer Hardware ausfuehren. Raspberry Pi 3 und 1-2-GB-Systeme werden fuer den monatlichen Replace-Pfad nicht empfohlen.

Cron-Beispiel:

```cron
5 5 * * * /usr/bin/python3 /opt/evcc-vm-tools/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill --start-day $(date -d 'yesterday' +\%Y-\%m-01) --end-day $(date -d 'yesterday' +\%F) --replace-range --write >> /var/log/evcc-vm-rollup.log 2>&1
```

Manueller Delete-Dry-run fuer einen monatlichen Rollup-Bereich:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf delete --start-day 2026-04-01 --end-day 2026-04-30
```

`--write` erst hinzufuegen, nachdem Matcher und Serienzahlen korrekt aussehen.

## Validierung

Nach jeder Schreibphase:

1. Neue `evcc_*`-Metriken direkt in VictoriaMetrics abfragen.
2. Zugehoerige Grafana-Dashboards oeffnen.
3. Repraesentative Zeitraeume gegen die Legacy-Influx-Referenzdashboards vergleichen.
4. Screenshots aufnehmen, wenn sich das Dashboard-Set sichtbar geaendert hat.

## Troubleshooting

Wenn Dashboards doppelte Serien zeigen:

- auf instabile Infrastruktur-Labels wie `host` pruefen
- verifizieren, dass das Rollup-Design nur Fachlabels behaelt
- bestaetigen, dass Dashboardqueries Nicht-Fachlabels bei Bedarf wegaggregieren

Wenn ein Langzeitdashboard weiterhin langsam wirkt:

- pruefen, ob es tatsaechlich Rollup-Metriken liest
- Kandidaten-Roh- und Rollupqueries erneut benchmarken
- monatliche Rollups erst hinzufuegen, wenn ein real gemessener Flaschenhals existiert

## Legacy-Hinweis

Das alte Influx-Dashboard-Set bleibt nur als statische deutsche Referenz-JSON unter `dashboards/influx-legacy/original/de` erhalten.
