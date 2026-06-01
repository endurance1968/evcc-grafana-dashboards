# Skript-Werkzeuge

Englische Version: [README_EN.md](./README_EN.md).

Das Verzeichnis `scripts` ist in folgende Bereiche aufgeteilt:

- Root: Installer-Einstiegspunkte
- `rollup/`: VictoriaMetrics-Rollup-Werkzeuge fuer den regulaeren Betrieb
- `localization/`: Uebersetzungsgenerierung und Audit-Helfer
- `helper/`: Migrations- und Hilfsskripte, die nicht zum normalen Endnutzerpfad gehoeren
- `test/`: Grafana-Import, Smoke-Checks und Screenshot-Werkzeuge

## Rollup-Werkzeuge

Aktuelle Rollup-Dateien:

- `rollup/evcc-vm-rollup.py`
- `rollup/evcc-vm-rollup.conf.example`
- `rollup/evcc-vm-rollup-prod.conf.example`
- `helper/check_data.py`
- `helper/compare_import_coverage.py`
- `helper/compare_labelsets.py`
- `helper/vm-rewrite-drop-label.py`

Das Werkzeug laesst die rohen EVCC-Metriken unveraendert:

- keine Schreibzugriffe, ausser `--write` wird explizit uebergeben
- keine Aenderungen an Rohmetriken durch die Rollup-Engine
- keine Dashboard-Umschaltung

## Hauptbefehle

Dimensionen erkennen:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example detect
```

Rollup-Plan anzeigen:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example plan
```

Repräsentative Rohdatenabfragen benchmarken:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example benchmark
```

Backfill-Dry-run:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup.conf.example backfill --start-day 2026-02-20 --end-day 2026-03-22 --progress
```

`evcc_*`-Rollups schreiben:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example backfill --start-day 2025-01-01 --end-day 2026-03-27 --progress --write
```

Vor Aenderungen am Rollup-Schreib-/Loeschpfad den disposable Rollup-End-to-End-Test ausfuehren:

```bash
python3 scripts/test/rollup-e2e.py --docker
```

Der Test importiert eine kleine Rohdaten-Fixture in eine isolierte VictoriaMetrics-Instanz, fuehrt `backfill --replace-range --write` zweimal aus und prueft, dass wiederholtes Ersetzen keine doppelten taeglichen Rollup-Samples hinterlaesst. Wenn Docker nicht verfuegbar ist, nur eine lokale disposable VM verwenden:

```bash
python3 scripts/test/rollup-e2e.py --base-url http://127.0.0.1:8428 --confirm-disposable
```

Monatlichen Rollup-Bereich vor erneutem Schreiben ersetzen:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example backfill --start-day 2026-04-01 --end-day 2026-04-10 --replace-range --progress --write
```

Monatlichen Rollup-Bereich loeschen, ohne ihn neu aufzubauen:

```bash
python3 scripts/rollup/evcc-vm-rollup.py --config scripts/rollup/evcc-vm-rollup-prod.conf.example delete --start-day 2026-04-01 --end-day 2026-04-30
```

## VM-Cleanup- und Validierungshelfer

Pruefen, ob rohe EVCC-Metriken und erwartete taegliche Rollups nach Import/Backfill existieren. In der Default-Phase `auto` prueft das Skript zuerst Rohdaten und nimmt Rollups automatisch dazu, sobald sie existieren. Es meldet auch, ob `host`-Cleanup empfohlen wird:

```bash
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428

# explizite Rohimport-Phase
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --phase raw

# historischer Import oder Benchmark-VM
python3 scripts/helper/check_data.py --base-url http://127.0.0.1:8428 --phase raw --end-time 2026-03-31T23:59:59Z
```

Influx-Quellabdeckung direkt nach `vmctl` gegen importierte VM-Rohmetriken vergleichen. Der Default prueft inzwischen den vollstaendigen Influx-Measurement-Satz, trennt das Ergebnis aber in `repo-relevant` und `additional`, damit die Schlussfolgerung klar zeigt, ob das aktive Dashboard-Schema blockiert ist oder nur zusaetzliche EVCC-Metadatenfamilien betroffen sind:

