# Migration Troubleshooting

Englische Version: [migration-troubleshooting.md](../en/migration-troubleshooting.md).

Nutze dieses Dokument nur, wenn der normale Pfad in [influx-to-vm-migration.md](./influx-to-vm-migration.md) ein Problem meldet.

## Erste Regel: Rohdaten vor Rollups pruefen

Die meisten Probleme in Langzeit-Dashboards entstehen an einer von zwei Stellen:

- Rohdaten wurden nicht vollstaendig importiert.
- Rollups wurden aus bereits defekten Rohdaten gebaut.

Pruefe in dieser Reihenfolge:

1. VictoriaMetrics Health
2. Rohmetriken vorhanden
3. Influx-zu-VM-Abdeckung
4. `host`-Label-Hygiene
5. Rollup-Ausgabe
6. Grafana-Datasource und Dashboard-Variablen

## Rohmetriken vorhanden?

Beispiel fuer eine Rohserienpruefung:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=2026-03-28T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T00:00:00Z'
```

Wenn fuer einen Zeitraum mit InfluxDB-Daten keine Serie zurueckkommt, pruefe `vmctl influx`, Datenbankname, Zeitraum und Zugangsdaten erneut.

## Coverage-Check meldet Probleme

Fuehre den Coverage-Check direkt nach `vmctl` und vor jeder Bereinigung aus:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --only-problems
```

Interpretation:

- `Repo-relevant problems: 0` bedeutet, dass das aktive Dashboard-Schema nicht blockiert ist.
- `Additional`-Funde koennen zusaetzliche EVCC-Metadaten oder Nicht-Dashboard-Messungen sein.
- `Critical energy problems` muessen geloest werden, bevor Rollups vertrauenswuerdig sind.

Eine einzelne Measurement-Familie untersuchen:

```bash
python3 compare_import_coverage.py \
  --influx-url http://<influx-host>:8086 \
  --influx-db evcc \
  --vm-base-url http://localhost:8428 \
  --start 2026-03-21T00:00:00Z \
  --end 2026-04-03T23:59:59Z \
  --measurement-regex '^batterySoc$' \
  --only-problems
```

## PV-Importdrift oder fehlendes `pvPower`

Wenn der kritische PV-Paritaetscheck fehlschlaegt, repariere rohe `pvPower`-Daten vor dem Neuaufbau der Rollups.

1. Betroffene rohe `pvPower_value`-Familie in VictoriaMetrics loeschen.
2. Nur `pvPower` mit `vmctl influx --influx-filter-series` erneut importieren.
3. Coverage fuer `pvPower` erneut pruefen.
4. `evcc_*` Rollups neu bauen.

Beispiel:

```bash
curl -fsS -X POST 'http://localhost:8428/api/v1/admin/tsdb/delete_series' \
  --data-urlencode 'match[]=pvPower_value'

yes | vmctl influx \
  --influx-addr='http://<influx-host>:8086' \
  --influx-user='<user>' \
  --influx-password='<password>' \
  --influx-database='evcc' \
  --influx-filter-series "on evcc from pvPower" \
  --influx-filter-time-start='2025-01-01T00:00:00Z' \
  --influx-filter-time-end='2026-03-31T23:59:59Z' \
  --influx-skip-database-label \
  --vm-addr='http://localhost:8428'
```

## `host`-Bereinigung meldet Konflikte

Pruefen, ob `host` existiert:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]={host!=""}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-30T23:59:59Z'
```

Dry-Run:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Folge exakt der Empfehlung, die das Tool ausgibt.

Sauberer Fall:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --reset-cache \
  --write
```

Wenn das Tool meldet, dass ein Ziel-Delete nicht verwaltete hostlose Geschwisterserien loeschen wuerde, stoppe. Re-importiere oder validiere zuerst die betroffene Measurement-Familie; sonst koennen Detail-Dashboards PV-String- oder Batterie-Detailserien verlieren, obwohl aggregierte Panels weiter Werte zeigen.

Konfliktbewahrender Fall, wenn hostlose Zielwerte autoritativ bleiben sollen:

```bash
python3 vm-rewrite-drop-label.py \
  --base-url http://localhost:8428 \
  --matcher '{host!=""}' \
  --drop-label host \
  --backup-jsonl backups/evcc-host-series.jsonl \
  --rewritten-jsonl backups/evcc-host-series-without-host.jsonl \
  --merge-target \
  --keep-target-values-on-conflict \
  --reset-cache \
  --write
```

Diese Labels niemals blind entfernen:

- `loadpoint`
- `vehicle`
- `id`
- `title`

Sie tragen EVCC-Fachbedeutung.

## Historische Fachlabel-Umbenennung

Nutze `vm-rewrite-label-value.py` nur fuer bewusste Fachlabel-Umbenennungen, zum Beispiel nachdem ein PV-Titel in EVCC geaendert wurde. Aendere zuerst die Live-EVCC-Konfiguration, sonst schreiben neue Samples weiter das alte Label.

