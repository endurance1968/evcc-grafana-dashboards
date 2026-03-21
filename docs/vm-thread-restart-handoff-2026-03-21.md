# VM Thread Restart Handoff

Stand: 2026-03-21

Diese Notiz fasst den aktuellen VictoriaMetrics-Stand nach der Umstellung auf die familiengetrennte Repo-Struktur, dem ersten produktiven VM-Localization-Flow und der nachtraeglichen Härtung gegen das zusaetzliche `host`-Label zusammen.

## Repo- und Branch-Stand

- Branch `codex/victoriametrics-en` wurde in `main` fast-forward gemerged.
- `main` wurde auf beide Remotes gepusht:
  - Forgejo `origin/main`
  - GitHub `github/main`
- Der letzte relevante Commit fuer die heutige VM-Haertung ist:
  - `c758f12` `fix: harden vm dashboards against host labels`

## Aktueller VM-Flow im Repo

Default-Pfad fuer VictoriaMetrics:

- Source-Dashboards:
  - `dashboards/original/en`
- Generierte Dashboards:
  - `dashboards/translation/<language>`
- Mapping-Dateien:
  - `dashboards/localization/en_to_<language>.json`
- Maintainer-Doku:
  - `docs/localization-maintainer-workflow.md`
  - `docs/grafana-localization-testing.md`
  - `docs/localization-review-2026-03-21.md`
  - diese Datei

Legacy-Influx bleibt strikt getrennt unter:

- `dashboards/influx-legacy`
- `docs/influx-legacy`
- `scripts/influx-legacy`

## Was heute verifiziert wurde

### 1. Deploy und Test-Flow

Der VM-Originalsatz laesst sich per Testskripten deployen:

```bash
node scripts/test/deploy-dashboards.mjs --family=vm --env=.env.local --language=en --variant=orig --purge=true --smoke=true
```

Grafana-Testinstanz:

- URL: `http://192.168.1.189:3000`
- Datasource: `VM-EVCC`
- Datasource-UID: `vm-evcc`
- Testfolder: `evcc-l10n-test`

Aktuelle Dashboard-URLs:

- `http://192.168.1.189:3000/d/vm-en-orig-adsmz7v/vm-en-orig-vm3a-evcc3a-today`
- `http://192.168.1.189:3000/d/vm-en-orig-adddvtj/vm-en-orig-vm3a-evcc3a-today-details`
- `http://192.168.1.189:3000/d/vm-en-orig-adtcx74/vm-en-orig-vm3a-evcc3a-today-mobile`

### 2. Gauge-Panel-Fix

Das Panel `EVCC: VM: Kennzahlen Gauges` lieferte zunaechst zu viele Gauges, weil mehrere Serien in die Math-Queries liefen.

Gefixt in:

- `dashboards/original/en/VM_ EVCC_ Today.json`
- `dashboards/original/en/VM_ EVCC_ Today - Mobile.json`

Die Eingangsqueries wurden dort auf eine einzige Serie reduziert.

### 3. Host-Label-Incident

Der groessere produktive Fehler lag danach im Panel `EVCC: VM: Energie`:

- `Today` zeigte Dopplungen wie `PV 1 / PV 2`, `Haus 1 / Haus 2`, `Speicher laden 1 / 2`
- `Yesterday` wirkte normal

Ursache:

- Im Live-Pfad wurden EVCC-Metriken zeitweise mit `host="lx-telemetry-ingest"` geschrieben.
- Historische bzw. spaetere Daten lagen gleichzeitig ohne `host` vor.
- VictoriaMetrics behandelt beide Labelsets als getrennte Serien.

Wichtiger Befund:

- Die Dubletten waren nicht nur in VM, sondern fuer den betroffenen Tageszeitraum auch in Influx vorhanden.
- Ein Reimport per `vmctl influx` aus Influx nach VM hat die host-getaggten Uebergangsdaten deshalb wieder mitgebracht.

### 4. Dashboard-Haertung

