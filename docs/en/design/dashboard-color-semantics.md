# Dashboard Color Semantics

The VictoriaMetrics dashboards use one shared semantic color scheme. The same energy and power domains should look the same across all dashboards, regardless of whether they are rendered as gauges, time series, bar gauges, or bar charts.

The central technical source is `scripts/helper/dashboard-colors.mjs`. Color changes should start there and then be applied to the original dashboards with `scripts/helper/apply-dashboard-colors.mjs`. Localized dashboards under `dashboards/translation/` are regenerated from the original dashboards afterwards.

## Colors

| Meaning | Color | Hex / Grafana color | Usage |
| --- | --- | --- | --- |
| PV low | Light green | `#A8DDB5` | low PV range in gauge thresholds |
| PV | Green | `#2F8F5B` | PV power, PV energy, PV bars |
| PV high | Dark green | `#1B5E20` | high PV range in gauge thresholds |
| PV forecast | Green, dashed | `#2F8F5B` | EVCC `tariffSolar_value` forecast lines |
| Grid general | Yellow | `#E0B400` | grid series when import/export are not split |
| Feed-in | Light yellow | `#F8E7A1` | energy exported to the grid, distinct from grid import and PV |
| Grid import | Yellow | `#E0B400` | energy imported from the grid |
| Grid import high | Amber | `#C98200` | higher grid import in gauge thresholds |
| Grid import critical | Brown orange | `#B85C2A` | very high grid import in gauge thresholds |
| Storage | Blue | `#3274D9` | storage level, storage power, general storage values |
| Storage charge low | Light blue | `#A8CBFF` | low charge power or negative storage power |
| Storage charge | Soft blue | `#73A7F2` | charge energy or negative storage power |
| Storage discharge | Blue | `#3274D9` | discharge energy or positive storage power |
| Storage discharge high | Dark blue | `#1F60A8` | high discharge range in gauge thresholds |
| Storage critical | Deep blue | `#174A7C` | very high storage-power range in gauge thresholds |
| Storage SOC low | Very light blue | `#D6E8FF` | low range in storage-SOC gauge thresholds |
| Storage SOC medium | Light blue | `#A8CBFF` | medium range in storage-SOC gauge thresholds |
| Storage SOC | Soft blue | `#73A7F2` | regular range in storage-SOC gauge thresholds |
| Storage SOC high | Blue | `#3274D9` | high range in storage-SOC gauge thresholds |
| Home low | Light violet | `#CDB6F6` | low house consumption in gauge thresholds |
| Home | Violet | `#9F7AEA` | house consumption and consumption distribution |
| Home high | Dark violet | `#7C5BD6` | higher house consumption in gauge thresholds |
| Home critical | Red violet | `#A44C9C` | very high house consumption in gauge thresholds |
| Loadpoints low | Light orange | `#FFC078` | low dynamic loadpoint power |
| Loadpoints | Orange | `#FF9830` | dynamic loadpoint series default color |
| Loadpoints high | Dark orange | `#E66A00` | high loadpoint-power range in gauge thresholds |
| Loadpoints critical | Brown orange | `#B84A1C` | very high loadpoint-power range in gauge thresholds |
| Autarky low | Light green | `#D8F3DC` | low range in autarky gauge thresholds |
| Autarky medium | Soft green | `#A8DDB5` | medium range in autarky gauge thresholds |
| Autarky | Green | `#73BF69` | autarky gauge and history |
| Autarky high | Dark green | `#2F8F5B` | high range in autarky gauge thresholds |
| Self-consumption low | Light violet | `#F5D8F1` | low range in self-consumption gauge thresholds |
| Self-consumption medium | Soft violet | `#DFA8D8` | medium range in self-consumption gauge thresholds |
| Self-consumption | Red violet | `#A44C9C` | self-consumption gauge and history, close to the home-consumption color family |
| Self-consumption high | Dark violet | `#7C3A75` | high range in self-consumption gauge thresholds |
| Green share low | Very light teal | `#D7F4E8` | low range in green-share gauge thresholds |
| Green share medium | Soft teal | `#8AD7BD` | medium range in green-share gauge thresholds |
| Green share | Teal green | `#43A67A` | EVCC green-share gauge and history |
| Green share high | Dark teal green | `#217A55` | high range in green-share gauge thresholds |
| Purchase / costs | Red | `red` | electricity cost, purchase, negative cost perspective |
| Sold / compensation | Green | `green` | feed-in compensation or sold energy |

## Gauge Rules

The power gauges in the Today dashboard intentionally use different scales:

- Grid and storage are signed: `-11 kW` to `+11 kW`.
- The gauge panel uses `neutral=0` as a panel default. Grafana shows this under gauge options, not as a visible field override; this makes the bar start at `0` and lets grid and storage extend in the matching direction based on the sign.
- Home and loadpoints are rendered as negative consumers in the Today power gauge: `-11 kW` to `0 kW`.
- PV is positive only: `0 kW` to the installed PV peak power. The deploy process can adjust the maximum via `installedWattPeak`.
- Loadpoints are dynamic because EVCC users can choose arbitrary names. Therefore loadpoints use default thresholds instead of hard `byName` overrides.

Gauge thresholds stay within the same color family:

- Grid uses yellow shades: feed-in/low import is light, regular import is yellow, high import is amber, very high import adds a red touch.
- Storage uses blue shades for charge and discharge.
- PV uses green shades from light to dark.
- Home uses violet shades.
- Loadpoints use orange shades.
- Autarky uses green shades instead of traffic-light colors.
- Self-consumption uses violet/red-violet shades close to the home color family.
- Green share uses teal-green shades so it is visually related to PV/autarky but still distinct.
- Storage SOC uses blue shades matching the storage base color.

## Maintenance Notes

New panels should first be classified semantically: PV, grid import, feed-in, storage, home, loadpoint, autarky, self-consumption, green share, or costs. Then use the same color as documented here.

Static protection lives in `scripts/test/dashboard-semantic-check.mjs`. The check prevents central series such as PV, grid, feed-in, storage, home, autarky, self-consumption, and green share from drifting back to inconsistent colors.

Recommended workflow after color changes:

```powershell
node scripts/helper/apply-dashboard-colors.mjs
node scripts/localization/generate-localized-dashboards.mjs
node scripts/localization/apply-safe-display-translations.mjs
npm test
npm run test:render-e2e
```
