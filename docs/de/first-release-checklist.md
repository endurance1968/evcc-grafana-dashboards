# First Release Checkliste

Englische Version: [first-release-checklist.md](../en/first-release-checklist.md).

Diese Checkliste ist das Release-Gate fuer die erste oeffentliche Endnutzer-Version der VictoriaMetrics-basierten EVCC-Dashboards.

Wenn einer der Punkte offen ist, sollte der Release nicht als final veroeffentlicht werden.

## 1. Dokumentation

- [x] Root-[README.md](../../README.md) passt weiterhin zum aktuellen Repository-Umfang und Release-Status.
- [x] [docs/de/README.md](../README.md) beschreibt weiterhin die empfohlene End-to-End-Reihenfolge.
- [x] [system-requirements.md](./system-requirements.md) buendelt Runtime-, Hardware-, Netzwerk-, Speicher- und Label-Hygiene-Anforderungen.
- [x] [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md) ist getestet und aktuell.
- [x] [victoriametrics-install-docker.md](./victoriametrics-install-docker.md) ist geprueft und aktuell.
- [x] [grafana-install-debian-13.md](./grafana-install-debian-13.md) ist getestet und aktuell.
- [x] [grafana-install-docker.md](./grafana-install-docker.md) ist geprueft und aktuell.
- [x] [influx-to-vm-migration.md](./influx-to-vm-migration.md) passt zu den aktuellen Migrations- und Rollup-Kommandos.
- [x] [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md) passt zum aktuellen Grafana-Setup- und Deploy-Ablauf.
- [x] [deployment-readme.md](./deployment-readme.md) und [vm-dashboard-install.md](./vm-dashboard-install.md) beschreiben die aktuellen Deployer-Optionen.

## 2. Installations- und Migrationsvalidierung

- [x] Frische VictoriaMetrics-Installation auf Debian 13 funktioniert end-to-end.
- [x] Frische Grafana-Installation auf Debian 13 funktioniert end-to-end.
- [x] VictoriaMetrics-Docker-Anleitung ist auf einem lokalen Docker-Host validiert.
- [x] Grafana-Docker-Anleitung ist auf einem lokalen Docker-Host validiert.
- [x] InfluxDB-Rohdatenimport funktioniert mit einem realistischen EVCC-Historienbestand.
- [x] Initialer Rollup-Backfill funktioniert ohne manuelle Korrekturen.
- [x] Taegliche Rollup-Aktualisierung funktioniert per `systemd`-Timer oder `cron`.
- [x] Mindestens ein sauberer New-User-Dry-Run wurde nur anhand der veroeffentlichten Doku durchlaufen.

## 3. Dashboard-Deployment-Validierung

- [x] `deploy.ps1` funktioniert unter Windows PowerShell mit sauberem Dashboard-Deployment.
- [x] `deploy-python.sh` funktioniert unter Linux mit sauberem Dashboard-Deployment.
- [x] `deploy-bash.sh` funktioniert unter Linux mit sauberem Dashboard-Deployment.
- [x] `purge=true` erstellt Dashboards und eingebettete Library Panels sauber neu.
- [x] `purge=false` aktualisiert bestehende Library Panels und zeigt die korrekten Preflight-Informationen.
- [x] Dashboard-Override-Variablen sind dokumentiert und verifiziert:
- [x] `DASHBOARD_FILTER_PEAK_POWER_LIMIT`
- [x] `DASHBOARD_ENERGY_SAMPLE_INTERVAL`
- [x] `DASHBOARD_TARIFF_PRICE_INTERVAL`
- [x] `DASHBOARD_INSTALLED_WATT_PEAK`
- [x] `DASHBOARD_FILTER_LOADPOINT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_EXT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_AUX_BLOCKLIST`
- [x] `DASHBOARD_FILTER_VEHICLE_BLOCKLIST`
- [x] `DASHBOARD_EVCC_URL`
- [x] `DASHBOARD_PORTAL_TITLE`
- [x] `DASHBOARD_PORTAL_URL`

## 4. Dashboard-Qualitaet

- [x] Alle sechs VM-Dashboards laden im produktionsnahen Deploy-Pfad ohne Panel-Fehler.
- [x] `Today` rendert korrekt inklusive eingebetteter Library Panels.
- [x] `Month` rendert korrekt inklusive Verbraucher-Panels.
- [x] `Year` rendert korrekt inklusive Verbraucher-Panels und Jahres-Navigationsbuttons.
- [x] `All-time` rendert korrekt inklusive Top-Day- und Jahres-/Monatsvergleich-Panels.
- [x] Dashboard-Links zwischen `Today`, `Month`, `Year` und `All-time` funktionieren wie vorgesehen.
- [x] `Year`, `Previous year` und `2 years ago` verhalten sich konsistent zur vorgesehenen Zeitlogik.
- [x] Einheiten, Dezimalstellen, Hintergrund-Styling und Panel-Layout sind visuell konsistent.

