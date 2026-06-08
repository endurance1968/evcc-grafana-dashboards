# Investitionskosten fuer effektiven Strompreis

Diese Datei beschreibt, wie Investitionskosten fuer PV-Anlagen, Speicher und gemeinsame Systemkomponenten gepflegt werden koennen. Ziel ist eine spaetere Berechnung des effektiven Strompreises aus realen EVCC/VictoriaMetrics-Daten und lokalen Investitionsdaten.

## Dateiablage

Die oeffentlichen Vorlagen liegen hier:

- `data/examples/investments.example.xlsx` fuer manuelle Pflege in Excel, LibreOffice oder OnlyOffice
- `data/examples/investments.example.csv` als skriptfreundliche Textvariante mit denselben Spalten

Echte Werte sollten lokal abgelegt werden und nicht ins Git-Repository gelangen:

- bevorzugt: `data/private/investments.xlsx`
- alternativ: `data/private/investments.csv`

`data/private/` ist fuer private Installationsdaten vorgesehen und wird durch `.gitignore` ausgeschlossen.

## Grundidee

VictoriaMetrics liefert die laufenden Messwerte und Rollups, zum Beispiel:

- PV-Erzeugung aus `pvPower_value`
- Netzbezugskosten aus `evcc_grid_import_cost_daily_eur`
- Einspeisegutschrift aus `evcc_grid_export_credit_daily_eur`
- Verbrauch aus `evcc_home_energy_daily_wh` und `evcc_loadpoint_energy_daily_wh`
- Speicherenergie aus `evcc_battery_charge_daily_wh` und `evcc_battery_discharge_daily_wh`

Die Excel-/CSV-Datei ergaenzt dazu die Stammdaten, die EVCC nicht kennen kann: Kaufdatum, Kaufpreis, Abschreibungsdauer, optionale laufende Kosten und bei gemeinsamen PV-Komponenten die Verteilung auf mehrere EVCC-PV-Titel.

## Spalten

| Spalte | Bedeutung |
| --- | --- |
| `asset_id` | Stabiler technischer Name der Investition. Jede eigenstaendige Investition braucht eine ID. Bei `pv_shared` wird dieselbe ID bewusst mehrfach verwendet, damit der Helper die Verteilung pruefen kann. |
| `asset_type` | Art des Assets: `pv`, `pv_shared`, `battery` oder `system`. |
| `evcc_title` | Exakter EVCC-/VictoriaMetrics-Titel passend zu `pvPower_value{title="..."}`. Fuer PV und `pv_shared` ist dieser Wert Pflicht, weil darueber Kosten und Energie gemappt werden. |
| `allocation_percent` | Anteil als Zahl von `0` bis `1`, nur fuer `pv_shared` Pflicht. `1` bedeutet 100 %, `0.5` bedeutet 50 %. Brueche wie `1/3` sind erlaubt. Alle eingeschlossenen Zeilen mit gleicher `asset_id` sollten zusammen `1.0` ergeben; der Helper gibt sonst eine Warnung aus. |
| `commissioning_date` | Inbetriebnahmedatum dieser Investitionszeile im Format `YYYY-MM-DD`. Ab diesem Tag beginnt die Abschreibung fuer genau diese Zeile. |
| `purchase_price_eur` | Anschaffungskosten in Euro. Rabatte oder Foerderungen sollten vorher abgezogen werden, wenn sie die Investition mindern sollen. |
| `lifetime_years` | Abschreibungsdauer in Jahren. Fuer PV und Speicher ist als einfache Annahme `20` sinnvoll. Nach Ablauf dieser Dauer erzeugt diese Investitionszeile keine weiteren Jahreskosten. |
| `yearly_opex_eur` | Optionale laufende Kosten pro Jahr, zum Beispiel Wartung, Versicherung oder Portalgebuehren. `0` ist erlaubt. |
| `watt_peak` | Installierte PV-Leistung in Wp. Fuer `asset_type=pv` Pflicht, fuer `pv_shared` nicht noetig. |
| `capacity_wh` | Speicherkapazitaet in Wh. Nur fuer Speicher relevant. |
| `include_in_effective_price` | `yes` oder `no`. Steuert, ob die Zeile in die Berechnung eingeht. |
| `notes` | Freitext fuer lokale Hinweise. |

## Asset-Typen

- `pv`: Eine einzeln messbare PV-Quelle oder eine spaetere Zusatzinvestition fuer diese Quelle. `evcc_title` muss exakt zum EVCC-Titel passen. Mehrere `pv`-Zeilen mit gleichem `evcc_title` werden kostenseitig addiert; die PV-Energie wird nur einmal je Titel gezaehlt.
- `pv_shared`: Gemeinsame PV-Komponente, zum Beispiel ein Wechselrichter, MPPT oder Verteiler fuer mehrere PV-Quellen. Dazu wird die gleiche `asset_id` mehrfach eingetragen, je Ziel-PV ein eigener `evcc_title`, und `allocation_percent` verteilt die Kosten. Beispiel: drei Zeilen mit `1/3`, `1/3`, `1/3`.
- `battery`: Speicher. In der Vorlage enthalten, fuer spaetere Systempreisberechnung vorgesehen, aber im aktuellen PV-only-Helper noch nicht Teil der PV-Gestehungskosten.
- `system`: Allgemeine Anlagenkosten, die nicht eindeutig PV oder Speicher sind. Ebenfalls fuer eine spaetere Systempreisberechnung vorgesehen.

## Aktueller PV-only-Helper

