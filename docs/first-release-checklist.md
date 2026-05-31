# First Release Checkliste

Englische Version: [first-release-checklist_EN.md](./first-release-checklist_EN.md).

Diese Checkliste sammelt die Punkte fuer die erste stabile Endnutzer-Freigabe.

## Release-Kriterien

- [x] Grafana 13 Tab-Dashboards sind der Standardpfad.
- [x] Row-/Dashboard-Set-Auswahl ist aus den Deployern entfernt.
- [x] `deploy-python.sh` funktioniert als Linux-Standardpfad.
- [x] `deploy-bash.sh` funktioniert fuer Bash + `jq`.
- [x] `deploy.ps1` funktioniert auf Windows PowerShell.
- [x] Dashboard-Variable-Overrides sind dokumentiert.
- [x] `PURGE_ONLY` ist dokumentiert.
- [x] Source Modes `github`, `rawurl`, `localdir` sind dokumentiert.
- [x] Doppelte Env-Keys werden abgelehnt.
- [x] Migration mit realen Daten wurde validiert.
- [x] Manuelle Sichtpruefung der Dashboards wurde erfolgreich abgeschlossen.

## Technische Mindesttests

- [x] `npm test`
- [x] PowerShell-Kompatibilitaet
- [x] Bash-Syntaxcheck ueber Git Bash
- [x] Lokalisierungs-Idempotenz
- [x] Dashboard-Semantikcheck
- [x] Render-/Query-Pfade fuer kritische Panels im Testpfad

## Dokumentation

- [x] Einstieg unter `README.md` und `docs/README.md`
- [x] Systemanforderungen
- [x] VictoriaMetrics Debian/Docker
- [x] Grafana Debian/Docker
- [x] InfluxDB-zu-VictoriaMetrics-Migration
- [x] Dashboard-Deployment
- [x] Troubleshooting
- [x] Release Notes
- [x] Screenshots und Screenshot-Regeln

## Vor Release nochmal pruefen

- [ ] Tags/Version im Release festlegen.
- [ ] Release Notes final lesen.
- [ ] GitHub-README-Darstellung pruefen.
- [ ] Letzten Deploy gegen frische Grafana-Instanz testen.
- [ ] Keine internen IPs in oeffentlichen Beispielpfaden.