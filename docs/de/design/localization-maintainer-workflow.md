# Maintainer-Workflow fuer Lokalisierung

Englische Version: [localization-maintainer-workflow.md](../../en/design/localization-maintainer-workflow.md).

Dieses Dokument beschreibt den aktuellen Maintainer-Workflow fuer die VictoriaMetrics-Dashboards unter `dashboards`.

## Mentales Modell

In diesem Repository gibt es zwei Uebersetzungsschichten.

### Schicht 1: Mappinggetriebene Generierung

Quelle:

- `dashboards/original/<sourceLanguage>`

Mappings:

- `dashboards/localization/<source>_to_<target>.json`

Generierte Ausgabe:

- `dashboards/translation/<language>`

Diese Schicht ist skriptgesteuert und sollte immer zuerst laufen.

### Schicht 2: sichere Display-only-Bereinigung

Nach der Generierung koennen sichtbare UI-Texte uebrig bleiben, weil sie in dashboard-spezifischen Display-Properties liegen, die vom Generator nicht vollstaendig abgedeckt werden.

Beispiele:

- Display-Name-Overrides in Panel-Field-Config
- einige Paneltitel
- einige Variablenlabels oder Beschreibungen

Diese Schicht ist ebenfalls skriptgesteuert und laeuft nur auf generierten Dashboards.

Nicht auf `dashboards/original` anwenden, ausser du refaktorierst absichtlich die VM-Quelldashboards.

## Aktueller VM-Umfang

Aktuelles Upstream-VM-Quellset:

- `dashboards/original/en/VM_EVCC_Today.json`
- `dashboards/original/en/VM_EVCC_Today-Mobile.json`
- `dashboards/original/en/VM_EVCC_Today-Details.json`

Wichtiger Hinweis:

- der importierte Upstream-Snapshot ist gemischtsprachig
- mehrere sichtbare Labels sind weiterhin Deutsch, obwohl das VM-Quelldashboard-Set als `en` behandelt wird

## Repository-Umfang

- Sprachkonfiguration: `dashboards/localization/languages.json`
- Source of Truth: `dashboards/original/<sourceLanguage>`
- Sprachmapping: `dashboards/localization/<source>_to_<target>.json`
- generierte Ausgaben: `dashboards/translation/<language>`

## Voraussetzungen

- Node.js 20+
- Befehle koennen aus dem Repository-Root ausgefuehrt werden
- fuer Grafana-Validierung siehe [grafana-localization-testing.md](./grafana-localization-testing.md)

## Standard-Update-Workflow

### 1. Quelldashboards bei Bedarf aktualisieren

Bearbeiten:

- `dashboards/original/<sourceLanguage>`

Nur fuer echte Quellaenderungen oder strukturelle Panel-Refactorings tun.

### 2. Veraltete Mapping-Eintraege entfernen

Ausfuehren, wenn sich Quelldashboards geaendert haben und Mapping-Dateien nur aktuelle Quelltexte enthalten sollen:

```bash
node scripts/localization/prune-mappings-to-source.mjs
```

Der Befehl ist standardmaessig ein Dry-run. Wenn die gemeldeten Entfernungen erwartet sind, die bereinigten Mapping-Dateien explizit schreiben:

```bash
node scripts/localization/prune-mappings-to-source.mjs --write
```

Das entfernt `exact`- und `contains`-Eintraege, die keinen aktuellen Quelldashboard-Text mehr treffen, nur wenn `--write` gesetzt ist.

### 3. Fehlende Mapping-Abdeckung auditieren

```bash
node scripts/localization/audit-localization.mjs
```

Erzeugte Kandidatendateien pruefen:

- `dashboards/localization/missing-<source>_to_<target>.exact.json`

Der Abschnitt `exactSources` listet die Quelldashboard-Dateinamen, die jeden Kandidaten erzeugt haben.

### 4. Mapping-Kandidaten uebersetzen oder uebernehmen

Die Skripte fuehren keine eigentliche Sprachuebersetzung aus. Ein menschlicher Uebersetzer oder eine KI muss den finalen Zielsprachentext in den Mapping-JSON-Dateien liefern, zum Beispiel:

- `dashboards/localization/en_to_de.json`
- `dashboards/localization/en_to_fr.json`
- `dashboards/localization/en_to_hi.json`

`exact` fuer vollstaendige Labels und stabile Phrasen verwenden.

`contains` nur fuer sehr stabile Token-Ersetzungen verwenden, die kontextuebergreifend sicher sind.

