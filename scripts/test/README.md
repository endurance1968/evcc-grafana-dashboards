# Testskripte

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt lokale Tests, E2E-Helfer und CI-nahe Pruefungen fuer Dashboards, Rollups, Lokalisierung und Deployment.

## Standardpfad

```bash
npm test
```

Dieser Befehl fuehrt die lokalen Checks aus:

- Python Unit Tests und Syntaxchecks
- Node Syntaxchecks
- Dashboard JSON Parse/Audit
- Dashboard-Semantikcheck
- Cross-Platform-Audit
- PowerShell-Deployer-Kompatibilitaet
- Lokalisierungs-Idempotenz
- Bash-Syntaxchecks fuer Deploy-Skripte

## Wichtige Einzeltests

```bash
npm run test:cross-platform
npm run test:powershell-compat
npm run test:localization-idempotency
npm run test:energy-validation
npm run test:query-readback
npm run test:render-e2e
npm run test:rollup-path
```

## Rollup-Pfad

Der vollstaendige Rollup-Validierungspfad ist:

```bash
npm run test:rollup-path
```

Auf privaten Runnern kann er mit echten Daten strenger laufen:

```bash
npm run test:rollup-path -- --strict-energy --vm-base-url http://<vm-host>:8428
```

## Dashboard Deploy Testhelfer

`deploy-dashboards.mjs` importiert Dashboard-Dateien in einen Testordner.

Unterstuetzte Source Modes:

- `localdir`
- `rawurl`
- `github`

Beispiel:

```bash
node scripts/test/deploy-dashboards.mjs --env=.env.local --source-mode=localdir --purge=true --smoke=true
```

## Docker-Hinweise

Einige E2E-Tests verwenden disposable Docker-Container. Diese Tests duerfen keine produktiven Daten schreiben. Fuer private Live-Validierung nur explizit dafuer angelegte VictoriaMetrics-Ziele verwenden.