Dry-Run:

```bash
python3 vm-rewrite-label-value.py \
  --base-url http://localhost:8428 \
  --matcher '{title="Balkon PV"}' \
  --label title \
  --from "Balkon PV" \
  --to "Balkon Sued" \
  --backup-jsonl backups/rename-balkon-pv.jsonl \
  --rewritten-jsonl backups/rename-balkon-sued.jsonl
```

Fuer PV-Geraete ist `title` normalerweise der stabilere Fachschluessel. EVCC kann PV-`id`-Werte neu nummerieren, wenn Geraete hinzugefuegt, entfernt oder umsortiert werden.

## Fachlabels, Titles und Blocklists

Wenn Grafana zwar Rohdaten findet, aber einzelne Detailpanels leer, doppelt oder falsch gruppiert wirken, pruefe zuerst die EVCC-Fachlabels. Typische Symptome sind:

- PV-, Batterie-, Consumer-, AUX- oder EXT-Details zeigen nur `Gesamt` oder unerwartete Namen.
- Hausverbrauch oder Verbraucheranteile wirken zu hoch, weil Consumer-, AUX- oder EXT-Meter nicht passend gefiltert werden.
- Ladepunkte oder Fahrzeuge fehlen, weil `loadpoint` oder `vehicle` nicht als Label vorhanden ist.
- Eine Waermepumpe erscheint als normaler Ladepunkt oder Fahrzeugverbrauch statt in der erwarteten Gruppe.

Pruefe die Serien direkt in VictoriaMetrics:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=pvPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=consumersPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=extPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=auxPower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=chargePower_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'
```

Wichtig:

- `title` ist fuer PV-, Batterie-, Consumer-, AUX- und EXT-Geraete der wichtigste Anzeigename.
- `loadpoint` trennt Ladepunkte.
- `vehicle` trennt Fahrzeuge.
- Fehlende Consumer-, AUX- oder EXT-Serien sind kein Fehler, wenn EVCC keine solchen Meter schreibt.
- Aendere zuerst EVCC, wenn ein Name falsch ist. Danach kommen neue Messwerte korrekt an; historische Werte koennen bei Bedarf mit `vm-rewrite-label-value.py` nachgezogen werden.

EVCC schreibt ab Version 0.309.2 echte Verbraucher als `consumersPower`. Historische Geraete, die vorher als zusaetzliche Zaehler unter `extPower` liefen, werden dadurch nicht automatisch umbenannt. Setze fuer einen Rollenwechsel mit unveraendertem `title` im Rollup `consumer_legacy_ext_regex` und berechne den kompletten betroffenen Zeitraum mit `--replace-range --write` neu. Setze beim Dashboard-Deployment zusaetzlich `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` auf dieselbe Regex. Consumer gewinnt bei Ueberlappung pro Messintervall; der zugeordnete Alt-Titel wird weder als EXT-Rollup noch in den EXT-Rohdaten-Panels von `Today - Details` angezeigt. Alle nicht zugeordneten `extPower`-Titel bleiben echte zusaetzliche Zaehler.

Dashboard-Blocklists filtern nur die Anzeige und loeschen keine Daten. Sie gehoeren in `vm-dashboard-install.env` und werden beim Dashboard-Deployment uebernommen:

```env
DASHBOARD_FILTER_CONSUMER_BLOCKLIST=".*Car.*|.*Haupt.*"
DASHBOARD_CONSUMER_LEGACY_EXT_REGEX="^(Spuelmaschine|Waschmaschine)$"
DASHBOARD_FILTER_EXT_BLOCKLIST=^none$
DASHBOARD_FILTER_AUX_BLOCKLIST=^none$
DASHBOARD_FILTER_LOADPOINT_BLOCKLIST=^none$
DASHBOARD_FILTER_VEHICLE_BLOCKLIST=^none$
DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX="(?i).*(daikin-wp|wp|warmepumpe|waermepumpe|heat pump).*"
```

`^none$` ist der sichere Wert fuer "nichts filtern", weil normale EVCC-Namen dadurch nicht matchen. Fuer `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX` ist dagegen `^$` der deaktivierte Standard. Wenn du Regexes mit `|`, Leerzeichen oder Sonderzeichen nutzt, setze sie in Anfuehrungszeichen. Nach einer Blocklist-Aenderung reicht ein erneutes Dashboard-Deployment; Daten muessen dafuer nicht migriert werden. Nach einer Rollenwechsel-Zuordnung sind sowohl das erneute Deployment als auch der vollstaendige Rollup des betroffenen Zeitraums erforderlich.

### Summen- und Elternzaehler aus der Hausaufteilung entfernen

Die Consumer- und AUX-Blocklists gelten fuer die sichtbaren Verbrauchsreihen und fuer `Sonstiges`. EXT ist fachlich getrennt: `extBlocklist` filtert nur den Tab `Zusaetzliche Zaehler`, und EXT-Werte werden weder vom Hausverbrauch abgezogen noch als Endverbraucher summiert. Soll ein echter EXT-Summen- oder Kontrollzaehler dort sichtbar bleiben, muss er deshalb aus `extBlocklist` entfernt werden. Keine Blocklist loescht Daten aus VictoriaMetrics.

Konkreter Anwendungsfall: Ein Summenzaehler und seine Unterzaehler duerfen nicht gleichzeitig in die Hausaufteilung eingehen. Typische ueberlappende Hierarchien sind:

- **Verteilerhierarchie:** `Haupt-Verteiler` > `EG-Verteiler` > `Buero` und `Kino`.
- **USV-Hierarchie:** `USV` > `Rack Kuehler` und `Rack Luefter`.
- **Waschraum-Hierarchie:** `Waschraum` > `Waschmaschine` und `Trockner`.

Waehle pro Hierarchie genau eine nicht ueberlappende Ebene. Wenn beispielsweise die Summenzaehler unter EXT geschrieben werden und nur die Unterzaehler sichtbar bleiben sollen, kann die Konfiguration so aussehen:

```env
DASHBOARD_FILTER_EXT_BLOCKLIST=".*Car.*|.*Haupt.*|^EG-Verteiler$|^USV$|^Waschraum$"
```

Passe die Regex immer an die tatsaechlichen EVCC-`title`-Werte und die Rollen Consumer, EXT oder AUX an. Ein gefilterter Consumer- oder AUX-Zaehler verschwindet aus Legende und Hausaufteilung. Ein gefilterter EXT-Zaehler verschwindet nur aus der getrennten Zusatzzaehleransicht. Die historische Zusammenfuehrung eines identischen EXT-/Consumer-`title` erfolgt im Rollup ueber `consumer_legacy_ext_regex` und in den Rohdaten-Panels von `Today - Details` ueber die identische Dashboard-Variable `DASHBOARD_CONSUMER_LEGACY_EXT_REGEX`.

`Sonstiges` bleibt bewusst die Differenz zwischen `homePower` und allen einbezogenen Detailzaehlern. Darin koennen deshalb reale Umwandlungs- und Verteilverluste sowie nicht separat gemessene Verbraucher enthalten sein, zum Beispiel MPII-Verluste oder ein Verbraucher am Wallbox-Zuleitungszweig. Uebersteigen die nach den Blocklists verbleibenden Detailzaehler den Hausverbrauch, zeigt das Dashboard die rote Diagnose `Zaehlerueberlappung`; dann sind Hierarchie, Vorzeichen oder Messpunktzuordnung zu pruefen.

## Forecast-Panel ist leer

Forecast-Panels basieren ausschliesslich auf der EVCC-Rohmetrik `tariffSolar_value`. Das Dashboard fragt Forecast.Solar, Solcast, Open-Meteo oder andere Provider nicht selbst ab.

Datenfluss:

```text
EVCC-Solar-Forecast -> tariffSolar_value -> Telegraf/Influx-Line-Protocol -> VictoriaMetrics -> Grafana
```

Pruefe zuerst, ob die Metrik in VictoriaMetrics existiert:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=tariffSolar_value' \
  --data-urlencode 'start=now-24h' \
  --data-urlencode 'end=now'

curl -fsG 'http://localhost:8428/api/v1/query' \
  --data-urlencode 'query=last_over_time(tariffSolar_value[24h])'
```

