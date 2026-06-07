# SMA-PV-Daten nach VictoriaMetrics importieren

Diese Seite beschreibt den optionalen Import von SMA-Portal- oder Sunny-Portal-PV-Ertragsdaten je PV-Anlage nach VictoriaMetrics. Der Importer ist fuer Vergleichs-, Plausibilitaets- und historische Gestehungskosten gedacht. Er ersetzt keine EVCC-Live-Rohdaten und schreibt bewusst nicht in `pvPower_value`. Systemweite SMA-Energiebilanzdaten fuer alte EVCC-freie Jahre sind separat beschrieben: [sma-energy-balance-import.md](./sma-energy-balance-import.md).

## Zweck

EVCC liefert die Live-Leistungsdaten, die die Dashboards heute verwenden. SMA-Exports liefern typischerweise Tagesertraege aus dem Wechselrichter- oder Portalumfeld. Diese Daten koennen helfen bei:

- Plausibilitaetscheck EVCC-PV-Ertrag gegen SMA-Portal,
- Nachimport historischer Tagesertraege ueber mehrere Jahre,
- Erkennen von Mapping-Problemen zwischen EVCC-Titeln und SMA-Portalnamen,
- Auswertung historischer PV-Gestehungskosten, wenn EVCC selbst fuer diese Jahre keine PV-Tagesdaten enthaelt.

Der SMA-Importer schreibt standardmaessig in die EVCC-kompatible Tagesmetrik:

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

`--exclude-name-regex` ist wichtig, wenn der Export neben den Einzelkomponenten auch eine Portal-Gesamtsumme enthaelt. Diese Summe darf fuer Anlagenkosten nicht zusammen mit den Einzelkomponenten importiert werden, sonst wird PV-Ertrag doppelt gezaehlt.

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

`evcc_title` muss zu den Titeln passen, die in der Investment-Datei verwendet werden. Fuer SMA-Portal-Classic werden die Portal-Komponentennamen normalisiert: Umlaute werden ASCII, Leerzeichen werden `_`, Gross-/Kleinschreibung ist egal.

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

## Gestehungskosten aus SMA-Tagesertraegen berechnen

Nach dem SMA-Import kann der Investment-Helper die Kostenmetriken direkt aus dieser Standard-Tagesmetrik erzeugen. `--pv-energy-metric` ist dafuer nicht noetig, weil `evcc_pv_energy_by_title_daily_wh` der Default ist:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2024-07-01 \
  --energy-source daily-metric \
  --skip-titles-without-energy \
  --write-pv-energy-rollup \
  --write --replace
```

`--skip-titles-without-energy` verhindert, dass Investitionskosten von EVCC-Anlagen ohne passende SMA-Historie in die Gesamtkosten eingehen. Das ist besonders wichtig, wenn die heutige EVCC-Anlagenstruktur feiner ist als die alte SMA-Portalstruktur.

Der Helper erzeugt weiterhin die normalen Dashboard-Metriken wie `evcc_pv_lcoe_yearly_ct_per_kwh` und `evcc_pv_effective_lcoe_yearly_ct_per_kwh`. Die Dashboards muessen dafuer keine langen SMA-spezifischen Queries enthalten.

Mit `--write-pv-energy-rollup` schreibt der Helper zusaetzlich einen EVCC-kompatiblen Tagesertrag:

```text
evcc_pv_energy_daily_wh{source="sma", local_year="YYYY", local_month="MM"}
```

Damit koennen die normalen PV-Jahres- und Monats-Panels historische SMA-Ertraege anzeigen, auch wenn fuer diese Jahre keine EVCC-PV-Tagesrollups vorhanden sind. Diese Option nur fuer bewusst importierte Historien oder Testsysteme verwenden. Wenn im gleichen Zeitraum bereits echte EVCC-Rollups fuer `evcc_pv_energy_daily_wh` existieren, wuerden SMA- und EVCC-Ertrag zusammen gezaehlt.

## Zusammenspiel mit EVCC-Live-PVs

Der SMA-PV-Importer bleibt ein reiner Importer. Er schreibt `evcc_pv_energy_by_title_daily_wh` und berechnet keine Gestehungskosten. Wenn SMA-Historie und heutige EVCC-PVs gemeinsam ausgewertet werden sollen, zuerst SMA importieren und danach den Investment-Helper auf `--energy-source combined` setzen.

Trockenlauf fuer die Kostenberechnung nach einem bereits erledigten SMA-Import:

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

Schreiben auf die Ziel-VM erst nach erfolgreichem Trockenlauf:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2015-01-01 \
  --end 2026-01-01 \
  --energy-source combined \
  --combined-energy-conflict prefer-evcc \
  --skip-titles-without-energy \
  --write-pv-energy-rollup \
  --write --replace
```

Bei `--energy-source combined` werden EVCC-`pvPower_value` und die Tagesmetrik `evcc_pv_energy_by_title_daily_wh` pro `evcc_title` zusammengefuehrt. Standard ist `--combined-energy-conflict prefer-evcc`: wenn fuer denselben Tag beide Quellen Werte liefern, zaehlt EVCC und der SMA-Wert wird fuer diesen Tag ignoriert. Das verhindert doppelte PV-Ertraege im Uebergangszeitraum. Die Zusammenfassung zeigt pro Titel `evcc_days`, `metric_days`, `overlap_days` und `merged_days`.

## Sicherheit

Nur auf eine Ziel- oder Test-VM schreiben, niemals auf die produktive Read-only-Instanz. `--replace` loescht beim SMA-Importer die mit `--metric` ausgewaehlte Zielmetrik; der Default ist `evcc_pv_energy_by_title_daily_wh`. Das ist fuer einen kontrollierten Neuimport gedacht. Beim Investment-Helper werden die generierten `evcc_pv_*` Kostenmetriken neu geschrieben. Wenn `--write-pv-energy-rollup` aktiv ist, loescht der Helper vor dem Reimport nur `evcc_pv_energy_daily_wh{source="sma"}` beziehungsweise `evcc_pv_energy_daily_wh{source="combined"}` und laesst echte EVCC-PV-Rollups unangetastet.




