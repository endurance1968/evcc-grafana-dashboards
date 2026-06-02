# Verbraucher-Energiezuordnung Design

Englische Version: [consumer-energy-attribution-design.md](../../en/design/consumer-energy-attribution-design.md).

Dieses Dokument definiert eine vorgeschlagene Erweiterung des EVCC-VictoriaMetrics-Rollup-Modells, um Verbraucherenergie ihren Versorgungsquellen zuzuordnen.

Ziel ist, Fragen zu beantworten wie:

- wie viel Jahresenergie hat die Waermepumpe verbraucht
- wie viel Jahresenergie haben die Ladestationen verbraucht
- wie viel dieser Energie kam aus PV, Batterieentladung und Netzbezug

## Ziel

Eine technisch konsistente Grundlage fuer Dashboard-Panels schaffen wie:

- `Heat pump energy mix`
- `Charging energy mix`

Jedes Panel soll zeigen koennen:

- Gesamtenergie in `kWh`
- Anteil aus `PV`
- Anteil aus `Battery`
- Anteil aus `Grid`

Das Design soll wiederverwendbar sein fuer:

- `Today`
- `Monat`
- `Jahr`
- `All-time`

## Warum dies ein gemeinsames Modell und eine neue Rollup-Schicht braucht

Das aktuelle Rollup-Modell enthaelt bereits:

- gesamte taegliche Verbraucherenergie pro Loadpoint
- gesamte taegliche Verbraucherenergie pro `EXT`-Titel
- gesamte taegliche Verbraucherenergie pro `AUX`-Titel
- gesamte taegliche PV-Energie
- gesamten taeglichen Netzbezug/-einspeisung
- gesamte taegliche Batterielade-/Entladeenergie

Was es nicht enthaelt, ist eine Quellenzuordnung pro Verbraucher.

Das aktuelle Schema kann also bereits beantworten:

- `How much did the heat pump consume this year?`
- `How much did charging consume this year?`

Es kann aber noch nicht belastbar beantworten:

- `How much of the heat pump energy came from PV?`
- `How much of the charging energy came from battery discharge?`

Ohne zusaetzliche Rollups waeren diese Prozentwerte in Langzeitdashboards nur grobe Dashboard-Heuristiken.

Gleichzeitig soll dieselbe Zuordnungslogik fuer `Today` direkt auf Rohdaten nutzbar sein.

## Akzeptierter Modellierungsansatz

Pro-Bucket-proportionale Zuordnung in der Python-Rollup-Pipeline verwenden.

Die Zuordnung soll auf denselben Rohzeit-Buckets berechnet werden, die bereits fuer taegliche Energie-Rollups genutzt werden.

Dieses Design definiert deshalb:

- einen gemeinsamen Zuordnungsalgorithmus
- einen Rohdaten-Ausfuehrungspfad fuer `Today`
- einen taeglichen Rollup-Ausfuehrungspfad fuer `Monat`, `Jahr` und `All-time`

Empfohlener Bucket:

- `60s`

Fuer jeden Bucket:

1. aktive getrackte Verbraucher bestimmen
2. verfuegbare Versorgungsquellen bestimmen
3. Quellleistung proportional auf getrackte Verbraucher verteilen
4. Bucket-Leistungszuordnung in Energie umrechnen
5. nach Verbraucher und Quelle fuer den lokalen Tag aggregieren

## Getrackte Verbrauchergruppen

Die erste Implementierung soll abdecken:

- `loadpoint`
- `ext title`
- `aux title`

Das ermoeglicht:

- Ladestationen
- Waermepumpe, wenn sie als `EXT` oder `AUX` erscheint
- weitere externe und Auxiliary-Verbraucher

## Versorgungsquellen

Fuer die Zuordnung soll das Modell verwenden:

- `PV`
- `Battery`
- `Grid`

Abgeleitet aus Rohmetriken:

- `pvPower_value`
- `batteryPower_value`
- `gridPower_value`

Operative Interpretation:

- `PV` bedeutet direkt PV-gestuetzten Verbrauch
- `Battery` bedeutet Versorgung durch Batterieentladung
- `Grid` bedeutet Netzimport

## Gemeinsames Ausfuehrungsmodell je Dashboard-Zeitraum

### Today

Fuer `Today` soll die Zuordnung direkt aus Rohmetriken in Grafana-Queries oder in einem dedizierten Helper-Panel-/Library-Modell berechnet werden.

Das bedeutet:

- keine zusaetzlichen taeglichen Rollups fuer `Today` erforderlich
- der Quellen-Split wird ueber den aktuell ausgewaehlten Tagesbereich berechnet
- die zugrunde liegende Zuordnungslogik bleibt dieselbe wie im Rollup-Pfad

### Monat, Jahr und All-time

Fuer `Monat`, `Jahr` und `All-time` soll die Zuordnung auf taeglichen Rollups basieren.

