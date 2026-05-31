# Grafana-Lokalisierung testen

Englische Version: [grafana-localization-testing_EN.md](./grafana-localization-testing_EN.md).

Dieses Dokument beschreibt den aktuellen End-to-End-Workflow, um die VictoriaMetrics-Dashboards gegen eine echte Grafana-Testinstanz zu validieren.

## Umfang

Nutze diesen Workflow, wenn du:

- lokalisierte Dashboard-JSON-Dateien erzeugen willst
- sie in einen Grafana-Testordner importieren willst
- per Smoke-Check pruefen willst, dass die Importe erfolgreich waren
- vergleichbare Desktop- und Mobile-Screenshots erstellen willst
- verbleibenden nicht uebersetzten UI-Text pruefen willst

Dieser Workflow validiert das, was in Grafana sichtbar ist. Query-Interna werden nicht blind uebersetzt.

## Voraussetzungen

- Node.js 20+
- erreichbare Grafana-Testinstanz
- Grafana-API-Token mit Dashboard-Schreib-/Loeschrechten in der Zielorganisation
- konfigurierte VictoriaMetrics-Datasource fuer EVCC
- fuer Screenshot-Automation:
  - Projektabhaengigkeiten via `npm install` installiert
  - Playwright Chromium via `npx playwright install chromium` installiert
  - Grafana-Benutzername/-Passwort fuer Browser-Login verfuegbar

## Erforderliche Umgebung

Nutze `.env.local` oder `.env`.

Erforderliche Variablen fuer VM:

- `GRAFANA_URL`
- `GRAFANA_API_TOKEN`
- `GRAFANA_DS_VM_EVCC_UID`

Wenn `GRAFANA_DS_VM_EVCC_UID` nicht gesetzt ist, faellt der Importer auf `vm-evcc` zurueck. Das entspricht der aktuellen VM-Test-Datasource-UID.

Erforderlich fuer Screenshots:

- `GRAFANA_USERNAME`
- `GRAFANA_PASSWORD`

Optional:

- `GRAFANA_TEST_FOLDER_UID`, Default: `evcc-test`
- `GRAFANA_TEST_FOLDER_TITLE`, Default: `EVCC Test`
- `GRAFANA_SCREENSHOT_WAIT_MS`, Default: `3500`
- `GRAFANA_TIME_FROM` und `GRAFANA_TIME_TO`, wenn die eingebaute Time-Range-Logik ueberschrieben werden soll

## Repository-Konventionen

### Quell- und generierte Ordner

- Quelldashboards: `dashboards/original/<sourceLanguage>`
- generierte lokalisierte Dashboards: `dashboards/translation/<language>`
- Mapping-Dateien: `dashboards/localization/<source>_to_<target>.json`
- Uebersetzungs-Auditberichte: `dashboards/localization/missing-<source>_to_<target>.exact.json`

### Import-Tags und Manifeste

Aktuelle VM-Import-Tags:

- Quell-Referenzset: `vm-original-<sourceLanguage>`
- generierte Sets: `vm-<language>-gen`

Aktuelle Manifest-Namen:

- `tests/artifacts/import-manifest-vm-original-en.json`
- `tests/artifacts/import-manifest-vm-de-gen.json`
- `tests/artifacts/import-manifest-vm-fr-gen.json`

## Schritt 1: Lokalisierte Dashboards erzeugen

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

Das kopiert `dashboards/original/<sourceLanguage>` in jeden konfigurierten Zielordner unter `dashboards/translation/` und wendet mappingbasierte Uebersetzungen fuer sichere Textschluessel an.

## Schritt 2: Sichere Display-only-Uebersetzungen anwenden

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

Wichtig: Schritt 1 und Schritt 2 strikt nacheinander ausfuehren. Nicht parallel starten.

Typisch sichere Faelle:

- Paneltitel
- Linktitel
- Override-Anzeigenamen in `fieldConfig.overrides[*].properties[*].value`
- Variablenlabels und Beschreibungen

Typisch unsichere Faelle, die nicht blind uebersetzt werden duerfen:

- `refId`
- `matcher.options`
- Regex-Matcher
- Formeln oder Expressions, die uebersetzte Strings referenzieren
- `alias`, wenn es von Matcher-Optionen, Regexes, Transformationen oder Formeln wiederverwendet wird

## Schritt 3: Uebersetzungsabdeckung auditieren

```bash
node scripts/localization/audit-localization.mjs
```

Das erzeugt pro Sprache Kandidatendateien unter `dashboards/localization/missing-*.exact.json`. Jeder Bericht enthaelt `exactSources` mit den Quelldashboard-Dateinamen fuer jeden fehlenden Kandidaten.

## Schritt 4: Ein Sprachset importieren und Smoke-Check ausfuehren

Beispiel fuer Franzoesisch:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/translation/fr --tag=vm-fr-gen --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

Quell-Referenzbeispiel:

```bash
node scripts/test/import-dashboards-raw.mjs --env=.env.local --source=dashboards/original/en --tag=vm-original-en --manifest=tests/artifacts/import-manifest-vm-original-en.json
node scripts/test/smoke-check.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-original-en.json
```

## Schritt 5: Screenshots fuer ein Set aufnehmen

```bash
node scripts/test/capture-screenshots.mjs --env=.env.local --manifest=tests/artifacts/import-manifest-vm-fr-gen.json
```

Ausgaben:

- `tests/artifacts/screenshots/vm/<tag>/desktop/*.png`
- `tests/artifacts/screenshots/vm/<tag>/mobile/*.png`

## Schritt 6: Vollstaendige Suite ausfuehren

Ohne Screenshots:

```bash
node scripts/test/run-suite.mjs --env=.env.local
```

Mit Screenshots:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true
```

Aktuelle generierte Dateien testen, ohne Vorbereitung erneut auszufuehren:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --prepare=false
```

Nach dem Lauf mit leerem Grafana-Testordner enden:

```bash
node scripts/test/run-suite.mjs --env=.env.local --screenshots=true --cleanup-final=true
```

### Verhalten der Full Suite

Fuer jedes konfigurierte Set macht die Suite:

1. lokalisierte Dashboards neu erzeugen, ausser `--prepare=false`
2. sichere Display-only-Uebersetzungen anwenden, ausser `--prepare=false`
3. wenn Screenshots aktiviert sind, zuerst den gesamten Grafana-Testordner bereinigen
4. das Set importieren
5. Smoke-Check ausfuehren
6. Screenshots aufnehmen

## Cleanup-only-Befehl

```bash
node scripts/test/cleanup-grafana.mjs --env=.env.local
```

Datasources werden nicht angefasst.

## Aktuelles Screenshot-Layout

VM-Screenshots werden hier gruppiert:

- `tests/artifacts/screenshots/vm/original-en`
- `tests/artifacts/screenshots/vm/en-gen`
- `tests/artifacts/screenshots/vm/de-gen`
- und so weiter

## VM-spezifischer Hinweis

Die aktuelle Upstream-VM-Quelle ist nur ein Drei-Dashboard-Snapshot und enthaelt noch gemischtsprachige Interna.

Das bedeutet:

- der aktuelle Workflow reicht fuer Lokalisierung, Smoke-Checks und Screenshot-Review aus
- einige verbleibende Source-Language-Interna koennen spaeter noch Source-Refactorings erfordern
