# SMA-PV-Daten nach VictoriaMetrics importieren

Diese Seite beschreibt den optionalen Import von SMA-Portal- oder Sunny-Portal-PV-Ertragsdaten je PV-Anlage nach VictoriaMetrics. Der Importer ist fuer Vergleich, Plausibilitaetspruefung und historische PV-Tagesertraege gedacht. Er ersetzt keine EVCC-Live-Rohdaten und schreibt bewusst nicht in `pvPower_value`. Systemweite SMA-Energiebilanzdaten fuer alte EVCC-freie Jahre sind separat beschrieben: [sma-energy-balance-import.md](./sma-energy-balance-import.md).

## Zweck

EVCC liefert die Live-Leistungsdaten, die die Dashboards heute verwenden. SMA-Exports liefern typischerweise Tagesertraege aus dem Wechselrichter- oder Portalumfeld. Diese Daten koennen helfen bei:

- Plausibilitaetscheck EVCC-PV-Ertrag gegen SMA-Portal,
- Nachimport historischer Tagesertraege ueber mehrere Jahre,
- Erkennen von Mapping-Problemen zwischen EVCC-Titeln und SMA-Portalnamen,
- Anzeigen historischer PV-Tagesertraege, wenn EVCC selbst fuer diese Jahre keine PV-Tagesdaten enthaelt.

Der SMA-Importer schreibt standardmaessig in die EVCC-kompatible per-title Tagesmetrik:

```text
evcc_pv_energy_by_title_daily_wh{title="...", local_year="YYYY", local_month="MM"}
```

`title` ist der EVCC-/VictoriaMetrics-Titel. SMA-Komponenten werden vorher ueber die Mapping-Datei auf diesen Titel abgebildet und pro Tag/Titel summiert. Die Import-Zusammenfassung zeigt weiterhin, welche SMA-Namen zu welchem Titel beigetragen haben.

## Unterstuetzte Eingabeformate

### SMA Portal Classic Analyse-Monatsdateien

Validiert ist das klassische SMA-Portal-Analyseformat mit Dateien nach dem Muster `Analyse_YYYY_MM.csv`. Die Spalten enthalten Portal-Komponenten wie `Norddach 10000TL-20 / Gesamtertrag / Mittelwerte [kWh]`, die Zeilen enthalten lokale Tageswerte in kWh.

Beispielimport eines ganzen Verzeichnisses:

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --vm-base-url http://localhost:8428 \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^backnang_home$' \
  --write --replace
```

`--exclude-name-regex` ist wichtig, wenn der Export neben den Einzelkomponenten auch eine Portal-Gesamtsumme enthaelt. Diese Summe darf nicht zusammen mit den Einzelkomponenten importiert werden, sonst wird PV-Ertrag doppelt gezaehlt.

### Long-Format

Vorlage: `data/examples/sma-pv-energy-long.example.csv`

```csv
date,sma_name,energy_kwh
2026-06-01,SMA Portal Nord,12.4
2026-06-01,SMA Portal Sued,9.8
```

### Wide-Format

Vorlage: `data/examples/sma-pv-energy-wide.example.csv`

```csv
date,SMA Portal Nord,SMA Portal Sued,SMA Portal West
2026-06-01,12.4,9.8,1.6
2026-06-02,13.1,10.2,1.4
```

Der Importer erkennt Komma, Semikolon und Tabulator als Trennzeichen. Dezimal-Komma wird unterstuetzt.

## Mapping-Datei

Vorlage: `data/examples/sma-pv-name-map.example.csv`

```csv
sma_name,evcc_title
norddach_10000tl-20,SMA-Nord
suddach_5000tl-20,SMA-Sued
carport_4000tl-21,SMA-Carport
```

`evcc_title` ist Pflicht und muss zu dem Titel passen, unter dem die Anlage in den Dashboards ausgewertet werden soll. Fuer SMA-Portal-Classic werden die Portal-Komponentennamen normalisiert: Umlaute werden ASCII, Leerzeichen werden `_`, Gross-/Kleinschreibung ist egal.

Mehrere SMA-Komponenten duerfen auf denselben `evcc_title` zeigen, zum Beispiel wenn ein Wechselrichter ersetzt wurde und beide Portalnamen zur gleichen Anlage gehoeren. Der Import summiert solche Tageswerte pro EVCC-Titel.

## Trockenlauf

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^portal_gesamt$'
```

Der Trockenlauf zeigt Serien, Samples, Zeitraum, gemappte Titel und Energie je Titel. Es wird nichts nach VictoriaMetrics geschrieben.

## Schreiben nach VictoriaMetrics

Wenn der Trockenlauf plausibel aussieht, kann der Import in die Ziel-VM geschrieben werden:

```bash
python3 scripts/helper/import-sma-pv-energy.py \
  --vm-base-url http://localhost:8428 \
  --format sma-portal-classic-analysis \
  --input-dir data/private/sma-portal/Analyse/Monate \
  --map-file data/private/sma-pv-name-map.csv \
  --require-mapping \
  --exclude-name-regex '^portal_gesamt$' \
  --write --replace
```

`--replace` loescht beim SMA-PV-Importer nur die mit `--metric` ausgewaehlte Zielmetrik. Der Default ist `evcc_pv_energy_by_title_daily_wh`. Das ist fuer einen kontrollierten Neuimport gedacht und veraendert keine EVCC-Rohdaten wie `pvPower_value` und keine vom Kostenhelper erzeugten Investment- oder Gestehungskostenmetriken.

## Ergebnis pruefen

Nach dem Import sollten die erwarteten Titel und Zeitraeume in VictoriaMetrics sichtbar sein:

```bash
curl "http://localhost:8428/api/v1/series?match[]=evcc_pv_energy_by_title_daily_wh"
```

Fuer eine schnelle Plausibilitaetspruefung kann je Titel die importierte Energie summiert werden:

```bash
curl --get "http://localhost:8428/api/v1/query" \
  --data-urlencode 'query=sum(evcc_pv_energy_by_title_daily_wh) by (title) / 1000'
```

## Zusammenspiel mit EVCC-Live-PVs

Der SMA-PV-Importer bleibt ein reiner Importer. Er schreibt Tagesertraege je `title` in `evcc_pv_energy_by_title_daily_wh` und berechnet keine weiteren Kennzahlen. Der Investment-Helper liest diese Energie bei Bedarf nur als Quelle und schreibt sie nicht selbst.

## Sicherheit

Nur auf eine Ziel- oder Test-VM schreiben, niemals unkontrolliert auf eine produktive Instanz. Vor `--write --replace` immer den Trockenlauf pruefen. `--replace` ist fuer wiederholbare Neuimporte gedacht und betrifft beim SMA-PV-Importer nur die Zielmetrik des SMA-PV-Imports.