Das bedeutet:

- der Quellen-Split wird einmal in der Python-Rollup-Pipeline berechnet
- Grafana summiert nur bereits zugeordnete taegliche Metriken
- alle Langzeitdashboards verwenden dasselbe gespeicherte Zuordnungsmodell

## Vorgeschlagene taegliche Rollup-Metriken

### Loadpoints

- `evcc_loadpoint_energy_from_pv_daily_wh{local_year="...",local_month="...",loadpoint="..."}`
- `evcc_loadpoint_energy_from_battery_daily_wh{local_year="...",local_month="...",loadpoint="..."}`
- `evcc_loadpoint_energy_from_grid_daily_wh{local_year="...",local_month="...",loadpoint="..."}`

### Externe Zaehler

- `evcc_ext_energy_from_pv_daily_wh{local_year="...",local_month="...",title="..."}`
- `evcc_ext_energy_from_battery_daily_wh{local_year="...",local_month="...",title="..."}`
- `evcc_ext_energy_from_grid_daily_wh{local_year="...",local_month="...",title="..."}`

### Auxiliary-Zaehler

- `evcc_aux_energy_from_pv_daily_wh{local_year="...",local_month="...",title="..."}`
- `evcc_aux_energy_from_battery_daily_wh{local_year="...",local_month="...",title="..."}`
- `evcc_aux_energy_from_grid_daily_wh{local_year="...",local_month="...",title="..."}`

## Optionale aggregierte Helper-Metriken

Diese sind fuer die erste Implementierung nicht erforderlich, koennen Dashboards spaeter aber vereinfachen:

- `evcc_tracked_consumer_energy_daily_wh`
- `evcc_other_energy_daily_wh`

Sie sind nuetzlich, wenn ein spaeteres Panel erklaeren soll, wie viel der gesamten Hauslast nicht Teil der getrackten Verbrauchergruppe ist.

## Zuordnungslogik

### 1. Getrackten Verbraucherbedarf pro Bucket bauen

Pro Bucket nur positiven Bedarf verwenden:

- `chargePower_value` pro `loadpoint`
- `extPower_value` pro `title`
- `auxPower_value` pro `title`

Negative Werte sollen keine zugeordnete Versorgung erzeugen.

Getrackter Verbraucherbedarf:

- `tracked_total_w = sum(all positive tracked consumer powers)`

### 2. Quellenverfuegbarkeit pro Bucket bauen

Verwenden:

- `pv_supply_w = max(pvPower_value, 0)`
- `battery_supply_w = max(batteryPower_value, 0)`, interpretiert als Entladung

Netzbezug soll die Residualquelle sein, die benoetigt wird, um den getrackten Verbrauch zu decken:

- `grid_supply_w = max(tracked_total_w - pv_allocatable_w - battery_allocatable_w, 0)`

Das Zuordnungsmodell darf niemals negative Quellenzuordnungen erzeugen.

### 3. Quellen-Zuordnungsreihenfolge

Empfohlene Reihenfolge:

1. `PV` zuordnen
2. `Battery` zuordnen
3. verbleibenden Bedarf `Grid` zuordnen

Grund:

- direkte PV soll vor importierter Energie verbraucht werden
- Batterieentladung ist eine explizite zweite Versorgungsquelle
- Netzimport ist der Residual-Fallback

### 4. Proportionaler Split pro Verbraucher

Fuer jeden getrackten Verbraucher:

- `consumer_share = consumer_power_w / tracked_total_w`

Dann:

- `consumer_pv_w = pv_allocatable_w * consumer_share`
- `consumer_battery_w = battery_allocatable_w * consumer_share`
- `consumer_grid_w = residual_w * consumer_share`

Dabei gilt:

- `pv_allocatable_w = min(pv_supply_w, tracked_total_w)`
- `remaining_after_pv_w = tracked_total_w - pv_allocatable_w`
- `battery_allocatable_w = min(battery_supply_w, remaining_after_pv_w)`
- `residual_w = max(tracked_total_w - pv_allocatable_w - battery_allocatable_w, 0)`

### 5. In Energie umrechnen

Pro Bucket:

- `energy_wh = power_w * bucket_seconds / 3600`

Dann summieren nach:

- lokalem Tag
- Fachdimension
- Quelle

## Wichtige Grenzen des Modells

Diese Zuordnung ist ein Modell, keine direkt gemessene Wahrheit.

### Warum

Der Rohdatensatz enthaelt keine expliziten Quellenmarker pro Verbraucher.

Er enthaelt:

- Verbraucherleistungen
- globale Quellenleistungen

Der Quellen-Split pro Verbraucher muss deshalb rekonstruiert werden.

### Konsequenzen

Die resultierenden Prozentwerte sollten behandelt werden als:

- operativ nuetzlich
- intern konsistent
- aber weiterhin modelliert

Sie sollten nicht als zaehlerzertifizierte Werte beschrieben werden.