Die aktuelle Umsetzung ist `scripts/helper/import-investment-costs.py`. Sie berechnet bewusst nur PV-Investitionskosten und betrachtet Akku- und Netzeffekte noch nicht.

Der Helper:

1. liest `data/private/investments.xlsx` oder `.csv`,
2. nutzt eingeschlossene Zeilen mit `asset_type=pv` oder `asset_type=pv_shared`,
3. prueft bei `pv_shared`, ob die Verteilung je `asset_id` auf 100 % kommt,
4. gruppiert mehrere Investment-Zeilen mit gleichem `evcc_title`,
5. liest die gemessene PV-Energie je `evcc_title` aus EVCC-`pvPower_value`, aus einer vorhandenen Tagesmetrik wie `evcc_pv_energy_by_title_daily_wh` oder aus einer Kombination beider Quellen,
6. schreibt daraus generierte Metriken nach VictoriaMetrics.

Generierte Metriken:

- `evcc_pv_energy_by_title_daily_wh`
- `evcc_pv_investment_cost_daily_eur`
- `evcc_pv_lcoe_daily_ct_per_kwh`
- `evcc_pv_lcoe_rolling_7d_ct_per_kwh`
- `evcc_pv_lcoe_yearly_ct_per_kwh`
- `evcc_pv_effective_lcoe_daily_ct_per_kwh`
- `evcc_pv_effective_lcoe_monthly_ct_per_kwh`
- `evcc_pv_effective_lcoe_yearly_ct_per_kwh`
- `evcc_pv_energy_by_title_monthly_wh`
- `evcc_pv_investment_cost_monthly_eur`
- `evcc_pv_lcoe_monthly_ct_per_kwh`

Das `Jahr`-Dashboard zeigt diese Werte im PV-Tab mit zwei Panels: links `PV-Gestehungskosten` mit Jahreswerten pro PV-Anlage plus gewichteter Gesamtwert und rechts `PV-Gestehungskosten pro Woche (ct/kWh)` als rollierende 7-Tage-Zeitreihen je PV-Anlage im ausgewaehlten Jahr. Die Dashboards lesen dafuer bewusst kurze Helper-Metriken statt langer MetricQL-Ausdruecke.

Jahreswerte mit weniger als 1 kWh gemappter PV-Energie und Wochenfenster mit weniger als 1 kWh gemappter PV-Energie werden unterdrueckt, damit keine irrefuehrenden Divisionen durch nahezu null entstehen.

Wichtig: Die Aussagekraft der Gestehungskosten haengt von vollstaendiger gemappter PV-Energie je `evcc_title` ab. Wenn ein Jahr nur wenige Tage mit `title`-Aufloesung enthaelt, die Investitionskosten aber fuer das ganze Jahr laufen, werden ct/kWh-Werte kuenstlich hoch. Solche Zeitraeume sollten vor der Bewertung ueber die Import-Zusammenfassung oder VictoriaMetrics geprueft werden.

## Gestehungskosten berechnen

Fuer normale EVCC-Installationen reicht der Standardpfad ueber EVCC-`pvPower_value`. Der Helper liest die PV-Energie je `evcc_title` direkt aus den vorhandenen EVCC-Rohdaten und schreibt daraus die Kostenmetriken fuer die Dashboards.

Trockenlauf:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --energy-source pv-power
```

Schreiben oder Ersetzen der generierten Metriken nur auf der Ziel-VictoriaMetrics-Instanz:

```bash
python3 scripts/helper/import-investment-costs.py \
  --vm-base-url http://localhost:8428 \
  --investment-file data/private/investments.xlsx \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --energy-source pv-power \
  --write --replace
```

`--replace` ersetzt nur die vom Helper erzeugten Investment-/Kostenmetriken. Die EVCC-Rohdaten bleiben unveraendert.

## Erweiterte Energiequellen

Die Optionen `--energy-source daily-metric` und `--energy-source combined` sind Spezialfaelle. Sie sind nur relevant, wenn bereits eine per-title Tagesmetrik wie `evcc_pv_energy_by_title_daily_wh` in VictoriaMetrics liegt und bewusst statt oder zusaetzlich zu EVCC-`pvPower_value` verwendet werden soll. Fuer den normalen EVCC-Pfad werden diese Varianten nicht benoetigt.

## Geplante Systemkennzahlen

Eine spaetere robuste Berechnung fuer den effektiven Systemstrompreis waere:

```text
effektiver Strompreis =
(Netzbezugskosten - Einspeisegutschrift + PV-Abschreibung + Speicher-Abschreibung + laufende Kosten)
/
(Hausverbrauch + Ladepunktverbrauch)
```

Fuer eine separate Speicherbetrachtung kann zusaetzlich gerechnet werden:

```text
Speicherkosten pro entladener kWh = Speicher-Abschreibung / Speicher-Entladung
```

Die Systemkennzahl sollte aber die Speicherabschreibung im Gesamtsystem beruecksichtigen, weil der Speicher Teil der realen Stromkosten ist.

## Hinweise fuer EVCC-Nutzer

- PV-Titel muessen exakt zu den EVCC-Titeln passen. Pruefbar ist das in VictoriaMetrics ueber `pvPower_value{title="..."}`.
- Wenn sich EVCC-IDs historisch geaendert haben, ist `title` stabiler als `id`.
- Gemeinsame PV-Kosten koennen ueber `pv_shared` auf mehrere EVCC-Titel verteilt werden. Der Helper warnt, wenn die Summe je gemeinsamem Asset nicht 100 % ergibt.
- Die Datei enthaelt finanzielle Stammdaten und sollte nicht in ein oeffentliches Repository committed werden.




