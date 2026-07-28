# Migrationsvalidierungsnotizen

Englische Version: [migration-validation-notes.md](../en/migration-validation-notes.md).

Dieses Dokument haelt Release- und Kalibrierungshintergrund aus dem Haupt-Migrations-Runbook heraus.

## Warum diese Notizen existieren

Die Haupt-Migrationsanleitung soll kurz genug fuer Erstnutzer bleiben. Die Details hier sind nuetzlich, wenn Rollup-Qualitaet validiert, Energiedrift untersucht oder ein Release vorbereitet wird.

## 2026-04-06 Baseline vor PV/Home-Mean-Umstellung

Vor der Umstellung des Python-Rollup-Pfads von `max` auf `mean` fuer taegliche PV- und Home-Energie wurde beobachtet:

- `evcc_pv_energy_daily_wh`: der VM-Rollup passte zu einem rohen `max`-Bucket-Pfad, waehrend Influx und nutzbare VRM-Vergleichsmonate naeher am rohen `mean`-Pfad lagen.
- `evcc_home_energy_daily_wh`: der VM-Rollup passte zu einem rohen `max`-Bucket-Pfad, waehrend Influx naeher am rohen `mean`-Pfad lag.
- `evcc_grid_import_daily_wh`: der VM-Rollup passte zum `gridEnergy`-Counter-Spread-Pfad und lag meist naeher an VRM als das Legacy-Influx-Aggregat; deshalb blieb er bewusst unveraendert.

Nutze das als Vorher-Zustand, wenn Full Backfills rund um die PV/Home-Reducer-Aenderung validiert werden.

## 2026-04-06 Verifizierter Vergleich nach PV/Home-Mean-Umstellung

Der Monatsvergleich wurde validiert gegen:

- Influx-Rohmonatssemantik fuer `PV`, `Home` und `Grid import`
- die Influx-Datasource `EVCC_AGGREGATIONS` (`evcc_agg`) fuer Dashboard-Level `Home`, `Loadpoints` und `Battery netto`
- VictoriaMetrics-Rollups im Namespace `evcc_*`
- lokal gecachte Victron-VRM-Tagessummen fuer `PV` und `Grid import`

Influx-Monatsdashboard-Semantik fuer `Gesamt: Energieverteilung`:

- `Home` kommt aus `homeDailyEnergy`
- `Loadpoints` kommen aus `loadpointDailyEnergy`
- `Battery netto` ist `chargeDailyEnergy - dischargeDailyEnergy`

Vergleichsmonate mit vollstaendiger VRM-Abdeckung:

- `2025-08`
- `2025-09`
- `2026-02`
- `2026-03`

| Monat | Metrik | Influx | VM rollup | VM aggregation | VRM |
| --- | --- | ---: | ---: | ---: | ---: |
| 2025-08 | PV | 1825.700 | 1826.580 | 1793.831 | 1829.700 |
| 2025-08 | Home | 1990.773 | 1994.219 | 1986.997 | - |
| 2025-08 | Grid import | 655.300 | 633.260 | 657.920 | 634.000 |
| 2025-08 | Loadpoints | 366.213 | 366.768 | 715.256 | - |
| 2025-08 | Battery netto | 57.051 | 55.911 | 125.630 | - |
| 2025-09 | PV | 996.500 | 997.219 | 1021.473 | 996.200 |
| 2025-09 | Home | 1244.685 | 1245.235 | 1239.921 | - |
| 2025-09 | Grid import | 624.000 | 612.290 | 591.455 | 611.900 |
| 2025-09 | Loadpoints | 367.166 | 367.416 | 750.311 | - |
| 2025-09 | Battery netto | -21.578 | -19.482 | -41.672 | - |
| 2026-02 | PV | 511.800 | 511.763 | 540.248 | 512.200 |
| 2026-02 | Home | 1128.338 | 1129.096 | 1138.051 | - |
| 2026-02 | Grid import | 1176.500 | 1168.690 | 1149.994 | 1165.600 |
| 2026-02 | Loadpoints | 515.632 | 516.647 | 934.805 | - |
| 2026-02 | Battery netto | 28.346 | 29.868 | 157.272 | - |
| 2026-03 | PV | 1252.900 | 1252.948 | 1185.964 | 1249.900 |
| 2026-03 | Home | 1262.666 | 1265.252 | 1218.546 | - |
| 2026-03 | Grid import | 531.500 | 512.810 | 469.013 | 510.800 |
| 2026-03 | Loadpoints | 405.301 | 406.338 | 796.323 | - |
| 2026-03 | Battery netto | 63.557 | 60.979 | 59.970 | - |

Zusammenfassung:

- `VM rollup` liegt fuer `PV` auf Influx-/VRM-Niveau.
- `VM rollup` liegt fuer `Home`, `Loadpoints` und `Battery netto` auf Influx-Dashboard-Niveau.
- `VM rollup` liegt fuer `Grid import` in den geprueften Monaten naeher an VRM als Influx.
- `VM aggregation` bleibt sichtbar weniger verlaesslich, besonders fuer `PV`, `Loadpoints` und mehrere `Grid import`-Monate.

## Privater Validierungsbefehl

Auf privaten Runnern mit aktualisierten Tibber-/Influx-/VRM-Caches und optionalem Live-VM-Zugriff:

```bash
npm run test:rollup-path -- --strict-energy --vm-base-url http://127.0.0.1:8428
```

