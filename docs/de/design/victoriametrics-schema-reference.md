# VictoriaMetrics-Schema-Referenz

Englische Version: [victoriametrics-schema-reference.md](../../en/design/victoriametrics-schema-reference.md).

Dieses Dokument beschreibt das VictoriaMetrics-Schema, das aktiv von den EVCC-VM-Dashboards und der aktuellen Python-Rollup-Pipeline verwendet wird.

Es ist Referenz fuer:

- Rohmetrikfamilien, die direkt von Dashboards genutzt werden
- taegliche Rollup-Familien, die `scripts/rollup/evcc-vm-rollup.py` schreibt
- akzeptierte Labels und Benennungsregeln
- die praktische Trennung zwischen Rohdaten-Dashboards und Rollup-basierten Dashboards

## Umfang

Dies ist das aktuell aktive Schema.

Bewusst dokumentiert werden:

- der Produktions-Rollup-Namespace `evcc_*`
- die rohen `*_value`-Metriken, die von Dashboards und Rollup-Skript abgefragt werden

Bewusst nicht dokumentiert werden:

- historische Vergleichsnamespaces wurden entfernt
- entfernte Compare-Namespaces
- obsolete Clamp-vs-Sampled-Experimente

## Kernkonventionen

- Rohe EVCC-Metriken bleiben in VictoriaMetrics unveraendert.
- Rollups werden als neue Metriken in einem separaten Namespace geschrieben.
- Der Produktions-Rollup-Namespace ist `evcc_*`.
- Das Repository nimmt eine VictoriaMetrics-Instanz pro EVCC-Instanz an.
- Wenn mehrere EVCC-Instanzen betrieben werden, sollen mehrere VictoriaMetrics-Instanzen laufen, statt sie ueber ein gemeinsames `db`-Label zu multiplexen.
- Dashboards und Rollups duerfen nicht von einem `host`-Label abhaengen.
- Einheiten sind in Metriknamen kodiert.
- Nur echte Fachdimensionen bleiben als Labels erhalten.

## Logische Schichten

### Schicht 1: Rohmetriken

Rohmetriken sind Source of Truth fuer:

- `Today`
- `Today - Details`
- `Today - Mobile`
- Debugging und Validierung
- Neuberechnung von Rollups

Typischer Rohmetrik-Namensstil:

- `<measurement>_value`

Beispiele:

- `pvPower_value`
- `homePower_value`
- `gridPower_value`
- `gridEnergy_value`
- `chargePower_value`
- `batteryPower_value`
- `batterySoc_value`
- `vehicleOdometer_value`
- `tariffGrid_value`
- `tariffFeedIn_value`
- `tariffPriceLoadpoints_value`
- `tariffSolar_value`

### Schicht 2: taegliche Rollups

Taegliche Rollups sind der Default-Input fuer:

- `Monat`
- `Jahr`
- `All-time`

Das Rollup-Skript schreibt ein Sample pro lokalem Tag und Serie.

### Schicht 3: dashboardseitige Aggregationen

Monats-, Jahres- und All-time-Dashboards bilden:

- Jahressummen
- Monatssummen
- Verhaeltnisse
- Bilanz- und Amortisationswerte
- Top-Tabellen

aus taeglichen Rollups.

Eine verpflichtende monatliche Rollup-Schicht gibt es aktuell nicht.

## Stabile Labelregeln

### Rohmetriken

Rohe EVCC-Historie sollte direkt per Metrikname und Fachlabels abgefragt werden:

- Beispiel: `pvPower_value{id=""}` oder `evcc_pv_energy_daily_wh{local_year="2025",local_month="07"}`

Nicht darauf verlassen:

- `host`
- PV-`id` als stabile Geraeteidentitaet

Grund:

- importierte Historie kann hostlos sein
- Live-Schreibzugriffe koennen zusaetzliche Infrastruktur-Labels tragen
- host-abhaengige Queries brechen historische Korrektheit
- EVCC kann PV-`id`-Werte neu nummerieren, wenn PV-Geraete hinzugefuegt, entfernt oder umsortiert werden
- fuer PV-Geraete `title` als dauerhaftes Fachlabel bevorzugen und `id` als EVCC-interne Listenposition behandeln

### Taegliche Rollups

Alle taeglichen Rollups tragen immer:

- `local_year`
- `local_month`

Zusaetzliche Labels werden nur gesetzt, wenn sie echte Dimensionen sind:

- `loadpoint`
- `vehicle`
- `title`

Akzeptierte Beispiele:

- `evcc_pv_energy_daily_wh{local_year="2025",local_month="07"}`
- `evcc_vehicle_energy_daily_wh{vehicle="BMW i3",local_year="2025",local_month="07"}`
- `evcc_ext_energy_daily_wh{title="USV",local_year="2025",local_month="07"}`

