# Dashboard-Farbschema

Die VictoriaMetrics-Dashboards verwenden ein gemeinsames semantisches Farbschema. Gleiche Energie- und Leistungsarten sollen in allen Dashboards gleich aussehen, unabhaengig davon, ob sie als Gauge, Time series, Bar gauge oder Balkendiagramm dargestellt werden.

Die zentrale technische Quelle ist `scripts/helper/dashboard-colors.mjs`. Aenderungen am Farbschema sollen dort beginnen und danach mit `node scripts/helper/apply-dashboard-colors.mjs` auf die Original-Dashboards angewendet werden. Die lokalisierten Dashboards unter `dashboards/translation/` werden anschliessend aus den Original-Dashboards neu generiert.

## Farben

| Bedeutung | Farbe | Hex / Grafana-Farbe | Verwendung |
| --- | --- | --- | --- |
| PV | Gruen | `#2F8F5B` | PV-Leistung, PV-Energie, PV-Balken |
| PV dunkel | Dunkelgruen | `#1B5E20` | hoher PV-Bereich in Gauge-Schwellen |
| PV Forecast | Gruen, gestrichelt | `#2F8F5B` | EVCC `tariffSolar_value` Forecast-Linien |
| Netz allgemein | Gelb | `#E0B400` | Netzserie, wenn Bezug/Einspeisung nicht getrennt dargestellt wird |
| Netzbezug | Gelb | `#E0B400` | Bezug aus dem Netz |
| Einspeisung | Tuerkis | `#14B8A6` | Einspeisung ins Netz, getrennt von Netzbezug und PV |
| Speicher | Blau | `#3274D9` | Speicherstand, Speicherleistung, allgemeine Speicherwerte |
| Speicher laden | Hellblau | `#73A7F2` | Ladeenergie oder negative Speicherleistung |
| Speicher entladen | Blau | `#3274D9` | Entladeenergie oder positive Speicherleistung |
| Speicher hoch | Dunkelblau | `#1F60A8` | hoher Speicherleistungsbereich in Gauge-Schwellen |
| Haus | Violett | `#9F7AEA` | Hausverbrauch und Verbrauchsverteilung |
| Ladepunkte | Orange | `#FF9830` | dynamische Ladepunktserien als Default-Farbe |
| Ladepunkte hoch | Dunkelorange | `#E66A00` | hoher Ladepunktleistungsbereich in Gauge-Schwellen |
| Autarkie | Schwellenfarben | `red`, `orange`, `yellow`, `green` | Gauge-Schwellen: bis 25 %, bis 50 %, bis 75 %, danach gruen |
| Eigenverbrauch | Tuerkis | `#14B8A6` | Eigenverbrauchs-Gauge und Verlauf |
| Einkauf / Kosten | Rot | `red` | Stromkosten, Einkauf, negative Kostensicht |
| Verkauf / Verguetung | Gruen | `green` | Einspeiseverguetung oder Verkauf |

## Gauge-Regeln

Die Leistungs-Gauges im Today-Dashboard sind bewusst unterschiedlich skaliert:

- Netz und Speicher sind signiert: `-11 kW` bis `+11 kW`.
- Haus und Ladepunkte sind nur positiv: `0 kW` bis `11 kW`.
- PV ist nur positiv: `0 kW` bis zur installierten PV-Leistung. Der Deploy-Prozess kann den Maximalwert ueber `installedWattPeak` anpassen.
- Ladepunkte sind dynamisch, weil EVCC-Nutzer die Namen frei vergeben koennen. Deshalb verwenden Ladepunkte Default-Schwellen statt harter `byName`-Overrides.

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
