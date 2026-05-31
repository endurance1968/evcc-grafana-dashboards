# VictoriaMetrics Schema-Referenz

Englische Originalfassung: [victoriametrics-schema-reference_EN.md](./victoriametrics-schema-reference_EN.md).

Diese Referenz beschreibt die wichtigsten Metrikfamilien fuer die EVCC-Dashboards.

## Rohdaten

Rohdaten stammen aus EVCC bzw. aus der migrierten InfluxDB-Historie. Sie werden fuer die Today-Dashboards verwendet.

Typische Familien:

- PV-Leistung und PV-Energie
- Netzbezug und Einspeisung
- Hausverbrauch
- Batterie-SOC, Ladeleistung und Entladeleistung
- Ladepunkte und Fahrzeuge
- Preise und Tarife
- Forecast-Daten

## Rollup-Metriken

Taegliche Langzeitmetriken verwenden den Prefix `evcc_*`. Sie werden von `evcc-vm-rollup.py` erzeugt und von `Month`, `Year` und `All-time` genutzt.

Beispiele:

- Tagesenergie fuer PV, Netz, Batterie und Verbrauch
- Kosten und Tarife
- Fahrzeug- und Ladepunktaggregate
- Autarkie- und Eigenverbrauchswerte

## Label-Regeln

- Labels muessen stabil bleiben, damit Dashboards Zeitraeume vergleichen koennen.
- Anzeigenamen sollten ueber Dashboard-Variablen oder Overrides gesteuert werden.
- Blocklists duerfen Reihen ausblenden, aber keine Daten veraendern.
- Import-Rewrite-Werkzeuge nur bewusst und nachvollziehbar einsetzen.

## Datasource

Die Standard-Datasource UID ist `vm-evcc`. Abweichungen werden beim Deployment ueber `GRAFANA_DS_VM_EVCC_UID` ersetzt.

## Validierung

Aenderungen am Schema sollten mindestens ausloesen:

```bash
npm test
npm run test:query-readback
npm run test:render-e2e
```

Bei Rollup-Aenderungen:

```bash
npm run test:rollup-path
```

Die englische Fassung enthaelt die detailliertere historische Feld- und Query-Referenz.