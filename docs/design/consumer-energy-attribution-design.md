# Design: Verbrauchs- und Energiezuordnung

Englische Originalfassung: [consumer-energy-attribution-design_EN.md](./consumer-energy-attribution-design_EN.md).

Dieses Design beschreibt, wie Energieverbrauch in EVCC-Dashboards verschiedenen Verbrauchern zugeordnet werden kann.

## Ziel

Die Dashboards sollen Lasten wie Hausverbrauch, Ladepunkte, Fahrzeuge, Waermepumpe oder sonstige Verbraucher nachvollziehbar darstellen, ohne die Rohdaten zu veraendern.

## Prinzipien

- Rohdaten bleiben Quelle der Wahrheit.
- Zuordnung erfolgt ueber Labels, Dashboard-Variablen und Rollup-Logik.
- Blocklists verhindern Doppelzaehlung oder unerwuenschte Anzeige.
- Waermepumpen- und Zusatzverbraucher koennen per Regex erkannt werden.

## Relevante Variablen

```env
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|wärmepumpe|heat pump).*"
```

## Qualitaetskriterien

- keine Doppelzaehlung
- nachvollziehbare Labelauswahl
- sinnvolle Defaults fuer Einsteiger
- Overrides fuer individuelle Anlagen
- Query-Readback fuer kritische Panels

## Offene Themen

- klarere No-Data-Zustaende
- sichtbare Datenqualitaets-/Label-Hinweise
- bessere Dokumentation fuer Sonderfaelle mit mehreren Verbrauchern

Die englische Fassung enthaelt die ausfuehrlichere Entwurfshistorie und Alternativen.