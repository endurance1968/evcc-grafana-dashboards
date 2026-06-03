# Dashboard-Farbschema

Die VictoriaMetrics-Dashboards verwenden ein gemeinsames semantisches Farbschema. Gleiche Energie- und Leistungsarten sollen in allen Dashboards gleich aussehen, unabhaengig davon, ob sie als Gauge, Time series, Bar gauge oder Balkendiagramm dargestellt werden.

Die zentrale technische Quelle ist `scripts/helper/dashboard-colors.mjs`. Aenderungen am Farbschema sollen dort beginnen und danach mit `scripts/helper/apply-dashboard-colors.mjs` auf die Original-Dashboards angewendet werden. Die lokalisierten Dashboards unter `dashboards/translation/` werden anschliessend aus den Original-Dashboards neu generiert.

## Farben

| Bedeutung | Farbe | Hex / Grafana-Farbe | Verwendung |
| --- | --- | --- | --- |
| PV niedrig | Hellgruen | `#A8DDB5` | niedriger PV-Bereich in Gauge-Schwellen |
| PV | Gruen | `#2F8F5B` | PV-Leistung, PV-Energie, PV-Balken |
| PV hoch | Dunkelgruen | `#1B5E20` | hoher PV-Bereich in Gauge-Schwellen |
| PV Forecast | Gruen, gestrichelt | `#2F8F5B` | EVCC `tariffSolar_value` Forecast-Linien |
| Netz allgemein | Gelb | `#E0B400` | Netzserie, wenn Bezug/Einspeisung nicht getrennt dargestellt wird |
| Einspeisung | Hellgelb | `#F8E7A1` | Einspeisung ins Netz, getrennt von Netzbezug und PV |
| Netzbezug | Gelb | `#E0B400` | Bezug aus dem Netz |
| Netzbezug hoch | Amber | `#C98200` | hoeherer Netzbezug in Gauge-Schwellen |
| Netzbezug kritisch | Braunorange | `#B85C2A` | sehr hoher Netzbezug in Gauge-Schwellen |
| Speicher | Blau | `#3274D9` | Speicherstand, Speicherleistung, allgemeine Speicherwerte |
| Speicher laden niedrig | Hellblau | `#A8CBFF` | niedrige Ladeleistung oder negative Speicherleistung |
| Speicher laden | Blauhell | `#73A7F2` | Ladeenergie oder negative Speicherleistung |
| Speicher entladen | Blau | `#3274D9` | Entladeenergie oder positive Speicherleistung |
| Speicher entladen hoch | Dunkelblau | `#1F60A8` | hoher Entladebereich in Gauge-Schwellen |
| Speicher kritisch | Tiefblau | `#174A7C` | sehr hoher Speicherleistungsbereich in Gauge-Schwellen |
| Speicher-SOC niedrig | Sehr helles Blau | `#D6E8FF` | niedriger Bereich in Speicher-SOC-Gauge-Schwellen |
| Speicher-SOC mittel | Hellblau | `#A8CBFF` | mittlerer Bereich in Speicher-SOC-Gauge-Schwellen |
| Speicher-SOC | Blauhell | `#73A7F2` | normaler Bereich in Speicher-SOC-Gauge-Schwellen |
| Speicher-SOC hoch | Blau | `#3274D9` | hoher Bereich in Speicher-SOC-Gauge-Schwellen |
| Haus niedrig | Hellviolett | `#CDB6F6` | niedriger Hausverbrauch in Gauge-Schwellen |
| Haus | Violett | `#9F7AEA` | Hausverbrauch und Verbrauchsverteilung |
| Haus hoch | Dunkelviolett | `#7C5BD6` | hoeherer Hausverbrauch in Gauge-Schwellen |
| Haus kritisch | Rotviolett | `#A44C9C` | sehr hoher Hausverbrauch in Gauge-Schwellen |
| Ladepunkte niedrig | Hellorange | `#FFC078` | niedrige dynamische Ladepunktleistung |
| Ladepunkte | Orange | `#FF9830` | dynamische Ladepunktserien als Default-Farbe |
| Ladepunkte hoch | Dunkelorange | `#E66A00` | hoher Ladepunktleistungsbereich in Gauge-Schwellen |
| Ladepunkte kritisch | Braunorange | `#B84A1C` | sehr hoher Ladepunktleistungsbereich in Gauge-Schwellen |
| Autarkie niedrig | Hellgruen | `#D8F3DC` | niedriger Bereich in Autarkie-Gauge-Schwellen |
| Autarkie mittel | Gruenhell | `#A8DDB5` | mittlerer Bereich in Autarkie-Gauge-Schwellen |
| Autarkie | Gruen | `#73BF69` | Autarkie-Gauge und Verlauf |
| Autarkie hoch | Dunkelgruen | `#2F8F5B` | hoher Bereich in Autarkie-Gauge-Schwellen |
| Eigenverbrauch niedrig | Helltuerkis | `#CFFAFE` | niedriger Bereich in Eigenverbrauch-Gauge-Schwellen |
| Eigenverbrauch mittel | Tuerkishell | `#5EEAD4` | mittlerer Bereich in Eigenverbrauch-Gauge-Schwellen |
| Eigenverbrauch | Tuerkis | `#14B8A6` | Eigenverbrauchs-Gauge und Verlauf |
| Eigenverbrauch hoch | Dunkeltuerkis | `#0F766E` | hoher Bereich in Eigenverbrauch-Gauge-Schwellen |
| Einkauf / Kosten | Rot | `red` | Stromkosten, Einkauf, negative Kostensicht |
| Verkauf / Verguetung | Gruen | `green` | Einspeiseverguetung oder Verkauf |

