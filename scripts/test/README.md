# Testskripte (Grafana)

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt den skriptbasierten Grafana-Validierungsworkflow zum Importieren von Dashboards, Ausfuehren von Smoke-Checks und Erstellen von Review-Screenshots.

## Skriptuebersicht

- `deploy-dashboards.mjs`: High-level-Deploy-Workflow fuer eine einzelne Sprache oder Variante
- `import-dashboards-raw.mjs`: Import ueber Grafanas Raw-Dashboard-Import-Endpunkt
- `smoke-check.mjs`: Validierung nach dem Import
- `dashboard-semantic-check.mjs`: statische semantische Checks fuer Dashboard-Zeitraeume, kritische Panels, Bar-Chart-Achsen und bekannte Grafana-Fehlerregressionen
- `render-smoke-check.mjs`: browserbasierte gerenderte Dashboard- und kritische Solo-Panel-Smoke-Checks
- `rollup-path-check.mjs`: vollstaendiger deterministischer Rollup-Pfad-Orchestrator (`npm run test:rollup-path`)
- `dedup-series-e2e.py`: optionaler disposable VictoriaMetrics-End-to-End-Test fuer exakte Serien-Deduplizierung
- `rename-label-e2e.py`: optionaler disposable VictoriaMetrics-End-to-End-Test fuer Label-Value-Rewrites
- `rollup-e2e.py`: optionaler disposable VictoriaMetrics-End-to-End-Test fuer Rollup-Lesen/-Schreiben/-Ersetzen
- `capture-screenshots.mjs`: browserbasierte Screenshot-Erfassung
- `run-suite.mjs`: Batch-Import-/Smoke-/Screenshot-Workflow ueber alle konfigurierten Sets
- `local-checks.mjs`: portabler deterministischer Check-Runner fuer `npm test` und CI
- `cross-platform-audit.mjs`: Guard gegen Windows-only-npm-Entrypoints und unsichere Child-Process-Shell-Nutzung
- `powershell-deployer-compat.mjs`: Windows-PowerShell-5.1-Deployer-Regressionstest fuer JSON-Parsing, Datasource-Ersetzung und Single-Item-Array-Erhalt
- `local-checks.ps1`: optionaler Windows-Kompatibilitaetswrapper; wird von portablen npm-Entrypoints nicht verwendet
- `cleanup-grafana.mjs`: vollstaendige Bereinigung von Dashboards und Library Panels im Grafana-Testordner
- `_lib.mjs`: gemeinsame Helfer

Lokalisierungs-Vorbereitungsskripte vor Testlaeufen:

- `../localization/generate-localized-dashboards.mjs`
- `../localization/apply-safe-display-translations.mjs`

## Cross-Platform-Test-Entrypoints

Diese Befehle auf Windows, Linux und Forgejo-Runnern verwenden:

```bash
npm test
npm run test:ci
npm run test:cross-platform
npm run test:powershell-compat
npm run test:dedup-e2e
npm run test:rename-e2e
npm run test:rollup-path
```

`npm test` und `npm run test:ci` nutzen beide den Node-basierten Runner. Sie benoetigen PowerShell nicht als Entrypoint, fuehren unter Windows aber inzwischen intern einen Kompatibilitaetscheck gegen `powershell.exe` aus, damit der native Deployer mit Windows PowerShell 5.1 kompatibel bleibt. Der PowerShell-Wrapper bleibt nur fuer Nutzer verfuegbar, die bewusst einen Windows-nativen Entrypoint wollen.

Erforderliche lokale Werkzeuge fuer die volle Validierungsflaeche:

- Node.js 22 oder neuer fuer die skriptbasierten Test-Runner
- Python 3.12 oder neuer, oder `PYTHON=/path/to/python`, fuer Helper-Compile-Checks und Rollup-Tests
- Docker mit lokalem Port-Publishing fuer Query-Readback, Render-E2E und Rollup-E2E
- Playwright-Chromium-Browser-Abhaengigkeiten fuer Render-Smoke-Checks; in Linux-CI wird `npx playwright install --with-deps chromium` genutzt
- Bash oder Git Bash fuer Deploy-Shell-Syntaxchecks. Unter Windows wird dieser Check uebersprungen, wenn Bash nicht verfuegbar ist.

## Erforderliche Umgebung

Nutze `--env=.env.local` oder `.env`.

Immer erforderlich:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_VM_EVCC_UID`

Erforderlich fuer Render-Smoke-Checks und Screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID`, Default: `evcc-test`
- `GRAFANA_TEST_FOLDER_TITLE`, Default: `EVCC Test`
- `GRAFANA_SCREENSHOT_WAIT_MS`, Default: `3500`
- `GRAFANA_RENDER_SMOKE_WAIT_MS`, Default: `GRAFANA_SCREENSHOT_WAIT_MS` oder `3500`
- `GRAFANA_TIME_FROM` und `GRAFANA_TIME_TO` fuer globalen Screenshot-Zeitbereichs-Override

