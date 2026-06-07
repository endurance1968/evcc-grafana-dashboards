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

## Zusammenspiel mit PV-Gestehungskosten

Die Energiebilanz ist unabhaengig von der Investment-Datei. Dieses Skript importiert nur historische Tagesenergien fuer Gesamt-PV, Haus, Netz und Speicher. Es erzeugt keine PV-Gestehungskosten und importiert keine PV-Ertraege je einzelner Anlage.

Wenn zusaetzlich Gestehungskosten ausgewertet werden sollen, ist der Ablauf getrennt:

1. dieses Skript fuer die systemweite SMA-Energiebilanz ausfuehren,
2. `scripts/helper/import-sma-pv-energy.py` fuer PV-Ertraege je Anlage ausfuehren,
3. `scripts/helper/import-investment-costs.py` fuer die Kostenmetriken ausfuehren.

Beispiel fuer Schritt 3 nach den Importen:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2026-01-01 \
  --energy-source combined \
  --combined-energy-conflict prefer-evcc \
  --skip-titles-without-energy \
  --write-pv-energy-rollup
```

Ohne `--write` ist das ein Trockenlauf. Zum Schreiben denselben Kostenlauf mit `--write --replace` starten.

## Datenverantwortung

Fuer historische Jahre ohne EVCC-Daten ist der Import bewusst als EVCC-Simulation gedacht. Fuer Uebergangszeitraeume mit echten EVCC-Rollups sollte der Zeitraum eingeschraenkt werden, damit SMA- und EVCC-Energie nicht doppelt in denselben Dashboards auftauchen.



