# Archiv: VictoriaMetrics Aggregation Guide

Englische Originalfassung: [victoriametrics-aggregation-guide_EN.md](./victoriametrics-aggregation-guide_EN.md).

Dieses Dokument ist archiviert. Der aktuelle Aggregationspfad ist `evcc-vm-rollup.py`, dokumentiert in [../influx-to-vm-migration.md](../influx-to-vm-migration.md) und [../design/victoriametrics-rollup-design.md](../design/victoriametrics-rollup-design.md).

## Historischer Zweck

Der Guide beschrieb fruehe Ueberlegungen zur Aggregation von EVCC-Rohdaten in VictoriaMetrics. Ziel war, Langzeit-Dashboards schneller und stabiler zu machen.

## Heutiges Modell

- Rohdaten bleiben in VictoriaMetrics erhalten.
- `Today`-Dashboards lesen Rohdaten direkt.
- `Month`, `Year` und `All-time` verwenden taegliche `evcc_*` Rollups.
- Rollups werden idempotent mit `--replace-range` aktualisiert.

## Warum Rollups?

- weniger teure Langzeit-Queries
- stabilere Energie- und Kostenberechnung
- klare Trennung zwischen Rohdaten und Tageswerten
- bessere Validierbarkeit gegen externe Referenzen

## Aktuelle Dokumente

- [../design/victoriametrics-rollup-design.md](../design/victoriametrics-rollup-design.md)
- [../design/victoriametrics-schema-reference.md](../design/victoriametrics-schema-reference.md)
- [../migration-validation-notes.md](../migration-validation-notes.md)

Details aus der fruehen Entwurfsphase bleiben in der englischen Archivfassung erhalten.