## Gauge-Regeln

Die Leistungs-Gauges im Today-Dashboard sind bewusst unterschiedlich skaliert:

- Netz und Speicher sind signiert: `-11 kW` bis `+11 kW`.
- Netz und Speicher verwenden in den Gauges `neutral=0`, damit der Balken bei `0` startet und je nach Vorzeichen in die passende Richtung laeuft.
- Haus und Ladepunkte sind nur positiv: `0 kW` bis `11 kW`.
- PV ist nur positiv: `0 kW` bis zur installierten PV-Leistung. Der Deploy-Prozess kann den Maximalwert ueber `installedWattPeak` anpassen.
- Ladepunkte sind dynamisch, weil EVCC-Nutzer die Namen frei vergeben koennen. Deshalb verwenden Ladepunkte Default-Schwellen statt harter `byName`-Overrides.

Gauge-Schwellen bleiben innerhalb derselben Farbfamilie:

- Netz nutzt gelbe Abstufungen: Einspeisung/geringer Bezug hell, normaler Bezug gelb, hoher Bezug amber, sehr hoher Bezug gelb mit Rotanteil.
- Speicher nutzt blaue Abstufungen fuer Laden und Entladen.
- PV nutzt gruene Abstufungen von hell bis dunkel.
- Haus nutzt violette Abstufungen.
- Ladepunkte nutzen orange Abstufungen.
- Autarkie nutzt gruene Abstufungen statt Ampelfarben.
- Eigenverbrauch nutzt tuerquise Abstufungen.
- Speicher-SOC nutzt blaue Abstufungen passend zur Speicher-Grundfarbe.

## Pflegehinweise

Neue Panels sollen zuerst semantisch eingeordnet werden: PV, Netzbezug, Einspeisung, Speicher, Haus, Ladepunkt, Autarkie, Eigenverbrauch oder Kosten. Danach soll dieselbe Farbe wie in dieser Referenz verwendet werden.

Die statische Absicherung liegt in `scripts/test/dashboard-semantic-check.mjs`. Der Check verhindert, dass zentrale Serien wie PV, Netz, Einspeisung, Speicher, Haus, Autarkie und Eigenverbrauch wieder unterschiedliche Farben bekommen.

Empfohlener Ablauf nach Farbaenderungen:

```powershell
node scripts/helper/apply-dashboard-colors.mjs
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm test
npm run test:render-e2e
```
