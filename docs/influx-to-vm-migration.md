# Migration von InfluxDB zu VictoriaMetrics

Englische Version: [influx-to-vm-migration_EN.md](./influx-to-vm-migration_EN.md).

Pruefe vor den Kommandos zuerst die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Dies ist der normale Endnutzer-Pfad von einem bestehenden EVCC + InfluxDB Setup zu VictoriaMetrics.

Diese Anleitung beschreibt bewusst nur den gruenen Pfad. Wenn eine Pruefung fehlschlaegt, nutze [migration-troubleshooting.md](./migration-troubleshooting.md). Hintergrund zur Release- und Energievalidierung steht in [migration-validation-notes.md](./migration-validation-notes.md).

## Zielzustand

Nach der Migration enthaelt VictoriaMetrics zwei Datenschichten:

- EVCC-Rohmetriken, genutzt von `Today`, `Today - Mobile` und `Today - Details`
- taegliche `evcc_*` Rollups, genutzt von `Month`, `Year` und `All-time`

Die Rollup-Engine ueberschreibt keine EVCC-Rohmetriken. Sie schreibt zusaetzliche Tagesmetriken im Namespace `evcc_*`.

## Annahmen

- VictoriaMetrics ist installiert und erreichbar.
- `vmctl` ist installiert.
- Die InfluxDB-v1-Query-API ist erreichbar.
- Python 3.11 oder neuer ist vorhanden.
- Eine VictoriaMetrics-Instanz ist genau einer EVCC-Instanz zugeordnet.

Wenn VictoriaMetrics oder Grafana noch nicht installiert sind, starte mit [docs/README.md](./README.md).

## 1. Migrationsdateien herunterladen

Arbeitsverzeichnis anlegen:

```bash
mkdir -p /opt/evcc-vm-migration
cd /opt/evcc-vm-migration
```

Skripte herunterladen:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"

curl -fsSLo evcc-vm-rollup.py "$BASE/scripts/rollup/evcc-vm-rollup.py"
curl -fsSLo evcc-vm-rollup-prod.conf.example "$BASE/scripts/rollup/evcc-vm-rollup-prod.conf.example"
curl -fsSLo check_data.py "$BASE/scripts/helper/check_data.py"
curl -fsSLo compare_import_coverage.py "$BASE/scripts/helper/compare_import_coverage.py"
curl -fsSLo vm-rewrite-drop-label.py "$BASE/scripts/helper/vm-rewrite-drop-label.py"
```

Wenn du bewusst von einem selbst gehosteten Raw-Endpunkt herunterlaedst, nutze das Repository-Root-Raw-URL-Muster:

```bash
BASE="http://<server:port>/<reponame>/raw/branch/main"
```

Wenn du die Kommandos aus einem Repository-Checkout statt aus diesem Arbeitsverzeichnis ausfuehrst, nutze die Repository-Pfade, zum Beispiel `scripts/helper/check_data.py` und `scripts/rollup/evcc-vm-rollup.py`.

## 2. VictoriaMetrics pruefen

```bash
curl -fsSL http://localhost:8428/health
```

Erwartetes Ergebnis:

```text
OK
```

Ersetze `localhost` durch deinen VictoriaMetrics-Host, wenn das Kommando von einer anderen Maschine laeuft.

## 3. Rohdaten aus InfluxDB importieren

Nutze `vmctl influx`. Dadurch bleiben EVCC-Fachlabels wie `loadpoint`, `vehicle`, `id` und `title` erhalten.

Ohne InfluxDB-Authentifizierung:

```bash
vmctl influx \
  -s \
  --disable-progress-bar \
  --influx-addr='http://<influx-host>:8086' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

Mit InfluxDB-Authentifizierung:

```bash
vmctl influx \
  -s \
  --disable-progress-bar \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-time-start='2024-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-30T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

Wichtig:

- Behalte `--influx-skip-database-label` fuer das Standardmodell dieses Repositorys bei.
- Nutze kein synthetisches `db`-Label, um mehrere EVCC-Instanzen in eine VictoriaMetrics-Instanz zu multiplexen.
- Waehrend der Uebergangsphase kann EVCC weiter parallel nach InfluxDB schreiben.
- `-s --disable-progress-bar` macht den Import nicht-interaktiv und funktioniert auch, wenn `vmctl` in Docker oder einer anderen Non-TTY-Umgebung laeuft.
- Wenn `vmctl` in einem Docker-Container auf Docker Desktop laeuft und InfluxDB oder VictoriaMetrics auf dem Host veroeffentlicht sind, nutze `host.docker.internal` in `--influx-addr` und `--vm-addr`.

## 4. Rohimport validieren

VM-only-Checker ausfuehren:

```bash
python3 check_data.py --base-url http://localhost:8428 --phase raw
```

Fuer einen historischen Migrationszeitraum die Pruefung am importierten Enddatum verankern:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --phase raw \
  --end-time 2026-03-30T23:59:59Z
```

Danach die Influx-Quellabdeckung gegen VictoriaMetrics vergleichen:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Nutze ein abgeschlossenes Vergleichsfenster. Wenn EVCC waehrend des Imports weiter nach InfluxDB schreibt, vergleiche nicht gegen die laufende aktuelle Stunde. Nutze abgeschlossene Tage, zum Beispiel gestern als `--end`, oder exakt das Import-Snapshot-Ende. Sonst kann der Checker korrekt `TRUNCATED` melden, weil InfluxDB neuere Samples enthaelt als der abgeschlossene VictoriaMetrics-Import.

