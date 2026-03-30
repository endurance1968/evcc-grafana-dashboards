# Migration von InfluxDB zu VictoriaMetrics

Diese Anleitung beschreibt den kompletten Enduser-Weg von einer bestehenden EVCC-InfluxDB zu einem VictoriaMetrics-basierten Setup.

Annahmen:

- VictoriaMetrics ist bereits installiert und erreichbar
- EVCC schreibt bereits nach VictoriaMetrics oder soll danach dorthin schreiben

Nicht Bestandteil dieser Anleitung:

- Installation von VictoriaMetrics selbst
- Installation von Grafana selbst
- Deployment der Grafana-Dashboards

## Zielbild

Nach der Migration gibt es zwei Datenebenen:

- Rohdaten in VictoriaMetrics
  - Basis für `Today`, `Today - Mobile`, `Today - Details`
- tägliche Rollups im Namespace `evcc_*`
  - Basis für `Monat`, `Jahr`, `All-time`

Wichtig:

- Rohdaten werden nicht überschrieben
- Rollups werden zusätzlich erzeugt
- `Today*` bleibt auf Rohdaten

## Was du brauchst

- Python 3.11 oder neuer
- HTTP-Zugriff auf InfluxDB v1 Query API
- HTTP-Zugriff auf VictoriaMetrics

Praktische Minimalvoraussetzungen auf Linux:

```bash
sudo apt update
sudo apt install -y python3 curl
```

## Benötigte Dateien herunterladen

Arbeitsverzeichnis anlegen:

```bash
mkdir -p /opt/evcc-vm-migration
cd /opt/evcc-vm-migration
```

Benötigte Dateien herunterladen:

```bash
curl -fsSLo reimport_influx_to_vm.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/helper/reimport_influx_to_vm.py
curl -fsSLo evcc-vm-rollup.py https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.py
curl -fsSLo evcc-vm-rollup-prod.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup-prod.conf.example
```

Optional zusätzlich die allgemeine Beispiel-Config:

```bash
curl -fsSLo evcc-vm-rollup.conf.example https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main/scripts/rollup/evcc-vm-rollup.conf.example
```

## Verwendete Dateien

- Rohdaten-Reimport:
  - `reimport_influx_to_vm.py`
- Rollup-Engine:
  - `evcc-vm-rollup.py`
- Rollup-Config:
  - `evcc-vm-rollup-prod.conf.example`

## Schritt 1: VictoriaMetrics und EVCC prüfen

Bevor du Daten umziehst, prüfe:

- VictoriaMetrics antwortet:

```bash
curl -fsSL http://<vm-host>:8428/health
```

- die Ziel-Datasource in Grafana zeigt später auf VictoriaMetrics
- EVCC soll am Ende ebenfalls nach VictoriaMetrics schreiben

Wenn EVCC noch parallel nach InfluxDB schreibt, ist das für die Übergangszeit ok.

## Schritt 2: Rohdaten einmalig von InfluxDB nach VictoriaMetrics übernehmen

Der Helper importiert numerische Influx-Messungen direkt nach VictoriaMetrics.

Wichtig:

- der aktuelle Helper nutzt die InfluxDB-v1-Query-API
- er erwartet direkten HTTP-Zugriff ohne Auth-Header-Handling im Script
- falls deine InfluxDB Auth verlangt, brauchst du entweder einen lokalen Proxy/Tunnel oder du musst das Script dafür erweitern

### 2.1 Erst als Dry-Run testen

Beispiel:

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z \
  --dry-run
```

Der Dry-Run zeigt dir:

- wie viele Measurements erkannt wurden
- wie viele Serien und Punkte importiert würden

### 2.2 Danach echten Import starten

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z
```

Optional für einzelne Measurements:

```bash
python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://<vm-host>:8428 \
  --db evcc \
  --measurement pvPower \
  --start 2024-01-01T00:00:00Z \
  --end 2026-03-30T00:00:00Z
```

### 2.3 Rohdaten verifizieren

Direkt in VictoriaMetrics prüfen:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value{db="evcc"}' \
  --data-urlencode 'start=2026-03-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-02T00:00:00Z'