Nicht auf Rollups gespeichert:

- `local_day`
- `local_date`
- `host`

Wichtiger Hinweis:

- `local_day` und `local_date` existieren intern im Skript-Fenstermodell
- sie werden absichtlich nicht als Labels geschrieben, weil sie jede taegliche Familie in eine Serie pro Tag fragmentieren wuerden

## Aktiv genutzte Rohmetrikfamilien

### Energie und Leistung

Diese Rohmetriken speisen die Langzeit-Rollups:

| Rohmetrik | Bedeutung | Hauptnutzung |
| --- | --- | --- |
| `pvPower_value` | PV-Leistung | taegliche PV-Energie |
| `homePower_value` | Hausleistung | taegliche Hausenergie, No-PV-Baseline |
| `chargePower_value` | Ladeleistung | Loadpoint-Energie, Fahrzeugenergie, Fahrzeugkosten |
| `extPower_value` | externer Zaehler Leistung | zaehlerseitige Hausaufschluesselung |
| `auxPower_value` | Auxiliary-Zaehler Leistung | Auxiliary-Zaehleraufschluesselung |
| `gridPower_value` | Netzleistung | Netzeinspeiseenergie, dynamische Preisgewichtung |
| `gridEnergy_value` | Netzbezugszaehler | taegliche Netzbezugsenergie |
| `batteryPower_value` | Batterieleistung | Lade-/Entladeenergie, Batteriebewertung |
| `batterySoc_value` | Batterie-SOC | taeglicher min/max SOC |
| `vehicleOdometer_value` | Fahrzeugodometer | taeglich gefahrene Distanz |

### Tarife und Prognose

Diese Rohmetriken sind ebenfalls aktiv genutzt:

| Rohmetrik | Bedeutung | Hauptnutzung |
| --- | --- | --- |
| `tariffGrid_value` | Netzbezugstarif | Importkosten- und Preisrollups |
| `tariffFeedIn_value` | Einspeisetarif | Exportgutschrift und Batterie-Opportunitaetskosten |
| `tariffPriceLoadpoints_value` | Ladetarif am Loadpoint | Fahrzeugladekosten |
| `tariffSolar_value` | Solarprognose | PV-Prognosepanels in `Today` und `Today - Details` |

Hinweis: `tariffSolar_value` ist ein optionaler EVCC-Rohwert. Er entsteht nur, wenn EVCC selbst einen Solar-Forecast konfiguriert hat. Die Dashboards rufen Forecast.Solar, Solcast oder Open-Meteo nicht direkt ab; sie zeigen nur die von EVCC geschriebenen Forecast-Samples an.

## Produktions-Rollupfamilien pro Tag

Der Produktionspraefix ist aktuell `evcc`.

### Energie- und SOC-Baselines

| Metrik | Labels | Bedeutung |
| --- | --- | --- |
| `evcc_pv_energy_daily_wh` | `local_year`, `local_month` | taegliche PV-Energie |
| `evcc_home_energy_daily_wh` | `local_year`, `local_month` | taegliche Hausenergie |
| `evcc_loadpoint_energy_daily_wh` | `local_year`, `local_month`, `loadpoint` | taegliche Ladeenergie pro Loadpoint |
| `evcc_vehicle_energy_daily_wh` | `local_year`, `local_month`, `vehicle` | taegliche Ladeenergie pro Fahrzeug |
| `evcc_vehicle_distance_daily_km` | `local_year`, `local_month`, `vehicle` | taeglich gefahrene Distanz pro Fahrzeug |
| `evcc_ext_energy_daily_wh` | `local_year`, `local_month`, `title` | taegliche Energie pro externem Zaehler-Titel |
| `evcc_aux_energy_daily_wh` | `local_year`, `local_month`, `title` | taegliche Energie pro Auxiliary-Zaehler-Titel |
| `evcc_battery_soc_daily_min_pct` | `local_year`, `local_month` | minimaler taeglicher Batterie-SOC |
| `evcc_battery_soc_daily_max_pct` | `local_year`, `local_month` | maximaler taeglicher Batterie-SOC |
| `evcc_grid_import_daily_wh` | `local_year`, `local_month` | taegliche Netzbezugsenergie |
| `evcc_grid_export_daily_wh` | `local_year`, `local_month` | taegliche Netzeinspeiseenergie |
| `evcc_battery_charge_daily_wh` | `local_year`, `local_month` | taegliche Batterieladeenergie |
| `evcc_battery_discharge_daily_wh` | `local_year`, `local_month` | taegliche Batterieentladeenergie |

### Taegliche Finanz- und Preis-Baselines

