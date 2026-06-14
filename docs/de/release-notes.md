# Release Notes

Englische Version: [release-notes.md](../en/release-notes.md).

Diese Hinweise fassen das erste oeffentliche EVCC-Dashboard-Release auf VictoriaMetrics-Basis zusammen.

## VNext (unreleased)

### Neue Funktionen

- PV-Gestehungskosten (LCOE) sind jetzt als optionale Finanz-Panels in `Year` und `All-time` verfuegbar. Die Auswertung nutzt eine Investment-Datei, unterstuetzt mehrere Investitionen pro Anlage, lineare Abschreibung je Position, geteilte Investments und zeigt die Datenabdeckung direkt im Anlagenlabel. Commits: `b7b1638`, `2e463c1`, `3d61f5d`, `126ae00`, `bfb43fd`.
- Ein woechentlicher Investment-Helper fuer Linux-Produktionssysteme kann die LCOE-Metriken parallel zum normalen EVCC-Rollup aktualisieren. Wenn keine Investment-Metriken vorhanden sind, werden die optionalen Panels automatisch ausgeblendet. Commits: `67d6497`, `0192569`.
- Historische PV-Ertraege aus externen Quellen koennen EVCC-kompatibel als taegliche PV-Energie pro `title` importiert werden. Der enthaltene SMA-Portal-Importer ist ein Beispielpfad fuer historische Anlagen; Investment-Berechnung und Energieimport bleiben voneinander getrennt. Commits: `b7b1638`, `a863616`.
- `Year` und `All-time` enthalten neue PV-Anlagenvergleiche fuer Jahresenergie und spezifischen Ertrag (`kWh/kWp`). Fuer den spezifischen Ertrag wird bevorzugt die Anlagenleistung aus den Investmentdaten genutzt; bestehende Installationen fallen weiter auf `installedWattPeak` zurueck. Commits: `8e6be9b`, `85d821c`, `2e4bd12`.

### Dashboard-Verbesserungen

- `Today` nutzt die Grafana-13-Sparkline-Gauges als Standarduebersicht. Die alte separate Today-Gauges-Variante wurde in den normalen Today-Pfad uebernommen.
- Autarkie, Eigenverbrauch und Speicher-SOC verwenden konsistente Sparkline-Gauges und ein einheitliches Farbschema ueber die Dashboards hinweg.
- Forecast-Vergleichspanels zeigen bei fehlenden EVCC-Forecast-Daten einen direkten Hinweis im betroffenen Panel statt still leerer Vergleichsdaten.
- Jahres- und Monatsdashboards zeigen partielle PV-Daten mit Coverage-Hinweis, statt sinnvolle Teiljahre pauschal auszublenden.

### Qualitaet und Validierung

- Der Energievergleich waehlt fuer Tibber-vs-Influx nicht mehr automatisch lokale `current-evcc-agg`-Snapshots als Release-Baseline. Solche Dateien bleiben manuell auswertbar, blockieren aber nicht mehr den reproduzierbaren Release-Pfad.
- Lokale Release-Pruefungen decken statische Dashboard-Semantik, MetricsQL-Readback, Lokalisierungs-Idempotenz, PowerShell-Kompatibilitaet und Grafana-Render-E2E gegen disposable Docker-Instanzen ab.

## Unterstuetzte Installationspfade

Unterstuetzte Endnutzerpfade:

- VictoriaMetrics auf Debian 13
- VictoriaMetrics mit Docker
- Grafana auf Debian 13
- EVCC/Telegraf-Live-Ingest nach VictoriaMetrics
- Grafana mit Docker
- Dashboard-Deployment von Windows PowerShell
- Dashboard-Deployment von Linux mit dem Python-Deployer
- optionaler Linux-Bash-Deployer fuer Systeme, die Bash und `jq` bevorzugen

Starte mit [system-requirements.md](./system-requirements.md) und folge danach [README.md](../README.md) fuer die empfohlene Reihenfolge.

## Migration von InfluxDB

Der normale Migrationspfad ist in [influx-to-vm-migration.md](./influx-to-vm-migration.md) dokumentiert:

1. VictoriaMetrics installieren oder vorbereiten
2. EVCC/Telegraf-Live-Ingest vorbereiten, den VictoriaMetrics-Schreibpfad bei Migrationen aber noch deaktiviert lassen
3. rohe EVCC-Historie aus InfluxDB v1 mit `vmctl influx` importieren
4. Rohdatenabdeckung mit `check_data.py` und `compare_import_coverage.py` validieren
5. Infrastruktur-Labels wie `host` normalisieren, wenn der Checker es verlangt
6. `evcc-vm-rollup.py` als Dry-run und danach als Schreib-Backfill fuer taegliche `evcc_*`-Metriken ausfuehren
7. taeglichen Rollup-Refresh fuer abgeschlossene lokale Tage planen
8. finalen Delta-Import ausfuehren, bei Bedarf Rollups fuer neu abgeschlossene Tage aktualisieren und dann den VictoriaMetrics-Schreibpfad aktivieren
9. Grafana mit VictoriaMetrics verbinden und Dashboards deployen

