# Grafana auf Debian 13 installieren

Englische Version: [grafana-install-debian-13_EN.md](./grafana-install-debian-13_EN.md).

Pruefe vor den Kommandos zuerst die zentrale Uebersicht der Voraussetzungen: [system-requirements.md](./system-requirements.md).

Diese Anleitung beschreibt eine geradlinige Grafana-Installation auf einer Debian-13-VM oder einem Debian-13-LXC.

## Validierungsstatus

Aktueller Status:

- Grafana-APT-Repository-Setup: am 2026-05-29 auf blankem `debian:trixie` Docker getestet
- `grafana-enterprise`-Installation: getestet
- Grafana HTTP/API Health Check: bestaetigt
- VictoriaMetrics Datasource Plugin fuer diese Dashboards: getestet

Docker-Validierungshinweis:

Ein Standard-`debian:trixie` Docker-Container laeuft nicht mit `systemd`. In dieser Umgebung kann die Paketinstallation geprueft werden, aber `systemctl enable --now grafana-server` muss uebersprungen werden. Fuer den Release-Check vom 2026-05-29 wurde Grafana manuell mit denselben Debian-Paketpfaden wie in der Service-Datei gestartet; `/api/health` meldete `database: ok`.

Annahmen:

- Debian 13 laeuft bereits.
- Die Kommandos sind fuer einen Nutzer mit `sudo` geschrieben; wenn du als `root` angemeldet bist, lasse `sudo` weg.
- Grafana soll lokal per `systemd` laufen.
- Grafana verwendet spaeter VictoriaMetrics als Datasource.

Nicht enthalten:

- VictoriaMetrics selbst installieren
- Migration von InfluxDB zu VictoriaMetrics
- EVCC-Dashboards deployen

Dafuer weiter mit:

- [victoriametrics-install-debian-13.md](./victoriametrics-install-debian-13.md)
- [influx-to-vm-migration.md](./influx-to-vm-migration.md)
- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Empfohlener Installationspfad

Fuer Debian 13 ist das offizielle Grafana-APT-Repository der empfohlene Pfad.

Vorteile:

- einfache Updates ueber `apt`
- kein manuelles `.deb`-Handling
- sauberer `systemd`-Service

Offizielle Referenz:

- [Install Grafana on Debian or Ubuntu](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)

## Welche Edition?

Grafana dokumentiert aktuell:

- `grafana-enterprise` als Standardpaket
- `grafana` als OSS-Paket

Wichtig:

- `grafana-enterprise` kann ohne bezahlte Lizenz genutzt werden.
- Fuer normale EVCC-Setups ist das ueblicherweise in Ordnung.
- Wenn du explizit nur OSS willst, installiere stattdessen `grafana`.

Diese Anleitung nutzt:

- `grafana-enterprise`

## 1. Basispakete installieren

```bash
sudo apt update
sudo apt install -y apt-transport-https wget gnupg curl
```

## 2. Grafana-APT-Key hinzufuegen

```bash
sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc
```

## 3. Grafana-Repository hinzufuegen

Fuer stabile Releases:

```bash
echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
```

Danach Paketindex aktualisieren:

```bash
sudo apt update
```

## 4. Grafana installieren

Empfohlene Standardedition:

```bash
sudo apt install -y grafana-enterprise
```

Wenn du explizit das OSS-Paket willst:

```bash
sudo apt install -y grafana
```

## 5. VictoriaMetrics Datasource Plugin installieren

Die EVCC-Dashboards verwenden das VictoriaMetrics Datasource Plugin. Installiere es, bevor du die Datasource anlegst:

```bash
sudo grafana cli \
  --homepath=/usr/share/grafana \
  --pluginsDir /var/lib/grafana/plugins \
  plugins install victoriametrics-metrics-datasource
```

Die expliziten Flags `--homepath` und `--pluginsDir` sind fuer das Debian-Paketlayout wichtig. Ein schlichtes `grafana cli plugins install ...` kann scheitern, weil der gepackte Grafana-Homepath nicht gefunden wird.

Grafana nach Plugin-Installation oder Plugin-Update neu starten.

## 6. Grafana starten und aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now grafana-server
```

Status pruefen:

```bash
sudo systemctl status grafana-server
```

## 7. Installation pruefen

Lokaler Check:

```bash
curl -I http://127.0.0.1:3000
```

Browser:

- `http://<dein-host>:3000`

Eine frische Installation startet typischerweise mit:

- Benutzername: `admin`
- Passwort: `admin`

Grafana erzwingt beim ersten Login normalerweise eine Passwortaenderung.

## 8. Netzwerkzugriff pruefen

Wenn Grafana von einem anderen Host erreichbar sein soll:

- Port `3000` muss offen sein.

Pruefen:

```bash
ss -ltnp | grep 3000
```

Wenn du eine Firewall nutzt, erlaube Port `3000` auch dort.

## 9. Updates

Wenn Grafana aus dem APT-Repository installiert wurde, laufen Updates ueber `apt`:

```bash
sudo apt update
sudo apt upgrade
```

Nur Grafana aktualisieren:

```bash
sudo apt update
sudo apt install grafana-enterprise
```

oder fuer OSS:

```bash
sudo apt update
sudo apt install grafana
```

## 10. Fuer EVCC vorbereiten

Sobald Grafana laeuft, ist der normale naechste Schritt:

1. VictoriaMetrics-Datasource anlegen
2. Grafana Service-Account-Token erstellen
3. EVCC-Dashboards deployen

Weiter mit:

- [grafana-vm-dashboard-setup.md](./grafana-vm-dashboard-setup.md)

## Hinweise fuer LXC

In einem normalen Debian-LXC funktionieren dieselben Schritte meist unveraendert.

Wichtig:

- ausreichend RAM zuweisen
- Port `3000` vom Host oder Netzwerk erreichbar machen
- Zeit und Zeitzone im Container korrekt halten

Grafana braucht typischerweise mindestens etwa:

- 512 MB RAM empfohlen
- 1 CPU-Kern empfohlen

## Haeufige Probleme

- Repository-Key fehlt oder ist falsch installiert
- Port `3000` ist lokal offen, aber im Netzwerk blockiert
- Default-Passwort wurde noch nicht geaendert
- VictoriaMetrics-Datasource ist noch nicht angelegt
- spaeterer Dashboard-Deploy scheitert, weil kein Service-Account-Token existiert

## Quellen

- [Install Grafana on Debian or Ubuntu](https://grafana.com/docs/grafana/latest/setup-grafana/installation/debian/)
- [Grafana installation overview](https://grafana.com/docs/grafana/latest/setup-grafana/installation/)