```

Wenn hier Daten zurückkommen, ist die Rohdatenbasis ok.

## Schritt 3: Rollup-Konfiguration anlegen

Produktive Config aus dem Beispiel ableiten:

```bash
sudo cp evcc-vm-rollup-prod.conf.example /etc/evcc-vm-rollup.conf
sudo editor /etc/evcc-vm-rollup.conf
```

Wichtige Felder:

- `base_url`
  - URL deiner VictoriaMetrics-Instanz
- `db_label`
  - normalerweise `evcc`
- `timezone`
  - z. B. `Europe/Berlin`
- `metric_prefix`
  - produktiv `evcc`
- `price_bucket_minutes`
  - typischerweise `15` bei dynamischen Tarifen
- `max_fetch_points_per_series`
  - begrenzt, wie viele Rohdatenpunkte pro Zeitreihe in einem einzelnen Fetch geholt werden

Empfohlener produktiver Kern:

```ini
[victoriametrics]
base_url = http://<vm-host>:8428
db_label = evcc
host_label =
timezone = Europe/Berlin
metric_prefix = evcc
raw_sample_step = 10s
energy_rollup_step = 60s
price_bucket_minutes = 15
max_fetch_points_per_series = 28000
```

Wichtig:

- `metric_prefix = evcc` erzeugt produktive Rollups wie `evcc_pv_energy_daily_wh`
- `host_label` leer lassen, solange du keinen sehr guten Grund hast
- Rollups sollen auf Business-Labels beruhen, nicht auf Infra-Labels

### Hintergrund zu `max_fetch_points_per_series`

Dieser Wert ist die wichtigste Stellschraube für das Gleichgewicht zwischen:

- RAM-Bedarf
- Anzahl der VM-Abfragen
- Gesamtlaufzeit des Rollups

Was er praktisch macht:

- der Rollup-Lauf holt Rohdaten nicht unendlich groß in einem Stück
- stattdessen werden große Zeiträume in mehrere Fetch-Blöcke zerlegt
- `max_fetch_points_per_series` setzt die Obergrenze pro Serie und pro Fetch

Wenn der Wert **größer** wird:

- es werden weniger einzelne HTTP-Abfragen an VictoriaMetrics nötig
- der Lauf wird oft schneller
- aber mehr Samples liegen gleichzeitig im Speicher

Wenn der Wert **kleiner** wird:

- es werden mehr einzelne Fetches nötig
- der Lauf wird langsamer
- aber der Speicherbedarf sinkt

Faustregel:

- stärkere Hosts:
  - Wert eher höher lassen
- kleine Systeme wie Raspi:
  - bei RAM-Problemen eher schrittweise reduzieren

Der Default `28000` ist ein pragmatischer Mittelwert:

- groß genug für gute Laufzeit
- klein genug, damit der Rollup-Lauf nicht unnötig speicherhungrig wird

Nur anpassen, wenn es dafür einen echten Grund gibt:

- OOM-/RAM-Probleme
- ungewöhnlich langsame Backfills
- sehr lange Rohdatenhistorie bei schwacher Hardware

Wenn du testweise anpasst, dann in kleinen Schritten, zum Beispiel:

- `28000`
- `20000`
- `15000`

und danach Laufzeit und Peak-RAM erneut messen.

## Schritt 4: Rollup vor dem Schreiben prüfen

### 4.1 Dimensionen erkennen

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
```

### 4.2 Rollup-Plan ansehen

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
```

### 4.3 Rohdaten-Benchmark laufen lassen

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

Das ist sinnvoll, weil du damit früh erkennst:

- ob die Rohdaten überhaupt lesbar sind
- ob die Query-Laufzeiten vertretbar sind
- ob `max_fetch_points_per_series` für deine Hardware passt

## Schritt 5: Einmaligen Initial-Backfill der Rollups ausführen

Jetzt werden die täglichen Rollups im Namespace `evcc_*` erzeugt.

### 5.1 Erst Dry-Run

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress
```

### 5.2 Danach echter Write-Run

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress \
  --write