Die Release-Validierung pruefte den Live-Ingest-Pfad, importierte eine echte mehrjaehrige EVCC-Historie nach VictoriaMetrics, bereinigte `host`-Labels, verifizierte `db=0`, erzeugte Rollups und renderte die Dashboards gegen die migrierten Daten.

## Dashboard-Set

Die deployten Dashboards verwenden immer das Grafana-13-Tab-Navigation-Layout und erfordern Grafana 13.0.1 oder neuer. Der Legacy-row-basierte Deploy-Pfad und die Dashboard-Set-Auswahl wurden aus Deploy-Manifest und Skripten entfernt.

Die Release-Screenshots dokumentieren das generierte deutsche Dashboard-Set mit Tab-Navigation direkt unter [screenshots](../screenshots/README.md), inklusive aktiver Grafana-Tableiste bei Dashboards mit Tabs.

## Deployer-Varianten

Unterstuetzte Deployer:

- `scripts/deploy.ps1` fuer Windows PowerShell
- `scripts/deploy-python.sh` fuer Linux- und Raspberry-Pi-aehnliche Systeme
- `scripts/deploy-bash.sh` als optionaler Bash- und `jq`-Pfad

Alle Deployer unterstuetzen dieselbe Kernkonfiguration:

- Grafana-URL und Authentifizierung
- VictoriaMetrics-Datasource-UID
- Dashboard-Sprache
- Dashboard-Variante
- Dashboards
- Purge- oder Update-Verhalten
- Dashboard-Variablen-Overrides wie EVCC-URL, Portal-URL, Blocklists und installierte Peak-Leistung

## Lokalisierung

Generierte Dashboard-Uebersetzungen sind verfuegbar fuer:

- `de`
- `fr`
- `nl`
- `es`
- `it`
- `zh`
- `hi`

Das Release-Gate enthaelt Lokalisierungs-Idempotenzchecks und Grafana-Spot-Checks fuer Deutsch, Franzoesisch und Chinesisch.

## Bekannte Einschraenkungen

- Eine VictoriaMetrics-Instanz pro EVCC-Instanz verwenden. Mehrere EVCC-Systeme nicht ueber ein kuenstliches `db`-Label multiplexen.
- Langzeitdashboards benoetigen taegliche `evcc_*`-Rollups. `Today`, `Today - Mobile` und `Today - Details` nutzen Rohmetriken direkt.
- Der Rollup-Schreibpfad lehnt den aktuellen lokalen Tag standardmaessig bewusst ab. Refreshes fuer gestern oder einen anderen abgeschlossenen Tag planen.
- Telegraf-Live-Fan-out muss Infrastruktur-Labels vermeiden. `omit_hostname = true` setzen und fuer VictoriaMetrics `[[outputs.http]]` mit `data_format = "influx"` verwenden.
- Docker-Desktop-Nutzer muessen beachten, dass `localhost` innerhalb von Grafana auf den Grafana-Container zeigt. Fuer die VictoriaMetrics-Datasource `host.docker.internal` oder einen gemeinsamen Docker-Netzwerknamen verwenden.
- `prioritySoc_value` kann als Warnung gemeldet werden, wenn es historisch existiert, aber im aktuellen EVCC-Rohdatenfenster nicht aktiv ist. Das blockiert den Kern-Dashboard-Pfad nicht.

## Validierungszusammenfassung

Die Release-Validierung deckte ab:

- Debian-13-VictoriaMetrics-Installation
- Debian-13-Grafana-Installation
- Docker-basierte VictoriaMetrics- und Grafana-Installationspfade
- realistische InfluxDB-Historienmigration
- Rohdatenabdeckung und Label-Hygiene-Checks
- vollstaendigen Rollup-Dry-run und Schreib-Backfill
- taeglichen Rollup-Refresh-Pfad
- Windows- und Linux-Dashboard-Deployer
- deutsche Screenshots der Dashboards mit Tab-Navigation fuer jeden aktiven Tab
- Grafana-Lokalisierungs-Spot-Checks fuer `de`, `fr` und `zh`
- lokale statische/unit/dashboard Checks via `npm test`