```bash
python3 scripts/helper/compare_import_coverage.py --influx-url http://127.0.0.1:8086 --influx-db evcc --vm-base-url http://127.0.0.1:8428 --start 2026-03-21T00:00:00Z --end 2026-04-03T23:59:59Z --only-problems

# optional: Check auf repo-relevante Measurements begrenzen
python3 scripts/helper/compare_import_coverage.py --influx-url http://127.0.0.1:8086 --influx-db evcc --vm-base-url http://127.0.0.1:8428 --start 2026-03-21T00:00:00Z --end 2026-04-03T23:59:59Z --only-problems --repo-relevant-only
```

Zusaetzliche Findings enthalten inzwischen einen kurzen `Hint`, damit sichtbar ist, ob es sich wahrscheinlich um String-/Boolean-Metadaten oder um eine echte zusaetzliche Importluecke handelt.

Nur wenn Coverage-Check und Datencheck gut aussehen, VM-only-Serien mit `host`-Tag umschreiben:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://127.0.0.1:8428 --matcher '{host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl
```

Der Dry-run gibt jetzt einen `Recommendation`-Abschnitt mit eindeutigem Status (`GO FOR IT`, `REVIEW` oder `STOP`) und den exakten Schreibflags aus, die als naechstes angehaengt werden sollen. Ein sauberer Lauf vermeidet Target-Loeschung und sieht so aus:

```text
GO FOR IT: Dry-run is clean. You can continue with the write step without deleting hostless target matchers.
Recommended write flags:
  --reset-cache \
  --write
```

In diesem sauberen Fall denselben Befehl mit diesen Flags erneut ausfuehren:

```bash
python3 scripts/helper/vm-rewrite-drop-label.py --base-url http://127.0.0.1:8428 --matcher '{host!=""}' --drop-label host --backup-jsonl backups/evcc-host-series.jsonl --rewritten-jsonl backups/evcc-host-series-without-host.jsonl --reset-cache --write
```

`--merge-target` nicht manuell hinzufuegen. Wenn `--merge-target` verwendet wird, prueft das Skript inzwischen, ob der VictoriaMetrics-Delete-Selector auch vorhandene hostlose Schwester-Serien loeschen wuerde, die durch diesen Rewrite nicht neu aufgebaut werden. Wenn das passiert, gibt es `STOP` zurueck und verweigert den Schreibzugriff.

Wenn die Empfehlung Konflikte nennt, folge stattdessen dem ausgegebenen konflikt-sicheren Flag-Set, zum Beispiel `--keep-target-values-on-conflict`. Nach jedem Cleanup-Schreibzugriff erneut `compare_import_coverage.py` und `check_data.py --phase raw` ausfuehren, bevor Rollups erzeugt werden.

Labelsets zwischen zwei Importzustaenden oder Benchmark-Exports vergleichen:

```bash
python3 scripts/helper/compare_labelsets.py --left-json /tmp/before-cleanup/target-stats.json --left-name before --right-json /tmp/after-cleanup/target-stats.json --right-name after

# nur eine Metrik
python3 scripts/helper/compare_labelsets.py --left-json /tmp/before-cleanup/target-stats.json --left-name before --right-json /tmp/after-cleanup/target-stats.json --right-name after --metric-regex '^pvPower_value$'
```

Gecachte externe Energievergleichs-Snapshots nach Rollup- oder Dashboard-Kosten-Aenderungen validieren:

```bash
npm run test:energy-validation
```

Das liest lokale Dateien aus `data/energy-comparison/tibber/` und `data/energy-comparison/vrm/`, schliesst die dokumentierten Anomaliemonate `2025-04` und `2025-10` aus und meldet monatliche Tibber-vs-VM-, Tibber-vs-Influx- und VRM-Cache-Zusammenfassungen. Mit `--vm-base-url http://127.0.0.1:8428` werden gecachte VRM-PV-/Grid-Import-Summen gegen Live-VM-Rollups verglichen.

Fuer einen strikten privaten Validierungsjob auf einem Runner mit aktualisierten Cache-Snapshots:

```bash
npm run test:energy-validation -- \
  --require-cache tibber-vm \
  --require-cache tibber-influx \
  --require-cache vrm
```

Fuege `-- --require-cache vrm-vm --vm-base-url http://127.0.0.1:8428` hinzu, wenn der Runner auch Zugriff auf eine VM-Instanz mit Rollups hat. Ohne `--require-cache` werden fehlende private Caches als `SKIP` gemeldet, damit der Befehl fuer public CI und frische Developer-Checkouts sicher bleibt.

Der Forgejo-Workflow haelt den public/default-Pfad cache-optional, kann aber ueber Runner-Umgebungsvariablen in strikte private Validierung geschaltet werden:

- `ENERGY_VALIDATION_STRICT=1` erzwingt Tibber-vs-VM-, Tibber-vs-Influx- und VRM-Cache-Snapshots.
- `ENERGY_VALIDATION_VM_BASE_URL=http://127.0.0.1:8428` aktiviert zusaetzlich den Live-VM-Rollup-Vergleich und erzwingt den VRM-vs-VM-Cache-Pfad.

Pruefen, dass generierte Dashboard-Uebersetzungen reproduzierbar aus `dashboards/original/` entstehen und die Lokalisierungsskripte auf sauberem Tree keine Diffs erzeugen:

```bash
npm run test:localization-idempotency
```

Das fuehrt `generate-localized-dashboards.mjs` und `apply-safe-display-translations.mjs` aus, vergleicht die generierten Uebersetzungsdateien vor/nach dem Lauf und prueft, dass die Quellsprache-Ausgabe unter `dashboards/translation/en/` eine JSON-aequivalente Kopie von `dashboards/original/en/` ist.

Jedes MetricsQL-Panel-Target aus den VM-Originalen gegen VictoriaMetrics ausfuehren, nachdem Grafana-Makros und Variablen ersetzt wurden:

```bash
npm run test:query-readback
```

Der Default-Befehl startet einen disposable leeren VictoriaMetrics-Container. Leere Daten sind hier absichtlich: Der Check prueft Query-Syntax, Dashboard-Makros und nicht unterstuetzte Influx-/Grafana-Reste. Mit `node scripts/test/dashboard-query-readback.mjs --base-url http://127.0.0.1:8428` laeuft der Check gegen eine bestehende VM.

Den vollstaendigen deterministischen Rollup-Pfad nach Rollup-, Query-, Dashboard- oder Validierungsaenderungen ausfuehren:

```bash
npm run test:rollup-path
```

Das orchestriert `test:ci`, `test:energy-validation`, `test:query-readback`, `test:render-e2e` und `test:rollup-e2e`. Nutze `-- --strict-energy` auf einem privaten Runner mit aktualisierten Tibber-/Influx-/VRM-Caches und ergaenze `-- --vm-base-url http://127.0.0.1:8428`, wenn eine Live-Rollup-VM gegen den VRM-Cache verglichen werden soll.

Cross-Platform-Guard:

```bash
npm run test:cross-platform
```

Dieser Check blockiert Windows-only-npm-Entrypoints und unsichere `child_process`-Shell-Nutzung in Node-Skripten. `npm test` ist absichtlich auf den portablen Node-Runner gemappt, nicht auf PowerShell.

Der Forgejo-CI-Workflow fuehrt dieselben deterministischen Checks als einzelne Schritte aus, damit Fehler leicht zuzuordnen bleiben:

```bash
npm run test:ci
npm run test:cross-platform
npm run test:energy-validation
npm run test:query-readback
npm run test:render-e2e
npm run test:rollup-e2e
```

Forgejo-Actions-Verkabelung von einer Entwicklermaschine pruefen:

```bash
npm run test:forgejo-actions
```

Die Default-Forgejo-Web/API-URL ist `http://<forgejo-host>:3000` und entspricht der lokalen Forgejo-Instanz dieses Repositories. Wenn sich die Instanz aendert, mit `FORGEJO_BASE_URL` oder `--base-url` ueberschreiben. Der Check prueft, dass Actions aktiviert sind und dass der neueste Workflow-Run von einem Runner angenommen wurde. `waiting` oder `cancelled` mit nie gestarteter Zeit bedeutet, dass kein passender Runner den Job angenommen hat. Der CI-Workflow startet auch mit einem `Runner Docker readiness`-Schritt, damit ein Runner ohne Docker-Zugriff scheitert, bevor Docker-basierte Query-Readback-, Render- oder Rollup-Tests laufen.