## Namenskonvention

VM-Tags:

- Quell-Referenzset: `vm-original-<sourceLanguage>`
- generiertes lokalisiertes Set: `vm-<language>-gen`

Manifest-Beispiele:

- `tests/artifacts/import-manifest-vm-original-en.json`
- `tests/artifacts/import-manifest-vm-fr-gen.json`

## import-dashboards-raw.mjs

Verhalten:

- loest Datasource-Inputs aus Env-UIDs auf
- loest Expression-Datasource-Inputs auf `__expr__` auf
- versieht Dashboardtitel mit Prefix `[<TAG>]`
- schreibt Dashboard-UIDs mit dem Tag um
- schreibt ein Importmanifest nach `tests/artifacts/import-manifest-<tag>.json`

Beispiel:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=vm-fr-gen --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/original/en --tag=vm-en-tabs --manifest=tests/artifacts/import-manifest-vm-en-tabs.json
```

## smoke-check.mjs

Checks:

- Dashboard existiert
- Titel existiert
- Panelanzahl groesser als null
- keine nicht aufgeloesten Importplatzhalter wie `${VAR_*}` oder `${DS_*}`

## capture-screenshots.mjs

Ausgaben:

- `tests/artifacts/screenshots/vm/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/vm/<tag>/mobile/*.png`

## render-smoke-check.mjs

Checks:

- importierte Dashboard-Seite rendert mindestens ein Panel-Grid-Item
- bekannte Grafana-Fehlertexte sind nicht sichtbar
- kritische Panels werden ueber `/d-solo/...&panelId=...` geoeffnet
- kritische Panels rendern nicht `No data`, ausser `--fail-no-data=false` wird uebergeben

## render-e2e.mjs

Zweck: disposable Grafana und VictoriaMetrics starten, Fixture-Daten importieren und die kritischen Dashboard-Panels browserbasiert rendern.

Standard-Fixture mit AUX/EXT:

```bash
npm run test:render-e2e
```

No-AUX/EXT-Fixture fuer Nutzer ohne Zusatzzaehler. Die Fixture enthaelt Hausverbrauch und Kernmetriken, aber keine `auxPower_value`-, `extPower_value`-, `evcc_aux_*`- oder `evcc_ext_*`-Serien:

```bash
npm run test:render-e2e:no-aux-ext
```

## rollup-e2e.py
Zweck: realen Rollup-Schreibpfad gegen eine disposable VictoriaMetrics-Instanz validieren.

Checks:

- importiert eine kleine rohe EVCC-Fixture in eine isolierte VM
- fuehrt `evcc-vm-rollup.py backfill --replace-range --write` zweimal aus
- prueft erwartete taegliche PV-, Home-, Grid-Import- und Loadpoint-Rollup-Werte
- prueft, dass der wiederholte Replace-Lauf keine doppelten taeglichen Samples hinterlaesst

Docker-Modus startet und stoppt einen temporaeren VM-Container:

```bash
python scripts/test/rollup-e2e.py --docker
```

Externer disposable VM-Modus ist absichtlich geschuetzt:

```bash
python scripts/test/rollup-e2e.py --base-url=http://127.0.0.1:8428 --confirm-disposable
```

Nicht auf Produktion zeigen. Der Test schreibt rohe Fixture-Daten und loescht alle `e2e_evcc_*`-Rollup-Serien plus seine eigene `e2e_fixture`-Rohserie.

## rename-label-e2e.py

Zweck: Sicherheit historischer Label-Value-Renames gegen eine disposable VictoriaMetrics-Instanz validieren.

Checks:

- importiert einen alten PV-Titel plus eine bereits vorhandene Zielserie mit neuem Titel
- fuehrt `vm-rewrite-label-value.py` im Dry-run-Modus aus und verlangt die Empfehlung `GO FOR IT`
- fuehrt `vm-rewrite-label-value.py --merge-target --write` aus
- prueft, dass der alte Titel entfernt ist und der neue Titel sowohl die umgeschriebene Historie als auch das vorher existierende Zielsample enthaelt

Docker-Modus startet und stoppt einen temporaeren VM-Container:

```bash
python scripts/test/rename-label-e2e.py --docker
npm run test:rename-e2e
```

Externer disposable VM-Modus ist geschuetzt:

```bash
python scripts/test/rename-label-e2e.py --base-url=http://127.0.0.1:8428 --confirm-disposable
```

Nicht auf Produktion zeigen. Der Test schreibt und loescht nur eigene Fixture-Labels, ist aber absichtlich ein destruktiver Rewrite-Pfad-Test.

## dedup-series-e2e.py

Zweck: Sicherheit exakter Serien-Deduplizierung gegen eine disposable VictoriaMetrics-Instanz validieren.

Checks:

- importiert doppelte Rohsamples in eine isolierte VM
- fuehrt `vm-dedup-series.py` im Dry-run-Modus aus und verlangt die Empfehlung `GO FOR IT` fuer identische Duplikate
- fuehrt `vm-dedup-series.py --write` aus und prueft, dass doppelte Timestamps entfernt sind
- fuehrt einen zweiten Dry-run aus und prueft, dass die Bereinigung idempotent ist
- prueft, dass widerspruechliche doppelte Werte den Schreibpfad stoppen
- prueft, dass Superset-Delete-Risiko vor jedem Schreibzugriff blockiert wird

Docker-Modus startet und stoppt einen temporaeren VM-Container:

```bash
python scripts/test/dedup-series-e2e.py --docker
npm run test:dedup-e2e
```

Externer disposable VM-Modus ist geschuetzt:

```bash
python scripts/test/dedup-series-e2e.py --base-url=http://127.0.0.1:8428 --confirm-disposable
```

Nicht auf Produktion zeigen. Der Test uebt absichtlich Delete-and-Reimport-Verhalten fuer exakte Serien.

## rollup-path-check.mjs

Zweck: vollstaendigen deterministischen Rollup-Validierungspfad nach Rollup-, Query- oder Dashboard-Aenderungen mit einem Befehl ausfuehren.

```bash
npm run test:rollup-path
```

Der Befehl fuehrt statische/unit/dashboard Checks, externe Tibber-/Influx-/VRM-Cache-Validierung, MetricsQL-Query-Readback gegen disposable VictoriaMetrics, Grafana-Render-E2E mit Fixture-Daten und disposable Rollup-Replace-E2E aus. Er dauert absichtlich laenger als `npm run test:ci`, weil er den kompletten Pfad von Rollup bis Dashboard abdeckt.

Nuetzliche Optionen:

- `-- --skip-render` ueberspringt nur das Browser-Render-E2E, wenn lokal ein schnellerer Vorcheck gebraucht wird.
- `-- --strict-energy` verlangt private Tibber-/Influx-/VRM-Cache-Snapshots, statt fehlende Caches als nicht blockierende Skips zu behandeln.
- `-- --vm-base-url http://127.0.0.1:8428` fuegt Live-VM-Rollup-Vergleich zur Energievalidierung hinzu.

## run-suite.mjs

Verhalten:

- fuehrt Lokalisierungsvorbereitung standardmaessig aus
- liest die VM-`languages.json`
- nimmt das Quell-Referenzset als `<vmTagPrefix>-original-<sourceLanguage>` auf
- nimmt jeden generierten Zielordner als `<vmTagPrefix>-<language>-gen` auf
- wenn `--screenshots=true`, wird vor jedem Set `cleanup-grafana.mjs` ausgefuehrt
- standardmaessig wird `cleanup-grafana.mjs` auch ohne Screenshots vor jedem Set ausgefuehrt, damit Library-Panel-UIDs sprachuebergreifend nicht kollidieren; `--cleanup-between=false` nur nutzen, wenn alle importierten Sets bewusst nebeneinander bleiben sollen
- importiert das Set
- fuehrt Smoke-Check aus
- fuehrt optional mit `--render-smoke=true` den Render-Smoke-Check aus
- nimmt optional Screenshots auf

Beispiele:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
node scripts/test/run-suite.mjs --env=.env.local --render-smoke=true
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

## cleanup-grafana.mjs

Zweck: alle Dashboards und alle Library Panels im konfigurierten Grafana-Testordner entfernen.

Datasources werden nicht angefasst.

## Deploy-Defaults

`deploy-dashboards.mjs` unterstuetzt diese Defaults fuer VM:

- Default-Sprache: `en`
- Default-Variante: `orig`
- Default-Source-Mode: `github`
- Default-GitHub-Repo: der konfigurierte lokale `github`-Remote

Unterstuetzte Argumente:

- `--source-mode=localdir|rawurl|github`
- `--source=<local path or repo-relative path>`
- `--github-repo=<owner/repo>`
- `--github-ref=<branch-or-tag>`
- `--raw-base-url=<repository-root-raw-url>`
- `--language=<code>`
- `--variant=orig|generated`
- feste Manifest-Dashboardliste aus `dashboards/deploy-manifest.json`

Beispiel lokales Deployment:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --source-mode=localdir --purge=true --smoke=true
```

Beispiel GitHub-basiertes Deployment:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --purge=true --smoke=true
```