| Metrik | Labels | Bedeutung |
| --- | --- | --- |
| `evcc_grid_import_cost_daily_eur` | `local_year`, `local_month` | taegliche Netzbezugskosten |
| `evcc_grid_import_price_avg_daily_ct_per_kwh` | `local_year`, `local_month` | arithmetischer taeglicher Mittelwert des Importtarifs |
| `evcc_grid_import_price_effective_daily_ct_per_kwh` | `local_year`, `local_month` | effektiver taeglicher Importpreis, nach Importenergie gewichtet |
| `evcc_grid_import_price_min_daily_ct_per_kwh` | `local_year`, `local_month` | minimaler taeglicher Importtarif |
| `evcc_grid_import_price_max_daily_ct_per_kwh` | `local_year`, `local_month` | maximaler taeglicher Importtarif |
| `evcc_grid_export_credit_daily_eur` | `local_year`, `local_month` | taegliche Einspeiseverguetung |
| `evcc_vehicle_charge_cost_daily_eur` | `local_year`, `local_month`, `vehicle` | taegliche Ladekosten zum Loadpoint-Tarif |
| `evcc_potential_vehicle_charge_cost_daily_eur` | `local_year`, `local_month`, `vehicle` | taegliche Ladekosten zum Netzbezugstarif als No-PV-Baseline |
| `evcc_potential_home_cost_daily_eur` | `local_year`, `local_month` | taegliche Hauskosten zum Netzbezugstarif als No-PV-Baseline |
| `evcc_potential_loadpoint_cost_daily_eur` | `local_year`, `local_month` | taegliche Ladekosten zum Netzbezugstarif als No-PV-Baseline |
| `evcc_battery_discharge_value_daily_eur` | `local_year`, `local_month` | taeglicher Wert entladener Batterieenergie zum Netzbezugstarif |
| `evcc_battery_charge_feedin_cost_daily_eur` | `local_year`, `local_month` | taegliche Opportunitaetskosten der Batterieladung zum Einspeisetarif |

### PV-Health-Rollups

Diese Helper-Rollups speisen den All-time-Anlagengesundheitsbereich:

| Metrik | Labels | Bedeutung |
| --- | --- | --- |
| `evcc_pv_top30_mean_yearly_wh` | `local_year` | Mittelwert der Top-30-PV-Tageswerte eines Jahres |
| `evcc_pv_top5_mean_monthly_wh` | `local_year`, `local_month` | Mittelwert der Top-5-PV-Tageswerte eines Monats |

## Source-of-Truth-Regeln je Thema

### Netzbezug

Aktuelle Regel:

- `evcc_grid_import_daily_wh` kommt aus dem Local-Day-Spread von `gridEnergy_value`

Das ist absichtlich so, weil:

- `gridEnergy_value` sich wie der echte kumulative Importzaehler verhaelt
- er besser zum gemessenen Bezugspfad passt als die Integration von `gridPower_value`

### Netzeinspeisung

Aktuelle Regel:

- `evcc_grid_export_daily_wh` wird weiterhin aus `gridPower_value` abgeleitet

Grund:

- im aktuellen Rohdatensatz gibt es keinen separaten Exportenergie-Zaehlerpfad

### Batterieenergie

Aktuelle Regel:

- Batterie-Lade-/Entladerollups entstehen aus vorzeichenbewusster Verarbeitung von `batteryPower_value`
- `evcc_battery_charge_daily_wh` enthaelt die taegliche Speicher-Ladeenergie
- `evcc_battery_discharge_daily_wh` enthaelt die taegliche Speicher-Entladeenergie

Die Dashboard-Kennzahl `Speicher-Effizienz` ist definiert als:

```text
sum(evcc_battery_discharge_daily_wh) / sum(evcc_battery_charge_daily_wh) * 100
```

Wenn im betrachteten Zeitraum keine Speicher-Ladeenergie vorhanden ist, wird keine Effizienz angezeigt. Fuer VRM-Vergleiche wird dieselbe Logik mit den naheliegenden VRM-Fluessen angewendet: `(battery_to_consumers_kwh + battery_to_grid_kwh) / (pv_to_battery_kwh + grid_to_battery_kwh) * 100`. Das ist ein Vergleich der bilanzierten Energiefluesse und keine Herstellerangabe zur Zell- oder Wechselrichtereffizienz.

### Fahrzeugdistanz

Aktuelle Regel:

- taegliche Fahrzeugdistanz wird aus dem Odometer-Spread abgeleitet
- Odometer-Serien koennen sich nach anderen Labels aufteilen und spaeter Nullwerte emittieren
- Dashboards koennen deshalb `max known odometer`-Semantik statt `last raw point` fuer die Anzeige nutzen

## Aggregationsmodell des Rollup-Skripts

### Taegliche Fenster

- Lokale Tagesfenster werden in der konfigurierten Zeitzone gebildet.
- Aktueller Zeitzonen-Default ist `Europe/Berlin`.
- Ein taegliches Sample wird am UTC-Start des zugehoerigen lokalen Tages geschrieben.

