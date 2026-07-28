# Release Notes

Englische Version: [release-notes.md](../en/release-notes.md).

Diese Hinweise fassen die oeffentlichen EVCC-Dashboard-Releases auf VictoriaMetrics-Basis zusammen.

## V2026-07-28

Relevante Commits: `10609e6`, `4bb01ee`, `fdb8093`, `fc4cdad`, `90c1dbf`, `42b748b`, `3e327e1`, `bf5ea36`.

### Neue Funktionen

- Reguläre EVCC-Consumer werden in `Today - Details`, `Month`, `Year` und `All-time` getrennt von AUX und EXT ausgewertet.
- Historische EXT-Verbraucher können über `consumer_legacy_ext_regex` und die gleich gesetzte Dashboard-Variable `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` lückenlos unter demselben Consumer-Titel fortgeführt werden; das gilt für Rollups und die Rohdaten-Panels in `Today - Details`, Überlappungen werden zugunsten der Consumer-Reihe dedupliziert.
- Umbenannte Consumer-Titel können über `consumer_title_aliases_json` vor der Tagesintegration kanonisiert werden.
- Der optionale VRM-Energieflussimport besitzt einen taggenauen Quell-/VM-Validator für alle sechs Hilfsmetriken.

### Verbesserungen

- EXT-Zähler besitzen eigene Ansichten als zusätzliche Zähler und beeinflussen `Sonstiges` oder die Hausverbraucherbilanz nicht mehr.
- Als historische Consumer zugeordnete EXT-Titel werden auch in den Rohdaten-Panels nicht mehr zusätzlich als EXT angezeigt; nicht zugeordnete Kontroll- und Summenzähler bleiben als zusätzliche Zähler sichtbar.
- Today-Finanzwerte verwenden dieselbe Vorzeichenkonvention wie die Langzeit-Rollups: Bezugskosten negativ, Einspeisegutschrift positiv und Bilanz als Summe beider Werte.
- Englische Quelldashboards werden statisch auf bekannte deutsche Endusertexte und veraltete Repository-Links geprüft.
- Die Datenprüfung erkennt mehrere Rollup-Samples desselben Labelsatzes am selben lokalen Tag als kritischen Fehler.
- Der Rollup-Scheduler schützt Schreibläufe mit einer Lock-Datei, verarbeitet standardmäßig nur abgeschlossene Tage und meldet Resets, Leistungsspitzen sowie fehlende Energie-Buckets.
- Der vollständige Livecopy-Backfill wurde profiliert; die Titelkanonisierung läuft speicherschonend in MetricsQL und der normale Monats-Ersatzpfad bleibt kurz.
- Grafana 13.0.1 bleibt die unterstützte Basis; derselbe Dashboard-Stand wurde zusätzlich unter Grafana 13.1.0 geprüft, ohne 13.1 vorauszusetzen.
- Die kuratierte Screenshot-Galerie umfasst jetzt 25 aktuelle Ansichten einschließlich Consumer- und Zusatzzaehler-Tabs.

### Fehlerbehebungen

- Consumer-Titelaliase werden jetzt vor der Tagesintegration angewendet; alte und aktuelle Schreibweisen erscheinen nicht mehr als doppelte Langzeitreihen.
- Der strikte Energievergleich behandelt EVCC- und VRM-Speicherwerte als getrennte Messgrenzen und prüft stattdessen die VRM-Importparität gegen denselben Quellsnapshot.

### Hinweise Für Nutzer

- Nach einem EXT-zu-Consumer-Rollenwechsel muss der komplette betroffene Zeitraum neu berechnet werden. `--replace-range --write` ist nur bei vollstaendiger Rohdatenhistorie sicher, weil vorhandene Rollups vor der Neuberechnung geloescht werden.
- `consumer_legacy_ext_regex` darf nur echte frühere Endverbraucher enthalten, keine Verteiler- oder Summenzähler.
- `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` muss beim Dashboard-Deployment auf dieselbe Regex gesetzt werden; ohne Rollenwechsel bleiben beide Einstellungen auf `^$`.
- `DASHBOARD_FILTER_EXT_BLOCKLIST` filtert nur die separate Zusatzzaehleransicht. Verwende `^none$`, wenn echte EXT-Kontroll- und Summenzaehler dort sichtbar bleiben sollen.

## V2026-06-30

### Neue Funktionen

- EVCC-Gruenanteil ist als eigener KPI in `Today`, `Month`, `Year` und `All-time` sichtbar. Der Wert folgt EVCCs `greenShareHome_value` und beschreibt EVCCs Haus-Gruenanteil als Trend-KPI. Relevante Commits: `5c6e84c`, `d339f10`.
- Optionaler Netzsteuerungs-/14a-Auditpfad: ein Collector kann EVCC-Begrenzungen und Steuerereignisse nach VictoriaMetrics schreiben und lokal als CSV-Historie sichern. `Today - Details` zeigt dafuer den Tab `Netzsteuerung` mit VNB-Grenzen, Einhaltungsreserven, aktuellen Limits, steuerbaren Gruppen und Ereignistabelle. Relevante Commits: `a2b2201`, `4086d95`, `0c5fe56`, `8645fa1`.
- Der Collector unterstuetzt explizit konfigurierte steuerbare Gruppen, z. B. zusammengefasste Ladepunkte, Waermepumpe und Batterie-Netzladung. Relevante Commits: `ace544d`, `a271eb1`, `25f3390`.

### Verbesserungen

- `Year` und `Month` ordnen Haus-/Verbraucher-/Finanzbereiche klarer: Versorgungsmix-Panels liegen unter `Haus`, Kosten- und Preis-Panels unter `Finanzen`. Relevanter Commit: `afb8248`.
- Netzsteuerungs-Panels verwenden konsistente Vorzeichen und Farben: Bezug/Verbrauch rot, Einspeisung gruen und berechnete Werte blau; Einspeisung wird negativ dargestellt. Relevante Commits: `d3c32c0`, `8645fa1`.
- Der Deployer schreibt eine aussagekraeftigere Dashboard-Build-Info mit Build/Source statt nur dem Deployment-Zeitpunkt. Relevanter Commit: `bec38c9`.

### Hinweise fuer Nutzer

- Fuer Langzeit-Gruenanteil in Monats-, Jahres- und Gesamtzeitraum-Dashboards muss der normale EVCC-VM-Rollup fuer die gewuenschten Zeitraeume gelaufen sein. Die aktuellen Langzeitwerte sind Trend-KPIs aus taeglichen EVCC-Ratios, keine externe Oekostrom- oder CO2-Bewertung.
- Der Netzsteuerungs-Tab erscheint nur, wenn `evcc_audit_*`-Metriken vorhanden sind. Fuer diese optionale Ansicht muss der Collector installiert und betrieben werden; die Doku verwendet dafuer `/opt/evcc-vm-tools`.

## V2026-06-14

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

Die deployten Dashboards verwenden immer das Grafana-13-Tab-Navigation-Layout und erfordern Grafana 13.0.1 oder neuer. Grafana 13.0.1 bleibt die unterstützte Mindestversion; Grafana 13.1.0 wurde zusätzlich geprüft, ist aber keine Voraussetzung. Der Legacy-row-basierte Deploy-Pfad und die Dashboard-Set-Auswahl wurden aus Deploy-Manifest und Skripten entfernt.

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
