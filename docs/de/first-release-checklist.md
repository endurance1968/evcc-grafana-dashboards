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
- [x] `purge=true` erstellt die Dashboards mit Inline-Panels sauber neu.
- [x] `purge=false` aktualisiert bestehende Dashboards und zeigt die korrekten Preflight-Informationen.
- [x] Dashboard-Override-Variablen sind dokumentiert und verifiziert:
- [x] `DASHBOARD_FILTER_PEAK_POWER_LIMIT`
- [x] `DASHBOARD_ENERGY_SAMPLE_INTERVAL`
- [x] `DASHBOARD_TARIFF_PRICE_INTERVAL`
- [x] `DASHBOARD_INSTALLED_WATT_PEAK`
- [x] `DASHBOARD_FILTER_LOADPOINT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_CONSUMER_BLOCKLIST`
- [x] `DASHBOARD_FILTER_EXT_BLOCKLIST`
- [x] `DASHBOARD_FILTER_AUX_BLOCKLIST`
- [x] `DASHBOARD_FILTER_VEHICLE_BLOCKLIST`
- [x] `DASHBOARD_EVCC_URL`
- [x] `DASHBOARD_PORTAL_TITLE`
- [x] `DASHBOARD_PORTAL_URL`

## 4. Dashboard-Qualitaet

- [x] Alle sechs VM-Dashboards laden im produktionsnahen Deploy-Pfad ohne Panel-Fehler.
- [x] `Today` rendert korrekt mit Inline-Panels.
- [x] `Month` rendert korrekt inklusive Verbraucher-Panels.
- [x] `Year` rendert korrekt inklusive Verbraucher-Panels und Jahres-Navigationsbuttons.
- [x] `All-time` rendert korrekt inklusive Top-Day- und Jahres-/Monatsvergleich-Panels.
- [x] Dashboard-Links zwischen `Today`, `Month`, `Year` und `All-time` funktionieren wie vorgesehen.
- [x] `Year`, `Previous year` und `2 years ago` verhalten sich konsistent zur vorgesehenen Zeitlogik.
- [x] Einheiten, Dezimalstellen, Hintergrund-Styling und Panel-Layout sind visuell konsistent.
- [x] Der aktuelle Release-Kandidat wurde in einer Wegwerf-Grafana-Instanz gegen die read-only Live-VM mit den echten Deploy-Overrides und Blocklists gerendert; Fixture-Daten allein reichen nicht.
- [x] Fuer jede neue optionale Funktion im Release-Umfang existieren Live-Metriken und eine sichtbare Endnutzerpruefung. Fehlen die Live-Metriken, wird die Funktion ausdruecklich nur als Fixture-getestet und nicht als live-validiert ausgewiesen.
- [x] Consumer-, AUX- und EXT-Summen wurden auf Eltern-/Kind-Ueberlappungen geprueft. Gefilterte Detailzaehler duerfen den Hausverbrauch nicht unbemerkt vollstaendig aufbrauchen oder ueberschreiten.

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
- [x] Read-only Live-Quellen-Render mit den echten Deploy-Overrides ist plausibel; neue optionale Funktionen ohne passende Live-Metrik sind nicht als live-validiert markiert

## Aktuelle Nachweise

Zuletzt aktualisiert: 2026-07-28.

Der aktuelle Release-Kandidat wurde in frisch bereinigten Docker-Testinstanzen mit der unterstützten Basis Grafana 13.0.1 und zusätzlich mit Grafana 13.1.0 gegen VictoriaMetrics 1.139.0 geprüft. Die Produktion blieb read-only; 19 Monatsblöcke von 2025-01-01 bis 2026-07-29 wurden in die isolierte Test-VM kopiert. Vor dem Endnutzer-Sichttest wurden alle alten Testdashboards gelöscht und exakt sechs aktuelle deutsche Dashboards mit den produktiven Filtern ausgerollt.

Aktuelle technische Nachweise:

- Der vollständige Rollup verarbeitete 573 abgeschlossene Tage, 36.625 Samples und 1.388 Serien in 210,606 Sekunden bei 1.264 MB Spitzenspeicher.
- `check_data.py --phase full` meldete insgesamt `OK`, keine doppelten Label-/Tageskombinationen sowie keine `host`- oder `db`-Labels.
- Der verpflichtende Lauf `npm run test:rollup-path -- --strict-energy --vm-base-url http://127.0.0.1:18440` bestand auf den finalen Release-Quellen in 521,3 Sekunden: 190 Python-Tests, 76 Dashboard-JSON-Dateien, 382 reale MetricsQL-Abfragen, 60 kritische Panels in sechs Dashboards, 17 zusaetzliche historische `Today - Details`-Panelpruefungen und wiederholtes `--replace-range` ohne Duplikate.
- Der VRM-Import enthielt 383 Tage und 2.298 Samples. Alle sechs VRM-Metriken stimmten taggenau mit dem normalisierten Quellsnapshot überein; `missing=0`, `extra=0`, `duplicates=0`. Juni 2026 ergab 85,260% Wirkungsgrad gegenüber 85,3% Referenz, also 0,040 Prozentpunkte Abweichung.
- Der Scheduler-Lock wies einen gleichzeitig gestarteten zweiten Schreiblauf ab. Der Voll-Backfill meldete zwei ignorierte Counter-Resets, keine Leistungsspitzen und 9.910 fehlende Energie-Buckets.
- Die Consumer-Langzeitreihen enthalten 14 kanonische Titel. Die alte Schreibweise `Trocker` erscheint nach dem Vollersatz nur noch als `Trockner`; gemappte frühere EXT-Verbraucher werden nicht zusätzlich als EXT gezählt.
- Der Endnutzer-Sichttest unter Grafana 13.0.1 und 13.1.0 bestätigte 2025 und 2026 im Gesamtzeitraum, plausible Juli-2026-Werte, `Today` als echten Grafana-Zeitraum sowie getrennte EVCC- und VRM-Speicherwerte. Für Juni 2026 zeigte Grafana 96,5% EVCC- und 85,3% VRM-Wirkungsgrad.
- Der EXT-zu-Consumer-Migrationstest pruefte unter beiden Grafana-Versionen den 25.07.2026 vor dem Rollenwechsel, den 27.07.2026 als Uebergangstag und die aktuelle Today-Ansicht gegen die Live-Kopie. Die vier Haus-Panels blieben in allen Fenstern gefuellt; 14 historische und 14 aktuelle Verbrauchertitel wurden ohne identische Doppeltitel sowie ohne Carport- oder Hauptverteiler-Summenzaehler geliefert.
- Das Monats-Speicherlayout wurde bei 1280 Pixel Breite korrigiert: Kennzahlen und Tagesachsen überlappen sich nicht mehr.

Frühere Installations-, Migrations- und Lokalisierungsnachweise bleiben gültig. Ole hat den finalen Dashboard-Stand am 2026-07-28 manuell freigegeben. Die kuratierte Galerie wurde danach vollständig neu erzeugt und umfasst 25 Ansichten einschließlich Consumer- und Zusatzzaehler-Tabs.

Das Release-Gate ist vollständig erfüllt: Oles manuelle Sichtfreigabe liegt vor, 25 kuratierte Screenshots bilden den finalen Stand ab und der verpflichtende Rollup-Pfad bestand auf den finalen Quellen in 521,3 Sekunden. Issue #30 wird mit diesem Release geschlossen. Issue #35 bleibt ausdrücklich außerhalb dieses Release-Umfangs.
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