### Energie-Rollups

Positive Energiefamilien nutzen:

- Rohsamples auf dem konfigurierten Rohschritt
- danach 60-Sekunden-Rollup-Buckets
- danach taglokale Aggregation

Grid- und Batterie-Familien mit Vorzeichen nutzen dedizierte Vorzeichenbehandlung auf gesampelten Leistungsserien.

### Preis- und Kosten-Rollups

Preis- und Kostenrollups nutzen:

- rohe Tarifserien
- 15-Minuten-Bucket-Grenzen
- taglokale Fenster
- Import-/Export- oder Ladeenergie, gewichtet gegen den passenden Tarif

## Dashboard-zu-Schema-Mapping

### Rohdaten-Dashboards

Diese Dashboards fragen Rohmetriken direkt ab:

- `VM_EVCC_Today.json`
- `VM_EVCC_Today-Gauges.json`
- `VM_EVCC_Today-Details.json`
- `VM_EVCC_Today-Mobile.json`

Spezialhinweis:

- die PV-Prognoselinie in `Today` nutzt rohes `tariffSolar_value`
- der grosse `Today`-Leistungsplot ist direkt im Dashboard enthalten; Quellaenderungen werden damit ohne separate Grafana-Library-Panels deployt

### Rollup-Dashboards

Diese Dashboards fragen `evcc_*`-Rollups ab:

- `VM_EVCC_Monat.json`
- `VM_EVCC_Jahr.json`
- `VM_EVCC_All-time.json`

Diese Dashboards haengen stark von:

- `local_year`
- `local_month`

ab, um Queries lesbar zu halten und wiederholte Inline-Timezone-Guards zu vermeiden.

## Praktische Filterregeln der Dashboards

Das Schema selbst traegt Fachdimensionen, und die Dashboards wenden darauf Blocklists an:

- `loadpointBlocklist`
- `extBlocklist`
- `auxBlocklist`
- `vehicleBlocklist`

Das sind Dashboard-Level-Filter, nicht Teil des Datenbankschema-Designs.

Beispiele:

- nicht nutzersichtbare Loadpoints ausblenden
- interne oder unerwuenschte Zaehler-Titel ausblenden
- Pseudo-Fahrzeuge aus Fahrzeugpanels ausschliessen

## Betriebshinweise

### Host-Label

- Historische Korrektheit haengt von hostlos-sicheren Queries ab.
- Wenn `host` durch Ingest wieder auftaucht, sollten Dashboards trotzdem korrekt bleiben, weil sie Metriknamen direkt abfragen und wo noetig `without(host)` aggregieren.

### Performance

Der aktuelle Produktions-Rollup-Pfad nutzt chunked Rohdatenabrufe und lokale Wiederverwendung geladener Samples.

Aktuelles Full-Rebuild-Profil ueber `2025-01-01 .. 2026-03-27`:

- Gesamtlaufzeit etwa `252.60s`
- Peak-RAM etwa `1266 MB`
- VM-Schreibzeit vernachlaessigbar
- Hauptkostenstelle ist weiterhin VM-Lese-/Query-Zeit

Mindestempfehlung fuer den Rollup-Job auf Raspberry-Pi-aehnlichen Systemen ist Raspberry Pi 4 mit 4 GB RAM oder vergleichbare Hardware. Raspberry Pi 3 und 1-2-GB-Systeme werden fuer den monatlichen `--replace-range`-Rollup-Pfad nicht empfohlen, weil der aktuelle Python-Prozess etwa 1,25 GB erreichen kann, bevor Betriebssystem, VictoriaMetrics und weitere Dienste beruecksichtigt sind.

### Namespace-Status

Aktueller gewuenschter Produktionszustand:

- nur `evcc_*` ist relevant
- alte Test- und Compare-Namespaces sind nicht mehr Teil des aktiven Designs

## Kurzcheckliste fuer kuenftige Schemaaenderungen

Beim Hinzufuegen einer neuen Rohmetrik oder Rollup-Familie gelten diese Regeln:

1. Rohmetriken nicht ueberschreiben.
2. Eine VictoriaMetrics-Instanz dediziert fuer eine EVCC-Instanz behalten und Metriknamen direkt abfragen.
3. `host` nicht erforderlich machen.
4. Nur Labels hinzufuegen, die echte Fachdimensionen darstellen.
5. `local_year` und `local_month` nur wiederverwenden, wenn sie Langzeit-Dashboardqueries spuerbar vereinfachen.
6. `local_day` oder `local_date` auf gespeicherten taeglichen Rollups vermeiden.
7. Dashboardseitige Aggregation bevorzugen, ausser das Ergebnis wird oft wiederverwendet oder ist teuer wiederholt zu berechnen.