Interpretation:

- Ergebnis vorhanden: Grafana-Datasource, Zeitbereich und Panel pruefen.
- Kein Ergebnis: EVCC schreibt aktuell keinen Solar-Forecast. Konfiguriere den Forecast in EVCC oder akzeptiere, dass die Forecast-Panels leer bleiben.
- Alte Historie ohne Forecast ist kein Importfehler, wenn EVCC damals keinen `tariffSolar_value` geschrieben hat.
- Im Today-Details-PV-Tab zeigt das Panel `Solar-Forecast Status` sichtbar an, ob in den letzten 24 Stunden EVCC-Forecast-Samples angekommen sind. Die Forecast-Linie in Uebersichtspanels darf dagegen still fehlen.
## Leere Grafana-Dashboards

`Today` leer bedeutet meist Rohdaten- oder Datasource-Probleme:

- Grafana-Datasource zeigt auf den falschen Host.
- Datasource-UID passt nicht zu `vm-evcc` oder zum Deploy-Override.
- EVCC schreibt keine aktuellen Rohdaten nach VictoriaMetrics.

`Month`, `Year` oder `All-time` leer bedeutet meist fehlende Rollups:

```bash
curl -fsG 'http://localhost:8428/api/v1/series' \
  --data-urlencode 'match[]=evcc_pv_energy_daily_wh' \
  --data-urlencode 'start=2026-01-01T00:00:00Z' \
  --data-urlencode 'end=2026-03-31T23:59:59Z'
```

Wenn keine `evcc_*`-Serien existieren, fuehre Rollup-Backfill und Scheduler-Setup aus [influx-to-vm-migration.md](./influx-to-vm-migration.md) erneut aus.