## 5. Lokalisierung

- [x] `node scripts/localization/audit-localization.mjs` meldet `0` fehlende Kandidaten.
- [x] Lokalisierte Dashboards sind aus der aktuellen `orig/en`-Quelle regeneriert.
- [x] Release-Screenshots unter [docs/screenshots](../screenshots/README.md) zeigen den finalen sichtbaren Dashboard-Zustand inklusive aktiver Grafana-Tab-Leiste bei Tab-Dashboards.
- [x] Mindestens `de`, `fr` und ein nicht-lateinisches Ziel (`zh` oder `hi`) wurden in Grafana stichprobenartig geprueft.

## 6. Release-Paketierung

- [x] Finaler Commit ist auf den Release-Remote gepusht.
- [x] Release Notes beschreiben:
- [x] unterstuetzte Installationspfade
- [x] Migrationspfad von InfluxDB
- [x] Deployer-Varianten
- [x] bekannte Einschraenkungen
- [x] Preview-Formulierungen sind entfernt oder reduziert, sobald der Release wirklich final ist.

## Minimales Release-Gate

Mindestens diese Punkte muessen vor dem ersten Endnutzer-Release erfuellt sein:

- [x] Debian-13-VictoriaMetrics-Installation getestet
- [x] Debian-13-Grafana-Installation getestet
- [x] InfluxDB-Migration getestet
- [x] Rollup-Backfill getestet
- [x] taegliche Rollup-Aktualisierung getestet
- [x] Windows- und Linux-Deployer getestet
- [x] Lokalisierungs-Audit bei `0`
- [x] kuratierte Release-Screenshot-Serie unter [docs/screenshots](../screenshots/README.md) bildet den finalen sichtbaren Dashboard-Zustand ab, inklusive Tab-Navigation
- [x] ein kompletter End-to-End-Migrationsdurchlauf wurde anhand der veroeffentlichten Doku abgeschlossen

## Aktuelle Nachweise

Zuletzt aktualisiert: 2026-05-31.

Die abgehakten Punkte basieren auf der abgeschlossenen Dokumentationsstruktur, dem erfolgreichen `npm run test:rollup-path` vom 2026-05-28, dem lokalen Windows-Docker-Migrationsdurchlauf vom 2026-05-29 mit Oles realen EVCC-/Influx-Daten und den manuell aktualisierten Release-Screenshots vom 2026-05-31.

Real-Daten-Migrationsnachweise vom 2026-05-29:

- InfluxDB-v1-Quelle: Datenbank `evcc`, waehrend des Tests nur lesend genutzt
- EVCC-API wurde nur zur lesenden Topologie-Verifikation genutzt
- Disposable Ziel-VictoriaMetrics: Docker-Image `victoriametrics/victoria-metrics:v1.138.0`
- Disposable Ziel-Grafana: Docker-Image `grafana/grafana`, Grafana `13.0.1+security-01`
- `vmctl influx` importierte 643 Serien, 267.886.076 Samples und 5,3 GB aus der realen Influx-Historie fuer den Zeitraum ab `2025-01-01T00:00:00Z` bis zum Live-Importsnapshot am 2026-05-29
- Reale Labels nach Import enthielten 3 Ladepunkte (`Carport_Ecke`, `Carport_Treppe`, `Daikin-WP`), 3 Fahrzeuge (`Altherma-3`, `BMW i3`, `Schneeflittchen`) und 16 EXT-Titel
- Host-Label-Cleanup-Dry-Runs meldeten `GO FOR IT`; finales `check_data.py` bestaetigte `host`-Serien `0` und `db`-Serien `0`
- `compare_import_coverage.py` ueber das abgeschlossene Fenster `2026-05-22T00:00:00Z` bis `2026-05-28T23:59:59Z` meldete 0 repo-relevante Probleme und 0 kritische Energieprobleme
- Rollup `detect`, `plan` und `benchmark` liefen erfolgreich; kompletter Backfill von `2025-01-01` bis `2026-05-28` schrieb 36 Rollup-Metriken, 1.154 Serien und 30.013 Samples
- `deploy.ps1` deployte die deutschen generierten Dashboards mit Tab-Navigation aus dem lokalen Checkout mit `PURGE=true`
- `render-smoke-check.mjs` bestand strikt fuer alle 6 Dashboards und 49 kritische Panels gegen die Real-Daten-Test-VM
- Manuelle Dashboard-Sicherheitspruefung vom 2026-05-30 erfolgreich abgeschlossen: Navigation zwischen Today, Month, Year und All-time, Jahres-Zeitnavigation, Einheiten, Dezimalstellen, Hintergrund-Styling und Panel-Layout wurden akzeptiert
- Sauberer New-User-Docker-Dry-Run vom 2026-05-30 anhand des veroeffentlichten Doku-Pfads abgeschlossen: frische VictoriaMetrics `v1.139.0`, frische Grafana `13.0.1`, Datasource UID `vm-evcc`, deutsches generiertes Deployment mit Tab-Navigation via `deploy-python.sh`
- Release-Screenshots vom 2026-05-31 wurden manuell aktualisiert und direkt unter `docs/screenshots` kuratiert, jeweils als PNG pro relevantem Dashboard bzw. aktivem Dashboard-Tab
- Lokalisierungs-Grafana-Stichproben vom 2026-05-30 bestanden fuer `de`, `fr` und `zh`; franzoesische und chinesische Deployments zeigten lokalisierte Dashboard- und Panel-Titel in Grafana
- Release Notes wurden in `docs/de/release-notes.md` ergaenzt, und Preview-Formulierungen im Root-`README.md` wurden entfernt

