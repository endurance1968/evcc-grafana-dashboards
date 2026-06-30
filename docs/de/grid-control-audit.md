# EVCC Netzsteuerungs-Audit nach VictoriaMetrics

Englische Version: [grid-control-audit.md](../en/grid-control-audit.md).

Diese optionale Anleitung richtet den Zusatz-Collector fuer den Daily-Details-Tab `Netzsteuerung` ein. Der normale EVCC/Telegraf-Live-Ingest bleibt unveraendert und liefert weiterhin die normalen EVCC-Metriken. Der Audit-Collector liest EVCC nur lesend aus, schreibt zusaetzliche `evcc_audit_*`-Metriken nach VictoriaMetrics und fuehrt lokal eine kumulative CSV-Datei der erkannten Eingriffe.

Der Tab wird automatisch nur angezeigt, wenn in der konfigurierten Audit-Datasource `evcc_audit_*`-Metriken vorhanden sind. Normale EVCC-Netzmetriken reichen dafuer nicht aus. Ohne Collector/Audit-Metriken bleibt der Tab verborgen; sobald der Collector Werte oder GridSession-Ereignisse liefert, werden Limits, Reserven, steuerbare Gruppen und die Event-Tabelle gefuellt.

## Was der Collector schreibt

Der Collector fragt regelmaessig diese EVCC-Endpunkte ab:

- `/api/state`
- `/api/gridsessions`

Daraus entstehen im Normalbetrieb nur die zusaetzlichen Audit- und Event-Metriken, die nicht schon durch den normalen EVCC/Telegraf-Ingest abgedeckt sind:

- `evcc_audit_hems_effective_max_consumption_power_w`
- `evcc_audit_hems_effective_max_production_power_w`
- `evcc_audit_gridsession_event_start_timestamp_seconds`
- `evcc_audit_minimum_allowed_power_w`
- `evcc_audit_control_group_power_w`
- `evcc_audit_control_units`
- `evcc_audit_collector_up`
- `evcc_audit_collector_last_success_timestamp_seconds`

Netzleistung, Hausverbrauch, Speicherwerte und Ladepunkt-Rohwerte werden nicht nochmals dauerhaft als `evcc_audit_*`-Kopie geschrieben. Die Dashboards verwenden dafuer die normalen EVCC-Metriken wie `gridPower_value`; der Collector nutzt diese Werte nur intern fuer Berechnungen.


Zusaetzlich schreibt der Collector eine lokale CSV nach `AUDIT_DATA_DIR/events/evcc-grid-control-events.csv`. Diese Datei enthaelt je Eingriff unter anderem Start, Ende, Typ, Status, Limit, Netzleistung zum Start, Quelle des Eingriffs und bei EEBUS die SKI, falls EVCC diese Information liefert.

Die Grafana-Tabelle liest nicht direkt aus EVCC und nicht direkt aus der CSV. Der Pfad ist bewusst: EVCC-API -> Collector -> lokale CSV + VictoriaMetrics -> Grafana. Bei aktivierter lokaler CSV fuehrt der Collector die Datei als lokale Historie weiter und schreibt im normalen Betrieb neue oder geaenderte EVCC-Events sowie ein kurzes Rueckspielfenster aus der lokalen CSV als `evcc_audit_gridsession_event_*`-Metriken nach VictoriaMetrics. Das Standardfenster ist `EVENT_REPLAY_LOOKBACK_DAYS=8` und haelt die 7-Tage-Tabelle auch nach einem VictoriaMetrics-Neustart gefuellt, ohne bei jedem Poll die komplette Historie erneut zu importieren. Wenn VictoriaMetrics neu aufgebaut wurde oder Event-Metriken fehlen, kann die komplette CSV bewusst mit `REPLAY_EVENTS=true` beziehungsweise `--replay-events` erneut nach VictoriaMetrics gespielt werden.

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
sudo mkdir -p /opt/evcc-vm-tools
curl -fsSLo /tmp/collect-evcc-grid-control-audit.py "$BASE/scripts/helper/collect-evcc-grid-control-audit.py"
curl -fsSLo /tmp/evcc-grid-control-audit.env.example "$BASE/scripts/helper/evcc-grid-control-audit.env.example"
curl -fsSLo /tmp/evcc-grid-control-audit.service.example "$BASE/scripts/helper/evcc-grid-control-audit.service.example"

sudo install -m 0755 /tmp/collect-evcc-grid-control-audit.py /opt/evcc-vm-tools/collect-evcc-grid-control-audit.py
sudo install -m 0640 /tmp/evcc-grid-control-audit.env.example /etc/evcc-grid-control-audit.env
sudo install -m 0644 /tmp/evcc-grid-control-audit.service.example /etc/systemd/system/evcc-grid-control-audit.service
```

Konfiguration bearbeiten:

```bash
sudo nano /etc/evcc-grid-control-audit.env
```

Minimalbeispiel:

```env
EVCC_BASE_URL=http://evcc.local:7070
VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus
SITE_ID=home
EVCC_API_POLL_SECONDS=10
HTTP_TIMEOUT_SECONDS=10
AUDIT_DATA_DIR=/var/lib/evcc-grid-control-audit
LOCAL_EVENT_CSV=true
REPLAY_EVENTS=false
```

Wenn der Collector direkt auf dem VictoriaMetrics-Host laeuft, ist `VM_WRITE_URL=http://127.0.0.1:8428/api/v1/import/prometheus` normalerweise richtig. Die lokale CSV liegt dann standardmaessig unter `/var/lib/evcc-grid-control-audit/events/evcc-grid-control-events.csv`.