Erwartetes Ergebnis:

- `Repo-relevant problems: 0`
- `Critical energy problems: 0`
- finaler Status `OK FOR REPO`

Wenn die Pruefung fehlende oder driftende Daten meldet, stoppe und nutze [migration-troubleshooting.md](./migration-troubleshooting.md), bevor Rollups gebaut werden.

## 5. `host` nur bereinigen, wenn der Checker es empfiehlt

Der Rohimport kann Infrastruktur-Labels wie `host` enthalten. EVCC-Fachlabels bleiben erhalten; `host` wird nur entfernt, wenn `check_data.py` host-getaggte Serien meldet.

Zuerst Dry-Run:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Bei einer vollstaendigen realen EVCC-Historie kann dieser Dry-Run mehrere Minuten dauern, weil das Tool vor dem Schreiben auf Zielkonflikte prueft. Lasse ihn fertig laufen und folge der Empfehlung im Tool-Output.

Wenn die Ausgabe `GO FOR IT` meldet, fuehre dasselbe Kommando nur mit den vom Tool empfohlenen Write-Flags erneut aus. Ein normaler sauberer Lauf braucht kein `--merge-target`:

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

Fuege `--merge-target` nicht manuell hinzu. Das Tool stoppt inzwischen, wenn ein Ziel-Delete auch existierende hostlose Geschwisterserien treffen wuerde, zum Beispiel PV-String- oder Batterie-Detailserien mit `id`- und `title`-Labels, die von den Detail-Dashboards genutzt werden.

Nach der Bereinigung die Rohimport-Validierung aus Schritt 4 mit demselben abgeschlossenen Fenster wiederholen. Fahre nur fort, wenn `compare_import_coverage.py` weiterhin `OK FOR REPO` meldet und `check_data.py --phase raw` keine host-getaggten Serien mehr meldet.

Wenn die Empfehlung `REVIEW` oder `STOP` lautet, nutze [migration-troubleshooting.md](./migration-troubleshooting.md). Baue keine Rollups auf einem teilweise bereinigten Rohimport.

## 6. Rollup-Konfiguration erstellen

```bash
sudo cp evcc-vm-rollup-prod.conf.example /etc/evcc-vm-rollup.conf
sudo editor /etc/evcc-vm-rollup.conf
```

Unter Windows die Konfiguration im Arbeitsverzeichnis behalten und mit `--config` darauf verweisen, zum Beispiel `--config .\evcc-vm-rollup.conf`.

Empfohlener Produktionskern:

```ini
[victoriametrics]
base_url = http://localhost:8428
host_label =
timezone = Europe/Berlin
metric_prefix = evcc
raw_sample_step = 10s
energy_rollup_step = 60s
price_bucket_minutes = 15
max_fetch_points_per_series = 28000
```

Behalte `metric_prefix = evcc`. Die Dashboards erwarten Produktions-Rollups wie `evcc_pv_energy_daily_wh`.

## 7. Rollup-Plan pruefen

```bash
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf detect
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf plan
python3 evcc-vm-rollup.py --config /etc/evcc-vm-rollup.conf benchmark
```

Erwartetes Ergebnis:

- `detect` findet deine Ladepunkte, Fahrzeuge und optionalen EXT-/AUX-Titel.
- `plan` listet die zu erzeugenden taeglichen `evcc_*` Rollups.
- `benchmark` kann repraesentative Rohdaten ohne Timeouts abfragen.

## 8. Initialen Backfill ausfuehren

Zuerst Dry-Run:

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress
```

Danach nur abgeschlossene Tage schreiben:

```bash
python3 evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day 2024-01-01 \
  --end-day 2026-03-30 \
  --progress \
  --write
```

Nutze bei einem Live-System gestern als `--end-day`. Der Write-Pfad lehnt heute und zukuenftige lokale Tage standardmaessig ab.

## 9. Rollups pruefen

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Danach den Checker erneut ohne erzwungenes `--phase raw` ausfuehren:

```bash
python3 check_data.py \
  --base-url http://localhost:8428 \
  --end-time 2026-03-30T23:59:59Z
```

Erwartetes Ergebnis: Rohdaten-Checks und Rollup-Checks sind beide OK.

## 10. Taegliche Aktualisierung planen

`/usr/local/bin/evcc-vm-rollup-daily.sh` erstellen:

```bash
#!/usr/bin/env bash
set -euo pipefail

/usr/bin/python3 /opt/evcc-vm-migration/evcc-vm-rollup.py \
  --config /etc/evcc-vm-rollup.conf \
  backfill \
  --start-day "$(date -d 'yesterday' +%Y-%m-01)" \
  --end-day "$(date -d 'yesterday' +%F)" \
  --replace-range \
  --write
```

Dann:

```bash
sudo chmod +x /usr/local/bin/evcc-vm-rollup-daily.sh
sudo crontab -e
```

Eintragen:

```cron
5 5 * * * /usr/local/bin/evcc-vm-rollup-daily.sh >> /var/log/evcc-vm-rollup.log 2>&1
```

Die Aktualisierung nur einmal pro Tag ausfuehren, nachdem der vorherige lokale Tag abgeschlossen ist.

## 11. Grafana-Dashboards deployen

Weiter mit [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md).

## Schneller Abschlusscheck

Nutze [migration-checklist.md](./migration-checklist.md), bevor du InfluxDB aus dem aktiven Dashboard-Pfad entfernst.