Noch offen: nichts fuer das erste oeffentliche Release-Gate.

Debian-13-Installationsnachweise vom 2026-05-29:

- validiert in frischen `debian:trixie` Docker-Containern mit Debian `13.5` und `x86_64`
- Blank-Image enthielt kein `sudo`; Doku beschreibt nun, dass Root-Nutzer `sudo` weglassen koennen
- VictoriaMetrics `v1.139.0` Binary und `vmctl` wurden aus den dokumentierten Release-Archiven installiert
- VictoriaMetrics-Service-Datei wurde erzeugt; Standard-Docker hat kein `systemctl`, daher wurde die Laufzeit durch manuellen Start von `victoria-metrics-prod` als Nutzer `victoriametrics` mit dokumentiertem Datenpfad und dokumentierten Flags validiert
- VictoriaMetrics `/health` lieferte lokal und ueber den von Windows veroeffentlichten Docker-Port `OK`
- Grafana-APT-Repository-Setup und `grafana-enterprise`-Installation liefen auf blankem Trixie erfolgreich; installierte Version war `13.0.1+security-01`
- Doku enthaelt nun `curl` in den Grafana-Basispaketen, weil der Verifikationsschritt `curl -I` nutzt
- VictoriaMetrics-Datasource-Plugin-Installation wurde mit `grafana cli --homepath=/usr/share/grafana --pluginsDir /var/lib/grafana/plugins plugins install victoriametrics-metrics-datasource` validiert
- Grafana `/api/health` meldete `database: ok`; eine VictoriaMetrics-Datasource gegen die frische Debian-VictoriaMetrics-Testinstanz meldete `Data source is working`

Weitere autonome Release-Gate-Nachweise vom 2026-05-29:

- `deploy-python.sh` v2026.05.29.1 wurde in blankem `debian:trixie` syntaxgeprueft und fuehrte ein sauberes Linux-Deployment (`PURGE=true`) des deutschen generierten Dashboard-Sets mit Tab-Navigation gegen Grafana `13.0.1` aus
- `deploy-bash.sh` v2026.05.29.1 wurde in blankem `debian:trixie` syntaxgeprueft, fuehrte `PURGE=true` und anschliessend `PURGE=false` gegen dieselbe Disposable-Grafana-Instanz aus
- Linux-Deployer verarbeiten nun Grafana-Dashboard-v2-JSON ueber `/apis/dashboard.grafana.app/v2/...`, inklusive Folder-Annotations und `metadata.resourceVersion`-Updates fuer bestehende Dashboards
- Dashboard-Override-Validierung fragte Grafana nach Deployment ab und verifizierte 46 Override-Variableninstanzen ueber alle 6 Dashboards, inklusive v2-Dashboards mit Tab-Navigation und klassischen Dashboards
- Taegliche Rollup-Refresh-Validierung nutzte die dokumentierte Cron-Form mit `date -d 'yesterday'` in blankem `debian:trixie`; der Lauf fuehrte `backfill --replace-range --write` erfolgreich aus, nachdem `rollup-e2e.py` wiederholtes Ersetzen ohne doppelte Tages-Samples validiert hatte
- Lokalisierungs-Audit meldet nun `0` fehlende Kandidaten fuer `de`, `fr`, `nl`, `es`, `it`, `zh` und `hi`; generierte lokalisierte Dashboards wurden regeneriert und `npm run test:localization-idempotency` bestand