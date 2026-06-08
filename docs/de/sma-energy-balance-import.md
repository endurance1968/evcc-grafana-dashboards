# SMA-Energiebilanz nach EVCC/VictoriaMetrics importieren

Diese Seite beschreibt den optionalen Import von SMA-Energiebilanz-Monatsdateien nach VictoriaMetrics. Der Import ist fuer historische Jahre gedacht, in denen keine EVCC-Daten vorhanden sind. Er erzeugt bewusst EVCC-kompatible Tages-Rollups, aber keine EVCC-Rohmetriken.

## Zweck

SMA-Energiebilanzdateien enthalten Tageswerte fuer das Gesamtsystem, zum Beispiel PV-Erzeugung, Hausverbrauch, Netzbezug, Einspeisung und Speicherenergie. Damit lassen sich alte Jahre in den `Month`, `Year` und `All-time` Dashboards darstellen, obwohl EVCC damals noch keine Rohdaten nach VictoriaMetrics geliefert hat.

Nicht moeglich sind daraus `Today`-Zeitverlaeufe, Ladepunkte, Fahrzeuge, einzelne Verbraucher, SOC-Min/Max oder 15-Minuten-Ansichten. Die Dateien enthalten nur Tagesenergie, keine Leistungskurven.

## Eingabeformat

Unterstuetzt sind SMA-Dateien nach dem Muster:

```text
Energiebilanz_YYYY_MM.csv
```

Die Dateien enthalten Tageszeilen und Spalten wie:

- `Gesamtverbrauch / Zähleränderung [kWh]`
- `Direktverbrauch / Zähleränderung [kWh]`
- `Batterieentladung / Zähleränderung [kWh]`
- `Netzbezug / Zähleränderung [kWh]`
- `PV-Erzeugung / Zähleränderung [kWh]`
- `Netzeinspeisung / Zähleränderung [kWh]`
- `Batterieladung / Zähleränderung [kWh]`

Dezimal-Komma und Excel-Formeldatumswerte wie `="01.06.2024"` werden unterstuetzt. Eine Jahresuebersichtsdatei wie `Energiebilanz_2014_2025.csv` wird beim Tagesimport ignoriert.

## Erzeugte Metriken

Der Importer schreibt Tageswerte mit `source="sma_energy_balance"` und den ueblichen `local_year` / `local_month` Labels:

```text
evcc_home_energy_daily_wh
evcc_pv_energy_daily_wh
evcc_grid_import_daily_wh
evcc_grid_export_daily_wh
evcc_battery_charge_daily_wh
evcc_battery_discharge_daily_wh
evcc_pv_direct_consumption_daily_wh
```

Damit verhalten sich die historischen SMA-Tageswerte fuer die Langzeitdashboards wie EVCC-Rollups. Die Source bleibt sichtbar und kann bei Bedarf gezielt ersetzt werden.

## Trockenlauf

```bash
python3 scripts/helper/import-sma-energy-balance.py \
  --input-dir data/private/sma-portal/Energie/Monate \
  --start 2015-01-01 \
  --end 2024-07-01
```

Der Trockenlauf zeigt Zeitraum, Serien, Samples und Summen je Energieart. Es wird nichts geschrieben.

## Schreiben nach VictoriaMetrics

Nur auf eine Ziel- oder Test-VM schreiben, nicht auf eine produktive Read-only-Instanz:

```bash
python3 scripts/helper/import-sma-energy-balance.py \
  --vm-base-url http://localhost:8428 \
  --input-dir data/private/sma-portal/Energie/Monate \
  --start 2015-01-01 \
  --end 2024-07-01 \
  --write --replace
```

`--replace` loescht nur die von diesem Importer erzeugten Serien mit `source="sma_energy_balance"`. Andere EVCC-Rollups bleiben erhalten.

## Abgrenzung der importierten Daten

Dieses Skript importiert nur historische Tagesenergien fuer Gesamt-PV, Haus, Netz und Speicher. Es importiert keine PV-Ertraege je einzelner Anlage und erzeugt keine Leistungszeitreihen.

Fuer historische Jahre ohne EVCC-Daten ist der Import bewusst als EVCC-kompatibler Tagesrollup gedacht. Fuer Uebergangszeitraeume mit echten EVCC-Rollups sollte der Importzeitraum eingeschraenkt werden, damit SMA- und EVCC-Energie nicht doppelt in denselben Dashboards auftauchen.