Ohne private Caches behandelt die public/default-Validierung fehlende externe Vergleichsdateien bewusst als nicht blockierende Skips.

## 2026-07-26 Read-only Live-Quellenpruefung fuer Consumer

Der Consumer-Releasekandidat wurde zusaetzlich zu den deterministischen Fixtures gegen die produktive, strikt read-only verwendete VictoriaMetrics-Quelle geprueft. Grafana lief dabei ausschliesslich in einer Wegwerf-Testinstanz.

Ergebnis:

- `check_data.py --phase full` meldete insgesamt `OK`, keine `host`- oder `db`-Labels und vorhandene Kern-Rohdaten sowie Rollups.
- Alle 385 MetricsQL-Ziele der sechs Quelldashboards wurden gegen die Live-VM erfolgreich ausgefuehrt.
- Alle sechs Dashboards mit 58 kritischen Panels renderten gegen die Live-VM ohne Panel-Fehler.
- Die Live-Quelle enthielt noch keine `consumersPower_value`- oder `evcc_consumer_*`-Reihen. Die neue Consumer-Funktion ist deshalb live noch nicht funktional verifiziert, sondern nur deterministisch per Fixture getestet.
- Die vorhandenen realen Verbraucher lagen weiterhin als 16 EXT-Reihen vor. Die produktive EXT-Blocklist filterte Carport- und Hauptverteiler, aber verbleibende Eltern-/Kind-Kombinationen wie EG-Verteiler, USV und Unterzaehler konnten die Summe zeitweise bis an oder ueber den Hausverbrauch treiben. Das Dashboard begrenzte `Sonstiges` korrekt auf null, aber die zugrunde liegende Zaehlertopologie bleibt ohne explizite Hierarchie fachlich mehrdeutig.

Releasefolgerung:

- Fixture-E2E bleibt fuer reproduzierbare Sollwerte und Fehlerszenarien Pflicht.
- Ein read-only Live-Render mit echten Deploy-Overrides ist ein zusaetzliches, verbindliches Release-Gate.
- Consumer darf erst als live-validiert gelten, wenn EVCC echte Consumer-Metriken liefert.
- Vor einer Freigabe muss die EXT-zu-Consumer-Migration beziehungsweise Blocklist so festgelegt sein, dass Eltern- und Kindzaehler nicht doppelt summiert werden.

## 2026-07-27 Live-Kopie Und Vollstaendiger Consumer-Rollup

Die Validierung vom Vortag wurde mit den inzwischen vorhandenen echten Consumer-Metriken wiederholt. Produktions-Grafana und Produktions-VictoriaMetrics blieben strikt read-only; Import, Bereinigung und Rollup liefen ausschliesslich in einer neu erstellten Wegwerf-VM.

Ergebnis:

- Die Live-Quelle lieferte sechs Consumer-Titel: `KWL`, `Rack Kühler`, `Rack Lüfter`, `Spüle`, `Waschmaschine` und `Waschmaschine II`.
- Der Rollup verarbeitete 572 Tage vom 2025-01-01 bis 2026-07-26 und schrieb 41 Metriken, 288 Serien und 7.840 Samples.
- Die 2025-Rollups enthielten 356 PV- und Haus-Tageswerte sowie 365 Tageswerte fuer Netzbezug und Einspeisung. Die Summen betrugen rund 14,42 MWh PV, 22,43 MWh Hausverbrauch, 14,06 MWh Netzbezug und 0,83 MWh Einspeisung.
- Die sechs als Consumer fortgefuehrten Titel waren anschliessend vollstaendig aus `evcc_ext_energy*_daily_wh` entfernt. Zehn echte Diagnose-/Verteilerzaehler blieben als EXT erhalten.
- Die produktiven Grafana-Einstellungen wurden in die Wegwerf-Instanz uebernommen. `Today` blieb der Zeitraum der Today-Dashboards; die Blocklist `.*Car.*|.*Haupt.*` filterte die bekannten Summenzaehler.
- Die grafische Endnutzerpruefung bestaetigte getrennte Consumer- und Zusätzliche-Zähler-Ansichten in Today Details, Month, Year und All-time. Year 2025 zeigte alle zwölf Monate, All-time zeigte 2025 und 2026, und die Jahresmatrizen verwendeten eine echte Jahresachse.
- Die Today-Finanzansicht zeigte Bezugskosten negativ, Einspeisegutschrift positiv und die Bilanz als Summe beider Werte.

Sicherheitsbefund:

- `--replace-range` loescht vorhandene Rollups im Zielzeitraum vor der Neuberechnung. Das ist fuer einen Gesamtzeitraum nur sicher, wenn die komplette Rohdatenhistorie aller betroffenen Familien vorliegt.
- Ein additiver Voll-Backfill ueber bereits importierte Rollups ist ebenfalls unsicher: Unterschiedliche Tageszeitstempel erzeugen mehrere Samples pro lokalem Tag und verdoppeln Monatswerte. Die korrigierte Live-Kopie transformierte nur die sechs gemappten EXT-Rollup-Reihen, bevorzugte Consumer tagweise bei Ueberlappung und importierte ausschliesslich diese Consumer-Reihen.
- `check_data.py --phase full` prueft nun alle `evcc_*_daily_*`-Reihen auf hoechstens ein Sample je Labelsatz und lokalem Tag. Die korrigierte Kopie meldete 0 doppelte Tage; Juli stimmte fuer PV, Haus, Netzbezug und Einspeisung exakt mit der read-only Live-VM ueberein.
