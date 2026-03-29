#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Iterator

NUMERIC_TYPES = {"float", "integer", "unsigned", "boolean"}


def influx_get(url: str):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def influx_stream(url: str) -> Iterator[dict]:
    decoder = json.JSONDecoder()
    with urllib.request.urlopen(url, timeout=300) as resp:
        buf = ""
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while True:
                buf = buf.lstrip()
                if not buf:
                    break
                try:
                    obj, idx = decoder.raw_decode(buf)
                except json.JSONDecodeError:
                    break
                yield obj
                buf = buf[idx:]
        buf = buf.strip()
        if buf:
            obj, idx = decoder.raw_decode(buf)
            yield obj


def influx_query(base: str, db: str, q: str) -> dict:
    url = f"{base}/query?db={urllib.parse.quote(db)}&q={urllib.parse.quote(q)}"
    return influx_get(url)


def field_map(base: str, db: str, measurement: str) -> dict[str, str]:
    data = influx_query(base, db, f'SHOW FIELD KEYS FROM "{measurement}"')
    out = {}
    for result in data.get("results", []):
        for series in result.get("series", []):
            columns = series.get("columns", [])
            values = series.get("values", [])
            if columns[:2] != ["fieldKey", "fieldType"]:
                continue
            for field, ftype in values:
                out[str(field)] = str(ftype)
    return out


def measurements(base: str, db: str) -> list[str]:
    data = influx_query(base, db, 'SHOW MEASUREMENTS')
    out = []
    for result in data.get("results", []):
        for series in result.get("series", []):
            for row in series.get("values", []):
                out.append(str(row[0]))
    return out


def vm_import(base: str, rows: list[dict]):
    if not rows:
        return
    body = ("\n".join(json.dumps(row, separators=(",", ":"), ensure_ascii=True) for row in rows) + "\n").encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/v1/import",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        if resp.status != 204:
            raise RuntimeError(f"VM import failed: {resp.status} {resp.read().decode('utf-8', errors='replace')}")


def series_rows_from_chunk(obj: dict, ftypes: dict[str, str], measurement: str, db_label: str) -> list[dict]:
    rows = {}
    for result in obj.get("results", []):
        for series in result.get("series", []):
            tags = dict(series.get("tags", {}) or {})
            columns = series.get("columns", [])
            values = series.get("values", [])
            if not columns or not values or columns[0] != "time":
                continue
            field_indices = []
            for idx, col in enumerate(columns[1:], start=1):
                ftype = ftypes.get(col)
                if ftype in NUMERIC_TYPES:
                    field_indices.append((idx, col, ftype))
            if not field_indices:
                continue
            for value_row in values:
                ts = value_row[0]
                try:
                    timestamp = int(ts)
                except Exception:
                    continue
                for idx, field_name, ftype in field_indices:
                    raw = value_row[idx]
                    if raw is None:
                        continue
                    if ftype == "boolean":
                        numeric = 1.0 if bool(raw) else 0.0
                    else:
                        try:
                            numeric = float(raw)
                        except Exception:
                            continue
                    labels = {"__name__": f"{measurement}_{field_name}", "db": db_label}
                    for k, v in tags.items():
                        labels[str(k)] = str(v)
                    key = tuple(sorted(labels.items()))
                    bucket = rows.setdefault(key, {"metric": labels, "values": [], "timestamps": []})
                    bucket["values"].append(numeric)
                    bucket["timestamps"].append(timestamp // 1_000_000)
    return list(rows.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--influx-base', required=True)
    ap.add_argument('--vm-base', required=True)
    ap.add_argument('--db', default='evcc')
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--measurement')
    ap.add_argument('--chunk-size', type=int, default=5000)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    names = [args.measurement] if args.measurement else measurements(args.influx_base, args.db)
    summary = {"measurements": 0, "series": 0, "points": 0, "imported": 0}
    for idx, measurement in enumerate(names, start=1):
        ftypes = field_map(args.influx_base, args.db, measurement)
        if not any(ft in NUMERIC_TYPES for ft in ftypes.values()):
            continue
        q = f'SELECT * FROM "{measurement}" WHERE time >= \'{args.start}\' AND time < \'{args.end}\''
        url = (
            f"{args.influx_base}/query?db={urllib.parse.quote(args.db)}"
            f"&epoch=ns&chunked=true&chunk_size={args.chunk_size}&q={urllib.parse.quote(q)}"
        )
        summary["measurements"] += 1
        for obj in influx_stream(url):
            rows = series_rows_from_chunk(obj, ftypes, measurement, args.db)
            if not rows:
                continue
            summary["series"] += len(rows)
            summary["points"] += sum(len(r["values"]) for r in rows)
            if not args.dry_run:
                vm_import(args.vm_base, rows)
                summary["imported"] += len(rows)
        print(json.dumps({"measurement": measurement, "index": idx, "summary": summary}, ensure_ascii=True), file=sys.stderr)
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