```

Hinweise:

- der Backfill wird intern monatsweise verarbeitet und geschrieben
- Januar wird also als eigener Block berechnet, dann Februar, dann März usw.
- der Rollup-Lauf hält dadurch nicht den kompletten Gesamtzeitraum gleichzeitig im Speicher
- das hält Speicherbedarf und Fortschritt überschaubar
- der Lauf schreibt nur `evcc_*`
- Rohdaten bleiben unangetastet

## Schritt 6: Rollups verifizieren

Nach dem Initial-Backfill direkt prüfen:

```bash
curl -fsG 'http://<vm-host>:8428/api/v1/query' \
  --data-urlencode 'query=sum(evcc_pv_energy_daily_wh{db="evcc"})'
```

Zusätzlich sinnvoll:

- Plausibilitätscheck gegen bekannte Zeiträume
- bei Bedarf Vergleich mit bekannten Altwerten aus Influx

## Schritt 7: Laufenden Rollup-Betrieb einrichten

Die Rollups sind tägliche Kennzahlen. Damit aktuelle Tage sauber nachlaufen, solltest du den aktuellen Tag regelmäßig neu berechnen.

Empfehlung:

- **stündlich** den Zeitraum `gestern + heute` neu rechnen

Warum nicht nur `heute`:

- Messwerte können leicht verspätet eintreffen
- Mitternacht und Zeitzone sind robuster
- kleine Nachkorrekturen vom Vortag werden gleich mitgenommen

### 8.1 Manueller stündlicher Refresh

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day $(date -d 'yesterday' +%F) \
  --end-day $(date +%F) \
  --write
```

### 8.2 Empfohlene systemd-Variante

Service:

```ini
[Unit]
Description=EVCC VictoriaMetrics hourly rollup refresh

[Service]
Type=oneshot
WorkingDirectory=/opt/evcc-vm-migration
ExecStart=/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill-test --start-day %%YESTERDAY%% --end-day %%TODAY%% --write
```

Die Datumswerte müssen bei systemd über ein Wrapper-Skript gesetzt werden. Deshalb ist in der Praxis diese Variante einfacher:

Wrapper `/usr/local/bin/evcc-vm-rollup-hourly.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill-test \
  --start-day \"$(date -d 'yesterday' +%F)\" \
  --end-day \"$(date +%F)\" \
  --write
```

Ausführbar machen:

```bash
sudo chmod +x /usr/local/bin/evcc-vm-rollup-hourly.sh
```

Service-Datei `/etc/systemd/system/evcc-vm-rollup-hourly.service`:

```ini
[Unit]
Description=EVCC VictoriaMetrics hourly rollup refresh

[Service]
Type=oneshot
ExecStart=/usr/local/bin/evcc-vm-rollup-hourly.sh
```

Timer-Datei `/etc/systemd/system/evcc-vm-rollup-hourly.timer`:

```ini
[Unit]
Description=Run EVCC VictoriaMetrics rollup refresh hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now evcc-vm-rollup-hourly.timer
systemctl list-timers | grep evcc-vm-rollup-hourly
```

### 8.3 Einfache cron-Alternative

```cron
7 * * * * /usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf backfill-test --start-day $(date -d 'yesterday' +\%F) --end-day $(date +\%F) --write >> /var/log/evcc-vm-rollup.log 2>&1
```

## Schritt 8: Nach der Migration InfluxDB aus dem Schreibpfad entfernen

Sobald du sicher bist, dass:

- Rohdaten sauber in VictoriaMetrics ankommen
- Rollups laufen

sollte EVCC nicht mehr parallel für den Dashboard-Betrieb an InfluxDB gebunden sein.

Die alte InfluxDB kannst du dann:

- nur noch als Backup/Referenz stehen lassen
- oder später ganz abschalten

## Was man leicht vergisst

- Grafana-Datasource muss auf VictoriaMetrics zeigen, nicht mehr auf Influx
- `Today*` und Langfrist-Dashboards arbeiten auf unterschiedlichen Datenebenen
- `metric_prefix` muss produktiv `evcc` sein, nicht `test_evcc`
- der Reimport ersetzt keine laufenden Rollups
- der Rollup-Lauf braucht einen Scheduler, sonst bleiben `Monat/Jahr/All-time` stehen
- der aktuelle Reimport-Helper kann nicht von selbst mit Influx-Auth umgehen
- bei Problemen zuerst Rohdaten prüfen, dann Rollups

## Reimport-Script vs. vmctl messen, ohne die produktive VM zu verändern