Wenn alle fehlenden Kandidaten zuerst als bewusste Platzhalter akzeptiert werden sollen:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all
```

Der Befehl ist standardmaessig ein Dry-run. Wenn die gemeldeten Platzhalter-Ergaenzungen erwartet sind, explizit schreiben:

```bash
node scripts/localization/adopt-missing-into-mappings.mjs --target=all --write
```

Das kopiert Kandidaten aus `missing-*.exact.json` nur mit `--write` als `source -> source` in die echten Mapping-Dateien. Das ist kein Uebersetzungsschritt; ersetze die Platzhalterwerte durch echte Uebersetzungen, bevor lokalisierte Ausgabe erwartet wird.

### 5. Lokalisierte Dashboards erzeugen

```bash
node scripts/localization/generate-localized-dashboards.mjs
```

### 6. Sichere Display-only-Uebersetzungen anwenden

Wichtig: diesen Schritt erst ausfuehren, nachdem Schritt 5 vollstaendig beendet ist. Beide Skripte nicht parallel starten.

```bash
node scripts/localization/apply-safe-display-translations.mjs
```

Dieser Schritt beruehrt nur nutzersichtbare Felder in generierten Dashboards, zum Beispiel:

- Paneltitel
- Linktitel
- Variablenlabels und Beschreibungen
- Override-`displayName`-Werte

### 7. Generierte Dashboards auf verbleibenden sichtbaren Quellsprachentext pruefen

Review-Methoden:

- JSON direkt inspizieren
- oder bevorzugt Grafana-Screenshots erzeugen und die gerenderten Dashboards pruefen

### 8. In Grafana validieren

Den vollstaendigen Testworkflow nutzen aus:

- [grafana-localization-testing.md](./grafana-localization-testing.md)

Fuer den Standard-End-to-End-Pfad fuehrt `run-suite.mjs` beide Vorbereitungsschritte automatisch aus, ausser sie werden mit `--prepare=false` deaktiviert.

## Safe-vs-unsafe-Uebersetzungsregel

### Sicher

Ein String ist sicher, wenn er nur fuer Nutzer sichtbar ist und nicht fuer interne Verdrahtung verwendet wird.

Hauefig sichere Beispiele:

- `displayName`-Override-Werte
- Paneltitel
- Linktitel
- Variablenlabels und Beschreibungen

### Unsicher bis refaktoriert

Ein String ist unsicher, wenn er Panel-Logik verbindet.

Hauefige Beispiele:

- `refId`
- `alias`-Werte, die in Matcher-Optionen, Regexes, Transformationen oder Formeln wiederverwendet werden
- `matcher.options`
- Regex-Matcher
- Formeln, die lokalisierte Namen referenzieren

Die skriptgesteuerte Alias-Uebersetzung in `apply-safe-display-translations.mjs` fuehrt einen Panel-level-Sicherheitscheck aus und ueberspringt Aliase, die an interne Verdrahtung gekoppelt wirken.

## Langfristige Wartbarkeitsregel

Wenn ein sichtbares Label auch als interner Schluessel genutzt wird, ist das Paneldesign nicht lokalisierungsfreundlich.

Bevorzugtes Design:

- stabile interne IDs wie `gridImport`, `selfConsumption`, `batteryCharge`
- uebersetzte Labels nur in Display-Properties

Das ist die wichtigste strukturelle Verbesserung, die Maintainer in VM-Quelldashboards anstreben sollten.

## Aktueller VM-Meilenstein

Stand 2026-03-21:

- feste VM-Konfiguration ist vorhanden
- Zielsprachen sind `de`, `fr`, `nl`, `es`, `it`, `zh`, `hi`
- das aktuelle VM-Quellset mit drei Dashboards generiert sauber
- Lokalisierungs-Audit ist fuer den aktuellen skriptgesteuerten Schluesselsatz sauber

## Review-Checkliste vor Commit

- Quelldashboards nur geaendert, wenn absichtlich erforderlich
- Mapping-Dateien soweit moeglich aktualisiert, statt zuerst generierte JSONs zu patchen
- generierte Dashboards nach Mapping-Aenderungen neu erzeugt
- sichere Display-only-Uebersetzungen ueber `apply-safe-display-translations.mjs` angewendet
- keine unbeabsichtigte unsichere Aenderung an `refId`, `matcher.options`, Regexes oder Formeln
- vollstaendiger Grafana-Smoke-Check und Screenshot-Lauf abgeschlossen
- verbleibende gekoppelte oder datengetriebene Texte separat dokumentiert