## Empfohlener Umgang mit ungetrackter Last

Eine zentrale Entscheidung ist, ob ungetrackte Last ignoriert oder explizit modelliert wird.

### Empfohlener Default

Fuer die erste Version die Zuordnung nur innerhalb der getrackten Verbrauchergruppe berechnen.

Das bedeutet:

- die Prozentwerte beantworten: `Within this tracked consumer group, how was the energy supplied?`

Das ist die einfachste und stabilste erste Implementierung.

### Optionale spaetere Verfeinerung

Eine interne Residualgruppe hinzufuegen:

- `other/home`

Das wuerde ein vollstaendigeres Energieflussbild ermoeglichen, ist fuer das erste Dashboard-Feature aber nicht erforderlich.

## Dashboard-Designempfehlung

Die Dashboards sollten den visuellen Stil der angehaengten Geraeteliste nicht exakt kopieren.

Empfohlenes Paneldesign:

### Eine Zeile pro Verbrauchergruppe

- `Heat pump`
- `Charging stations`

### Jede Zeile zeigt

- gesamte Jahresenergie in `kWh`
- `PV %`
- `Battery %`
- `Grid %`

Optional:

- ein schmaler gestapelter Quellenbalken in den bestehenden semantischen Farben

### Wiederverwendung je Dashboard-Zeitraum

#### Today

Dasselbe Zeilenkonzept verwenden, die Werte aber aus Rohdaten-Tageszuordnung beziehen.

Empfohlener erster Umfang:

- ein kompaktes Panel fuer `Heat pump`
- ein kompaktes Panel fuer `Charging stations`

#### Monat

Monatssummen der taeglichen Zuordnungsrollups verwenden.

Die visuelle Struktur kann wie in `Jahr` bleiben.

#### Jahr

Jahressummen der taeglichen Zuordnungsrollups verwenden.

Das ist das zuerst empfohlene Implementierungsziel.

#### All-time

All-time-Summen der taeglichen Zuordnungsrollups verwenden.

Fuer `All-time` sollte das Panel wahrscheinlich kompakt bleiben und fokussieren auf:

- gesamte `kWh`
- Quellen-Prozentwerte

ohne das Dashboard mit zu vielen Verbraucherzeilen zu ueberladen.

### Gruppendefinitionen

#### Ladestationen

Verwenden:

- alle sichtbaren Loadpoints nach Dashboard-Blocklists

#### Waermepumpe

Einen ausgewaehlten `EXT`- oder `AUX`-Titel je nach Installation verwenden.

Das benoetigt wahrscheinlich entweder:

- eine Namenskonvention
- oder eine kleine Dashboard-Variable wie `heatPumpTitle`

## Vorgeschlagene Implementierungsphasen

### Phase 1

Neue taegliche Zuordnungsrollups zur Python-Pipeline hinzufuegen.

### Phase 2

Einen kurzen Backfill ueber einen bekannten Datumsbereich ausfuehren und validieren:

- Summen entsprechen der taeglichen Verbraucherenergie
- Quellenanteile summieren sich auf `100%`
- keine negative zugeordnete Energie

### Phase 3

Erstes `Jahr`-Dashboard-Panelpaar hinzufuegen:

- `Heat pump energy mix`
- `Charging energy mix`

### Phase 4

Dieselben zugeordneten taeglichen Rollups wiederverwenden in:

- `Monat`
- `All-time`

### Phase 5

Eine Rohdatenversion desselben Konzepts hinzufuegen zu:

- `Today`

## Validierungsregeln

Jeder lokale Tag und jede Dimension sollte erfuellen:

- `from_pv + from_battery + from_grid ~= total_energy`
- keine Quellenkomponente unter null
- kein Quellenprozentwert ueber `100%`
- Prozentwerte summieren sich innerhalb Rundungstoleranz auf `100%`

## Offene Designentscheidungen

Diese Punkte brauchen noch eine explizite Implementierungsentscheidung:

- ob Waermepumpe aus `EXT`, `AUX` oder einem konfigurierbaren kombinierten Selektor kommen soll
- ob ungetrackte Hauslast ausserhalb des Zuordnungsmodells bleiben soll
- ob das erste Dashboard absolute Quellen-`kWh` zusaetzlich zu Prozentwerten zeigen soll

## Empfehlung

Mit einer ersten Implementierung fortfahren auf Basis von:

- taeglichen Zuordnungsrollups
- proportionaler 60-Sekunden-Quellenzuordnung
- `Jahr`-Dashboard-Panels fuer Waermepumpe und Ladestationen

Danach dasselbe Zuordnungsmodell wiederverwenden fuer:

- `Monat`
- `All-time`
- optional `Today` auf Rohdaten

Das schafft eine stabile und wiederverwendbare Basis, ohne getrennte Heuristiken pro Dashboard-Zeitraum hart zu kodieren.