Die kurze Einschätzung:

- `vmctl` wird sehr wahrscheinlich **deutlich schneller** sein als `reimport_influx_to_vm.py`
- Grund:
  - `vmctl` ist genau für Massentransfers gebaut
  - unterstützt Concurrency, Kompression und große Batches
  - laut offizieller VictoriaMetrics-Doku ist die Geschwindigkeit vor allem durch InfluxDB-Leseleistung und die eingestellte Parallelität begrenzt

Wichtiger als die absolute Vermutung ist aber ein sauberer Testaufbau.

### Sicherer Messaufbau

Nicht gegen die produktive VictoriaMetrics-Instanz messen.

Stattdessen:

1. zweite temporäre VictoriaMetrics-Instanz starten
2. beide Importe dorthin schreiben
3. Laufzeit und Datenmenge vergleichen

Beispiel mit einer separaten Single-Node-Instanz:

```bash
mkdir -p /tmp/vm-bench-data
victoria-metrics-prod -storageDataPath=/tmp/vm-bench-data -httpListenAddr=:18428
```

Wichtig:

- anderer Port, z. B. `18428`
- eigener leerer Datenpfad
- keine Verbindung zur produktiven VM

### Messung mit dem Python-Reimport-Script

```bash
/usr/bin/time -v python3 reimport_influx_to_vm.py \
  --influx-base http://<influx-host>:8086 \
  --vm-base http://127.0.0.1:18428 \
  --db evcc \
  --start 2025-01-01T00:00:00Z \
  --end 2025-02-01T00:00:00Z
```

Messen:

- Wall clock time
- CPU time
- Max RSS
- importierte Serien/Punkte aus der Script-Ausgabe

### Messung mit vmctl

Offiziell unterstützt laut VictoriaMetrics-Doku:

- `vmctl influx --influx-addr ... --influx-database ... --vm-addr ...`

Beispiel:

```bash
/usr/bin/time -v vmctl influx \
  --influx-addr=http://<influx-host>:8086 \
  --influx-database=evcc \
  --influx-filter-time-start=2025-01-01T00:00:00Z \
  --influx-filter-time-end=2025-02-01T00:00:00Z \
  --vm-addr=http://127.0.0.1:18428 \
  -s
```

Offizielle Quelle:

- [VictoriaMetrics vmctl](https://docs.victoriametrics.com/victoriametrics/vmctl/)
- [VictoriaMetrics vmctl InfluxDB](https://docs.victoriametrics.com/victoriametrics/vmctl/influxdb/)

### Fair vergleichen

Für einen fairen Vergleich:

- denselben Zeitraum verwenden
- dieselbe InfluxDB-Quelle verwenden
- vor jedem Lauf die temporäre VM wieder leeren
- zuerst klein anfangen:
  - 1 Tag
  - 7 Tage
  - 30 Tage
- erst danach einen großen Vergleich fahren

Temporäre VM zwischen den Läufen zurücksetzen:

```bash
rm -rf /tmp/vm-bench-data
mkdir -p /tmp/vm-bench-data
```

Danach VM neu starten.

### Was dabei herauskommt

Danach hast du:

- echte Laufzeit pro Importweg
- echten RAM-Bedarf
- echte importierte Sample-/Serienmengen
- keine Verfälschung deiner produktiven VictoriaMetrics-Instanz

### Empfehlung

Für den normalen Migrationsweg:

- zuerst den vorhandenen Python-Reimport nutzen, weil er schon im Repo liegt
- `vmctl` nur dann zusätzlich benchmarken, wenn:
  - der Rohdatenimport sehr groß ist
  - oder die Laufzeit des Python-Scripts unattraktiv wird

## Empfohlene Reihenfolge in kurz

1. VictoriaMetrics prüfen
2. Rohdaten aus Influx einmalig nach VictoriaMetrics importieren
3. Rohdaten in VictoriaMetrics verifizieren
4. Rollup-Config produktiv anlegen
5. `detect`, `plan`, `benchmark`
6. Initialen Rollup-Backfill mit `--write` fahren
7. Rollups verifizieren
8. stündlichen Rollup-Job einrichten
9. Influx nur noch als Altbestand/Referenz behalten