## Quelle der Steuerevents

Die Tabelle `EVCC-Steuerevents` zeigt die Quelle in dieser Reihenfolge:

1. Quelle aus dem EVCC-Event selbst, falls `/api/gridsessions` sie liefert
2. EVCC-HEMS-Konfiguration aus `/api/state`, zum Beispiel `hems.config.type=eebus`
3. optionaler Fallback aus `EVCC_14A_INTERVENTION_SOURCE`

Das Event-Label `type` aus EVCC bleibt dabei unveraendert und beschreibt weiterhin `production` oder `consumption`. Es ist nicht die technische Quelle. Wenn deine EVCC-Version die HEMS-Konfiguration nicht ueber `/api/state` liefert, setze den Fallback explizit:

```env
EVCC_14A_INTERVENTION_SOURCE=EEBUS
# Alternativen: Relay, HEMS, FNN
```

## Optional: steuerbare Gruppen benennen

`EVCC_14A_CONTROL_GROUPS` beschreibt ausschliesslich die Gruppen, die im Tab `Netzsteuerung` als steuerbar angezeigt werden sollen. Der Collector leitet daraus keine Gruppen automatisch aus EVCC-Namen ab. Wenn ein Ladepunkt oder eine Waermepumpe nicht steuerbar ist, nimm sie hier nicht auf.

Beispiel fuer zwei Ladepunkte als gemeinsame Gruppe, eine als EVCC-Ladepunkt gemessene Waermepumpe und Batterie-Netzladung:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Ladepunkte|loadpoints|Carport Ecke+Carport Treppe;wp1|Daikin-WP|heat_pump|Daikin-WP;battery|Batterie Netzladung|battery_grid_charge|
```

Syntax:

```text
id|Anzeigename|Typ|Mitglieder;id2|Anzeigename|Typ|Mitglieder2
```

Unterstuetzte Typen:

- `loadpoint` / `loadpoints`: Mitglieder sind sichtbare EVCC-Ladepunktnamen, zum Beispiel `Carport Ecke`, oder optional EVCC-Ladepunktnummern wie `1`. Mehrere Mitglieder werden mit `+` kombiniert.
- `heat_pump`: Mitglieder sind sichtbare EVCC-Ladepunktnamen fuer Waermepumpen, die in EVCC als Ladepunkt erscheinen
- `battery_grid_charge`: Mitglieder bleiben leer

Fuer die Mindestleistungsberechnung nutzt der Collector standardmaessig die Anzahl der konfigurierten Gruppen. Das ist nur eine technische Voreinstellung. Entscheidend ist, wie viele steuerbare Verbrauchseinrichtungen der Netzbetreiber beziehungsweise die Elektroinstallation tatsaechlich als steuerbar behandelt.

Wenn zwei Ladepunkte gemeinsam gesteuert werden und netzseitig als eine steuerbare Einheit gelten, konfiguriere sie als eine Gruppe und setze die Anzahl explizit auf `1`:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Ladepunkte|loadpoints|Carport Ecke+Carport Treppe
EVCC_14A_CONTROL_UNITS=1
```

Wenn dieselben zwei Ladepunkte als zwei separat steuerbare Verbrauchseinrichtungen gelten, kann die Anzeige trotzdem eine gemeinsame Gruppe bleiben; setze dann aber die rechtliche Anzahl auf `2`:

```env
EVCC_14A_CONTROL_GROUPS=wallboxes|Ladepunkte|loadpoints|Carport Ecke+Carport Treppe
EVCC_14A_CONTROL_UNITS=2
```

Der Mindestleistungswert wird aus deiner Konfiguration berechnet und ist kein rechtsverbindlicher Nachweis. Standard ist `EVCC_14A_MIN_POWER_MODE=ems`. Dabei nutzt der Collector die GZF-Tabelle fuer EMS-Steuerung: eine Einheit 4,2 kW, zwei Einheiten 7,56 kW, drei Einheiten 10,5 kW. Fuer direkte Einzelsteuerung kannst du `direct` setzen; dann rechnet der Collector 4,2 kW je Einheit. Wenn der Netzbetreiber oder Installateur einen konkreten Wert vorgibt, setze diesen direkt:

```env
EVCC_14A_MIN_POWER_MODE=ems
# Alternative: direct
# EVCC_14A_MIN_POWER_OVERRIDE_W=10500
```

## Einmaliger Test

Vor dem Service-Start kannst du einen Lauf ausfuehren:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-tools/collect-evcc-grid-control-audit.py \
  --evcc-url http://evcc.local:7070 \
  --vm-write-url http://127.0.0.1:8428/api/v1/import/prometheus \
  --site home \
  --once
```

Nur anzeigen, ohne nach VictoriaMetrics oder in die lokale CSV zu schreiben:

```bash
sudo /usr/bin/python3 /opt/evcc-vm-tools/collect-evcc-grid-control-audit.py \
  --evcc-url http://evcc.local:7070 \
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
