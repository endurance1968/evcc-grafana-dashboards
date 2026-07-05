# Optionaler VRM-Batteriefluss-Import

Diese optionale Erweiterung importiert taegliche Batterieflusswerte aus dem Victron VRM Portal nach VictoriaMetrics. Sie ist nuetzlich, wenn die EVCC-Speicherwerte fuer Laden/Entladen nicht fein genug sind oder wenn du den Speicherwirkungsgrad mit VRM-Tageswerten gegenpruefen moechtest.

Der Import ersetzt keine EVCC-Rohdaten und keine normalen `evcc_*` Rollups. Er ergaenzt nur zusaetzliche Tagesmetriken fuer die Monatsansicht.

## Was importiert wird

Der Helper liest die VRM-kWh-Tagesstatistik und schreibt folgende Tagesmetriken:

- `evcc_vrm_pv_to_battery_daily_wh`
- `evcc_vrm_grid_to_battery_daily_wh`
- `evcc_vrm_battery_to_consumers_daily_wh`
- `evcc_vrm_battery_to_grid_daily_wh`
- `evcc_vrm_battery_charge_daily_wh`
- `evcc_vrm_battery_discharge_daily_wh`

Eine separate Verlustmetrik wird nicht geschrieben. Verluste ergeben sich aus `battery_charge - battery_discharge`.

## Installation

```bash
BASE="https://raw.githubusercontent.com/endurance1968/evcc-grafana-dashboards/main"
# Alternative Forgejo-Beispiel:
# BASE="http://<server:port>/<owner>/<repo>/raw/branch/main"

sudo mkdir -p /opt/evcc-vm-tools
curl -fsSLo /tmp/import-vrm-energy-flows.py "$BASE/scripts/helper/import-vrm-energy-flows.py"
sudo install -m 0755 /tmp/import-vrm-energy-flows.py /opt/evcc-vm-tools/import-vrm-energy-flows.py
```

## Historischen Backfill ausfuehren

Fuer den ersten Lauf kannst du die Werte ab 2025-01-01 importieren. Das Ende ist inklusive; fuer abgeschlossene Tage bietet sich gestern an.

```bash
sudo /usr/bin/python3 /opt/evcc-vm-tools/import-vrm-energy-flows.py \
  --site-id "<VRM_SITE_ID>" \
  --token "<VRM_API_TOKEN>" \
  --vm-base-url "http://127.0.0.1:8428" \
  --start-day 2025-01-01 \
  --end-day "$(date -d 'yesterday' +%F)" \
  --write --replace-range
```

## Taegliche Aktualisierung

Ein taeglicher Lauf reicht, weil die VRM-Werte Tageswerte sind. Der Lookback von sieben Tagen aktualisiert auch spaeter korrigierte VRM-Tageswerte.

```cron
25 6 * * * /usr/bin/python3 /opt/evcc-vm-tools/import-vrm-energy-flows.py --site-id "<VRM_SITE_ID>" --token "<VRM_API_TOKEN>" --vm-base-url "http://127.0.0.1:8428" --lookback-days 7 --write --replace-range >> /var/log/evcc-vm-vrm-energy.log 2>&1
```

## Dashboard

Wenn die Metriken vorhanden sind, zeigt das Monatsdashboard im Tab `Speicher` zusaetzlich:

- `VRM Speicherwirkungsgrad`: Laden, Entladen und Wirkungsgrad aus VRM-Flussdaten.
- `VRM Speicherfluesse`: PV zu Speicher, Netz zu Speicher, Speicher zu Verbrauchern und Speicher zu Netz.
