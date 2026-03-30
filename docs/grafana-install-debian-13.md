# Grafana auf Debian 13 installieren

Diese Anleitung beschreibt die Installation von Grafana auf einer Debian-13-VM oder einem Debian-13-LXC.

Annahmen:

- Debian 13 läuft bereits
- du willst Grafana lokal per `systemd` betreiben
- Grafana soll später mit VictoriaMetrics als Datasource genutzt werden

Nicht Bestandteil dieser Anleitung:

- Installation von VictoriaMetrics selbst
- Migration von InfluxDB nach VictoriaMetrics
- Deployment der EVCC-Dashboards

Dafür gibt es bereits eigene Anleitungen:

- VictoriaMetrics installieren:
  - `victoriametrics-install-debian-13.md`
- InfluxDB -> VictoriaMetrics Migration:
  - `influx-to-vm-migration.md`
- Grafana mit VictoriaMetrics verbinden und EVCC-Dashboards deployen:
  - `grafana-vm-dashboard-setup.md`

## Empfohlener Installationsweg

Für Debian 13 ist der empfohlene Weg laut offizieller Grafana-Doku:

- Installation über das offizielle Grafana-APT-Repository

Vorteile:

- einfache Updates über `apt`
- kein manuelles `.deb`-Handling
- sauberer `systemd`-Service

Offizielle Quelle:

- [Grafana auf Debian oder Ubuntu installieren](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)

## Welche Edition?

Grafana dokumentiert aktuell:

- `grafana-enterprise` als empfohlene Standard-Edition
- `grafana` als OSS-Paket

Wichtig:

- `grafana-enterprise` ist ohne Lizenz kostenlos nutzbar
- funktional ist das für normale Setups meist unkritisch
- wenn du bewusst OSS-only willst, installiere stattdessen `grafana`

Diese Anleitung nutzt standardmäßig:

- `grafana-enterprise`

## Schritt 1: Basis-Pakete installieren

```bash
sudo apt update
sudo apt install -y apt-transport-https wget gnupg
```

## Schritt 2: Grafana-APT-Key einrichten

```bash
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
```

## Schritt 3: Grafana-Repository einbinden

Für stabile Releases:

```bash
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
```

Danach Paketliste aktualisieren:

```bash
sudo apt update
```

## Schritt 4: Grafana installieren

Empfohlene Standard-Edition:

```bash
sudo apt install -y grafana-enterprise
```

Falls du bewusst die OSS-Variante willst:

```bash
sudo apt install -y grafana
```

## Schritt 5: Grafana starten und aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now grafana-server
```

Status prüfen:

```bash
sudo systemctl status grafana-server
```

## Schritt 6: Funktion prüfen

Lokal testen:

```bash
curl -I http://127.0.0.1:3000
```

Im Browser:

- `http://<dein-host>:3000`

Standard-Login bei einer frischen Installation ist typischerweise:

- Benutzer: `admin`
- Passwort: `admin`

Beim ersten Login verlangt Grafana normalerweise direkt ein neues Passwort.

## Schritt 7: Netzwerkzugriff prüfen

Wenn Grafana von einem anderen Host erreichbar sein soll:

- Port `3000` muss erreichbar sein

Prüfen:

```bash
ss -ltnp | grep 3000
```

Wenn eine Firewall aktiv ist, muss Port `3000` dort zusätzlich freigeschaltet werden.

## Schritt 8: Updates

Wenn Grafana über das APT-Repository installiert wurde, laufen Updates normal über `apt`:

```bash
sudo apt update
sudo apt upgrade
```

Nur Grafana aktualisieren:

```bash
sudo apt update
sudo apt install grafana-enterprise
```

oder bei OSS:

```bash
sudo apt update
sudo apt install grafana
```

## Schritt 9: Für EVCC vorbereiten

Wenn Grafana läuft, ist der nächste Schritt normalerweise:

1. VictoriaMetrics als Datasource anlegen
2. Grafana Service-Account-Token erzeugen
3. EVCC-Dashboards deployen

Dafür weiter mit:

- `grafana-vm-dashboard-setup.md`

## Hinweise für LXC

Für einen normalen Debian-LXC gelten in der Regel dieselben Schritte wie für eine VM.

Wichtig ist vor allem:

- genügend RAM bereitstellen
- Port `3000` vom Host bzw. Netzwerk erreichbar machen
- Uhrzeit und Zeitzone im Container sauber halten

Grafana selbst braucht laut offizieller Doku mindestens ungefähr:

- 512 MB RAM empfohlen
- 1 CPU-Kern empfohlen

Quelle:

- [Grafana Installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)

## Typische Stolperfallen

- Repository-Key fehlt oder ist falsch eingebunden
- Port `3000` lokal offen, aber im Netzwerk blockiert
- Standardpasswort wurde noch nicht geändert
- VictoriaMetrics-Datasource ist noch nicht angelegt
- späterer Dashboard-Deploy scheitert wegen fehlendem Service-Account-Token

## Quellen

- [Grafana auf Debian oder Ubuntu installieren](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)
- [Grafana Installation allgemein](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)

