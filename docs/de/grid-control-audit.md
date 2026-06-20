# EVCC Netzsteuerungs-Audit nach VictoriaMetrics

Englische Version: [grid-control-audit.md](../en/grid-control-audit.md).

Diese optionale Anleitung richtet den Zusatz-Collector fuer den Daily-Details-Tab `Netzsteuerung` ein. Der normale EVCC/Telegraf-Live-Ingest bleibt unveraendert und liefert weiterhin die normalen EVCC-Metriken. Der Audit-Collector liest EVCC nur lesend aus, schreibt zusaetzliche `evcc_audit_*`-Metriken nach VictoriaMetrics und fuehrt lokal eine kumulative CSV-Datei der erkannten Eingriffe.

Der Tab wird nur eingeblendet, wenn im gewaehlten Zeitraum entweder eine aktive externe Begrenzung oder ein EVCC-GridSession-Ereignis erkannt wurde.

## Was der Collector schreibt

Der Collector fragt regelmaessig diese EVCC-Endpunkte ab:

- `/api/state`
- `/api/gridsessions`

Daraus entstehen unter anderem diese Metriken:

- `evcc_audit_hems_effective_max_consumption_power_w`
- `evcc_audit_hems_effective_max_production_power_w`
- `evcc_audit_site_grid_import_power_w`
- `evcc_audit_site_grid_export_power_w`
- `evcc_audit_gridsession_event_start_timestamp_seconds`
- `evcc_audit_minimum_allowed_power_w`
- `evcc_audit_control_group_power_w`

Zusaetzlich schreibt der Collector eine lokale CSV nach `AUDIT_DATA_DIR/events/evcc-grid-control-events.csv`. Diese Datei enthaelt je Eingriff unter anderem Start, Ende, Typ, Status, Limit, Netzleistung zum Start, Quelle des Eingriffs und bei EEBUS die SKI, falls EVCC diese Information liefert.

Normale EVCC-Daten zeigen, was am Netz passiert ist. Diese Audit-Metriken zeigen zusaetzlich, ob EVCC eine externe Begrenzung oder ein Steuerevent kennt.

## Installation auf dem VictoriaMetrics-Host

GitHub-Quelle:

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
```

Alternative Forgejo-Quelle:

```bash
BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"
```

Script und Beispiele installieren:

```bash
sudo mkdir -p /opt/evcc-vm-migration
curl -fsSLo /tmp/collect-evcc-grid-control-audit.py "$BASE/scripts/helper/collect-evcc-grid-control-audit.py"
curl -fsSLo /tmp/evcc-grid-control-audit.env.example "$BASE/scripts/helper/evcc-grid-control-audit.env.example"
curl -fsSLo /tmp/evcc-grid-control-audit.service.example "$BASE/scripts/helper/evcc-grid-control-audit.service.example"

sudo install -m 0755 /tmp/collect-evcc-grid-control-audit.py /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py
sudo install -m 0640 /tmp/evcc-grid-control-audit.env.example /etc/evcc-grid-control-audit.env
sudo install -m 0644 /tmp/evcc-grid-control-audit.service.example /etc/systemd/system/evcc-grid-control-audit.service
```

Konfiguration bearbeiten:

```bash
sudo nano /etc/evcc-grid-control-audit.env
```

Minimalbeispiel:

```env
EVCC_BASE_URL=http://192.168.1.197:7070
VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus
SITE_ID=home
EVCC_API_POLL_SECONDS=10
HTTP_TIMEOUT_SECONDS=10
AUDIT_DATA_DIR=/var/lib/evcc-grid-control-audit
LOCAL_EVENT_CSV=true
```

Wenn der Collector direkt auf dem VictoriaMetrics-Host laeuft, ist `VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus` normalerweise richtig. Die lokale CSV liegt dann standardmaessig unter `/var/lib/evcc-grid-control-audit/events/evcc-grid-control-events.csv`.

## Optional: steuerbare Gruppen benennen

`EVCC_14A_CONTROL_GROUPS` beschreibt ausschliesslich die Gruppen, die im Tab `Netzsteuerung` als steuerbar angezeigt werden sollen. Der Collector leitet daraus keine Gruppen automatisch aus EVCC-Namen ab. Wenn ein Ladepunkt oder eine Waermepumpe nicht steuerbar ist, nimm sie hier nicht auf.

Beispiel fuer zwei einzeln benannte Ladepunkte, eine als EVCC-Ladepunkt gemessene Waermepumpe und Batterie-Netzladung:

```env
EVCC_14A_CONTROL_GROUPS=wallbox1|Carport Ecke|loadpoint|1;wallbox2|Carport Treppe|loadpoint|2;wp1|Daikin-WP|heat_pump|3;battery|Batterie Netzladung|battery_grid_charge|
```

Syntax:

```text
id|Anzeigename|Typ|Mitglieder;id2|Anzeigename|Typ|Mitglieder2
```

Unterstuetzte Typen:

- `loadpoint` / `loadpoints`: Mitglieder sind EVCC-Ladepunktnummern, zum Beispiel `1` oder `1+2`
- `heat_pump`: Mitglieder sind EVCC-Ladepunktnummern fuer Waermepumpen, die in EVCC als Ladepunkt erscheinen
- `battery_grid_charge`: Mitglieder bleiben leer

Fuer die Mindestleistungsberechnung nutzt der Collector standardmaessig die Anzahl der konfigurierten Gruppen. Setze `EVCC_14A_CONTROL_UNITS`, wenn die rechtliche oder technische Anzahl davon abweicht:

```env
EVCC_14A_CONTROL_UNITS=4
```

## Einmaliger Test

Vor dem Service-Start kannst du einen Lauf ausfuehren:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py \
  --evcc-url http://192.168.1.197:7070 \
  --vm-write-url http://127.0.0.1:8428/api/v1/import/prometheus \
  --site home \
  --once
```

Nur anzeigen, ohne nach VictoriaMetrics oder in die lokale CSV zu schreiben:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-migration/collect-evcc-grid-control-audit.py \
  --evcc-url http://192.168.1.197:7070 \
  --site home \
  --once \
  --dry-run
```

## Service aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now evcc-grid-control-audit.service
sudo systemctl status evcc-grid-control-audit.service
```

Logs:

```bash
journalctl -u evcc-grid-control-audit.service -f
```

## Grafana-Datasource

Wenn der Collector in dieselbe VictoriaMetrics schreibt wie die EVCC-Daten, muss im Dashboard-Deployer nichts extra gesetzt werden. Wenn du eine separate VictoriaMetrics fuer Audit-Daten nutzt, setze beim Dashboard-Deployment:

```env
GRAFANA_DS_VM_EVCC_AUDIT_UID=<datasource_uid>
```