Fuer browserbasiertes Grafana-Rendering die Suite nach Dashboard-Import mit aktiviertem Render-Smoke ausfuehren:

```bash
node scripts/test/run-suite.mjs --env=.env.local --render-smoke=true
```

`render-smoke-check.mjs` scheitert bei Grafana-Datasource-/Query-HTTP-Fehlern, bekannten Panel-Fehlertexten, leeren kritischen Panels, haengenden Loading-Zustaenden und kritischen Panels, die ohne sichtbaren Inhalt, Tabelle oder numerischen Wert rendern. `--fail-no-data=false` nur nutzen, wenn Layout/Rendering absichtlich gegen unvollstaendige Testdaten geprueft wird.

Fuer einen vollstaendig disposable Render-Smoke-Lauf mit Fixture-Daten:

```bash
npm run test:render-e2e
```

Das startet temporaere Grafana- und VictoriaMetrics-Container, importiert minimale VM-Fixture-Daten, erstellt die VM-Datasource, importiert die originalen VM-Dashboards und fuehrt den gehaerteten Browser-Render-Smoke gegen kritische Panels aus. Der Forgejo-CI-Workflow fuehrt diesen Befehl nach Installation des Chromium-Browsers fuer Playwright aus.

Der Rollup-E2E-Test ist nicht nur ein Smoke-Test. Er importiert deterministische Rohdaten-Fixtures, fuehrt `evcc-vm-rollup.py --replace-range --write` zweimal aus und prueft erwartete taegliche Energie-, Tarif- und Kostenwerte, doppelfreie taegliche Timestamps und identische erforderliche Rollup-Ausgabe nach dem zweiten Replace-Lauf.

## Konfiguration

Die Beispielkonfiguration nutzt INI-Format, damit sie nur mit der Python-Standardbibliothek funktioniert.

Wichtige Einstellungen:

- `base_url`
- `host_label`
- `timezone`
- `metric_prefix`
- Benchmark-Start- und Endbereich

Das Repository geht von einer VictoriaMetrics-Instanz pro EVCC-Instanz aus. Wenn du mehrere EVCC-Instanzen betreibst, betreibe mehrere VictoriaMetrics-Instanzen, statt sie ueber ein gemeinsames `db`-Label zu multiplexen.

Den operatororientierten Workflow, Installationsschritte und Cron-Beispiele findest du in [influx-to-vm-migration.md](../docs/influx-to-vm-migration.md) und [migration-checklist.md](../docs/migration-checklist.md).

## Sicherheitsmodell

Rollups werden in den Namespace `evcc_*` geschrieben. Rohe EVCC-Metriken bleiben unveraendert.

## Aktueller Umfang

Im Katalog implementiert:

- taegliche PV-Energie
- taegliche Home-Energie
- taegliche Loadpoint-Energie
- taegliche Vehicle-Energie
- taegliche Vehicle-Distanz
- taegliche Ext-Energie
- taegliche Aux-Energie
- Batterie-Min-/Max-SOC pro Tag
- Grid-Import- und Export-Split
- Batterie-Lade- und Entlade-Split
- Importpreis- und Kosten-Rollups
- Exportverguetungs-Rollups

Taegliche Rollups tragen die Labels `local_year` und `local_month`, damit Monats-/Jahres-Dashboards nach lokalen Kalenderperioden filtern koennen, ohne grosse Timezone-Guard-Ausdruecke in jeder Query zu wiederholen.

Noch ausserhalb der aktuellen Baseline:

- optionale monatliche Rollup-Schicht

## Endnutzerinstallation

Fuer Endnutzer bevorzugen:

- `scripts/deploy.ps1`
- `scripts/deploy-python.sh`
- [vm-dashboard-install.md](../docs/vm-dashboard-install.md)