Da die Infrastruktur-Tags nicht in jeder Phase sauber genug garantiert werden konnten, wurden die sichtbaren Today-/Mobile-Abfragen gegen `host` gehaertet.

Umgesetzt in:

- `dashboards/original/en/VM_ EVCC_ Today.json`
- `dashboards/original/en/VM_ EVCC_ Today - Mobile.json`
- alle betroffenen generierten VM-Uebersetzungen unter `dashboards/translation`

Technik:

- Energie-/Tagesintegrale jetzt mit `sum without(host)(...)`
- aktuelle Leistungsabfragen jetzt mit `avg without(host)(...)`

Die live gespeicherten Grafana-Library-Panels wurden danach komplett geloescht und aus dem aktuellen Repo-Stand neu deployed.

## Wichtige Folgerung fuer spaetere Arbeit

Fuer VictoriaMetrics duerfen zusaetzliche Infrastruktur-Labels wie `host` nicht stillschweigend als stabil angenommen werden.

Wenn neue VM-Dashboards hinzukommen, sollte bei sichtbaren Summen-/Integral-/Momentanwert-Panels immer geprueft werden:

- ob ungewuenschte Labels wie `host` existieren
- ob Queries aggregiert werden muessen, z. B. mit `sum without(host)` oder `avg without(host)`

## Offene Themen

### 1. Datenhygiene

Die Dashboards sind jetzt robust, aber die Datenbasis fuer den Uebergangstag wurde nicht vollstaendig historisch bereinigt.

Wenn spaeter wirklich ein sauberer Datenbestand gewuenscht ist, muss der Zeitraum in Influx und/oder VM nochmals gezielt bereinigt werden.

### 2. VM-Aggregationen

Der Upstream-Maintainer hat VM-Aggregationen bereits konzeptionell erwaehnt, aber im Original-Repo gibt es noch kein belastbares VM-natives Aggregations-Setup.

Stand heute:

- dokumentarisch vorhanden im Branch `upstream/victoria-metrics`
- echte Script-Basis weiterhin Influx-zentriert
- daher fuer unsere VM-Schiene weiterhin ein offenes Folgeprojekt

### 3. Upstream-Source-Qualitaet

Die drei VM-Upstream-Dashboards enthalten weiterhin gemischtsprachige interne Strings und teils gekoppelte sichtbare Labels.

Das ist kein Blocker fuer den aktuellen Testsatz, bleibt aber Refactor-Arbeit.

## Noetige Zugriffe und Rechte fuer spaetere Fortsetzung

Wenn der Thread spaeter neu gestartet wird, werden voraussichtlich wieder diese Zugriffe benoetigt:

- Netzwerkzugriff aus Codex auf:
  - Grafana `http://192.168.1.189:3000`
  - VictoriaMetrics `http://192.168.1.160:8428`
  - InfluxDB `http://192.168.1.183:8086`
- optional Shell-/SSH-Zugriff auf:
  - `root@192.168.1.198` fuer Telegraf
  - VM-Host fuer `delete_series`, `resetRollupResultCache`, `force_merge`, `vmctl`
- Git push auf:
  - `origin`
  - `github`

Typische Befehle, die spaeter wieder relevant sein koennen:

```bash
node scripts/test/deploy-dashboards.mjs --family=vm --env=.env.local --language=en --variant=orig --purge=true --smoke=true
```

```bash
node scripts/test/run-suite.mjs --family=vm --env=.env.local --screenshots=true --cleanup-final=true
```

```bash
curl -X POST 'http://192.168.1.160:8428/api/v1/admin/tsdb/delete_series' \
  --data-urlencode 'match[]={db="evcc",host="lx-telemetry-ingest"}'
```

```bash
curl -X POST 'http://192.168.1.160:8428/internal/resetRollupResultCache'
```

## Empfohlene Lese-Reihenfolge bei Thread-Neustart

1. `docs/vm-thread-restart-handoff-2026-03-21.md`
2. `docs/victoriametrics-handoff-2026-03-21.md`
3. `docs/localization-maintainer-workflow.md`
4. `docs/grafana-localization-testing.md`
5. `docs/next-steps.md`
