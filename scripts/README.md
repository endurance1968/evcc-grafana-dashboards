# Skripte

Englische Version: [README_EN.md](./README_EN.md).

Dieser Ordner enthaelt Deployer, Rollup-Werkzeuge, Migrationshelfer, Lokalisierungsskripte und Tests.

## Endnutzer-Skripte

Dashboard-Deployment:

- `deploy-python.sh`: empfohlener Linux/POSIX-Pfad mit Python
- `deploy-bash.sh`: Bash + `jq`
- `deploy.ps1`: Windows PowerShell
- `vm-dashboard-install.env.example`: kommentierte Beispielkonfiguration

Rollup und Migration:

- `rollup/evcc-vm-rollup.py`: erzeugt taegliche `evcc_*` Rollups
- `rollup/evcc-vm-rollup-prod.conf.example`: Beispielkonfiguration fuer produktiven Betrieb
- `helper/check_data.py`: Datenpraesenz pruefen
- `helper/compare_import_coverage.py`: InfluxDB-Importabdeckung gegen VictoriaMetrics pruefen
- `helper/vm-rewrite-drop-label.py`: Label aus VictoriaMetrics-Reihen entfernen
- weitere Rewrite-/Dedup-Helfer unter `helper/`

## Maintainer-Skripte

- `localization/`: generiert und prueft Dashboard-Uebersetzungen
- `test/`: lokale und CI-nahe Tests
- `helper/deploy-manifest.mjs`: feste deploybare Dashboard-Dateiliste

## Wichtige Testbefehle

```bash
npm test
npm run test:ci
npm run test:rollup-path
npm run test:render-e2e
npm run test:query-readback
```

`npm test` ist der Standardcheck fuer Doku-/Deploy-Skript-Aenderungen. Bei Rollup-, Query- oder Dashboard-Logik den vollstaendigen Rollup-Pfad verwenden.

## Hinweise

- Skripte muessen plattformuebergreifend lauffaehig bleiben.
- Shell-neutrale npm-Entrypoints beibehalten.
- Dashboard-JSON nur unter `dashboards/original/` bearbeiten; `dashboards/translation/` wird generiert.