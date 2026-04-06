#!/usr/bin/env python3
"""Fetch and cache Victron VRM daily kWh stats locally for fast comparisons."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

UTC = dt.timezone.utc
SCRIPT_NAME = "fetch_vrm_kwh_cache.py"
SCRIPT_VERSION = "2026.04.06.1"
SCRIPT_LAST_MODIFIED = "2026-04-06"
ROOT = Path(__file__).resolve().parents[2]
ENV_LOCAL = ROOT / ".env.local"
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "vrm"
KWH_KEYS = ("Gc", "Bc", "Bg", "Gb", "Pc", "Pg", "Pb", "kwh")

KEY_DESCRIPTIONS = {
    "Gc": "grid_to_consumers_kwh",
    "Bc": "battery_to_consumers_kwh",
    "Bg": "battery_to_grid_kwh",
    "Gb": "grid_to_battery_kwh",
    "Pc": "pv_to_consumers_kwh",
    "Pg": "pv_to_grid_kwh",
    "Pb": "pv_to_battery_kwh",
    "kwh": "system_total_kwh",
}


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def local_timestamp() -> str:
    return local_now().replace(microsecond=0).isoformat()


def script_metadata() -> Dict[str, str]:
    return {
        "name": SCRIPT_NAME,
        "version": SCRIPT_VERSION,
        "last_modified": SCRIPT_LAST_MODIFIED,
        "generated_at": local_timestamp(),
    }


def load_env_local(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def parse_day(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def epoch_seconds_for_local_midnight(day: dt.date) -> int:
    return int(dt.datetime.combine(day, dt.time.min).astimezone().timestamp())


def fetch_vrm_stats(site_id: str, token: str, start_day: dt.date, end_day: dt.date) -> dict:
    start_epoch = epoch_seconds_for_local_midnight(start_day)
    end_epoch = epoch_seconds_for_local_midnight(end_day + dt.timedelta(days=1)) - 1
    params = urllib.parse.urlencode(
        {
            "type": "kwh",
            "interval": "days",
            "start": str(start_epoch),
            "end": str(end_epoch),
        }
    )
    url = f"https://vrmapi.victronenergy.com/v2/installations/{site_id}/stats?{params}"
    request = urllib.request.Request(url, headers={"x-authorization": f"Token {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_records(records: dict, start_day: dt.date, end_day: dt.date) -> List[dict]:
    total_days = (end_day - start_day).days + 1
    normalized: List[dict] = []
    for index in range(total_days):
        day = start_day + dt.timedelta(days=index)
        row = {
            "day": day.isoformat(),
            "pv_total_kwh": 0.0,
            "grid_import_total_kwh": 0.0,
            "battery_to_consumers_kwh": 0.0,
            "battery_to_grid_kwh": 0.0,
            "system_total_kwh": 0.0,
        }
        for key in KWH_KEYS:
            values = records.get(key, [])
            if index >= len(values):
                value = 0.0
            else:
                value = float(values[index][1])
            row[KEY_DESCRIPTIONS[key]] = value
        row["pv_total_kwh"] = (
            row["pv_to_consumers_kwh"]
            + row["pv_to_grid_kwh"]
            + row["pv_to_battery_kwh"]
        )
        row["grid_import_total_kwh"] = row["grid_to_consumers_kwh"] + row["grid_to_battery_kwh"]
        normalized.append(row)
    return normalized


def write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: List[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(rows[0].keys()) if rows else ["day"]
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def summarize(rows: List[dict]) -> dict:
    def total(key: str) -> float:
        return round(sum(float(row.get(key, 0.0)) for row in rows), 6)

    return {
        "days": len(rows),
        "pv_total_kwh": total("pv_total_kwh"),
        "grid_import_total_kwh": total("grid_import_total_kwh"),
        "grid_to_consumers_kwh": total("grid_to_consumers_kwh"),
        "grid_to_battery_kwh": total("grid_to_battery_kwh"),
        "battery_to_consumers_kwh": total("battery_to_consumers_kwh"),
        "pv_to_consumers_kwh": total("pv_to_consumers_kwh"),
        "pv_to_grid_kwh": total("pv_to_grid_kwh"),
        "pv_to_battery_kwh": total("pv_to_battery_kwh"),
    }


def main(argv: List[str] | None = None) -> int:
    load_env_local(ENV_LOCAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-id", default=os.environ.get("VRM_SITE_ID", ""), help="Victron VRM installation/site ID")
    parser.add_argument("--token", default=os.environ.get("VRM_API_TOKEN", ""), help="Victron VRM API token")
    parser.add_argument("--start-day", required=True, help="Local start day in YYYY-MM-DD")
    parser.add_argument("--end-day", required=True, help="Local end day in YYYY-MM-DD")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for cached output files")
    args = parser.parse_args(argv)

    if not args.site_id:
        raise SystemExit("Missing VRM site ID. Set VRM_SITE_ID in .env.local or pass --site-id.")
    if not args.token:
        raise SystemExit("Missing VRM API token. Set VRM_API_TOKEN in .env.local or pass --token.")

    start_day = parse_day(args.start_day)
    end_day = parse_day(args.end_day)
    if end_day < start_day:
        raise SystemExit("--end-day must be on or after --start-day")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"vrm-kwh-days-site-{args.site_id}-{start_day.isoformat()}_{end_day.isoformat()}"
    json_path = output_dir / f"{prefix}.json"
    csv_path = output_dir / f"{prefix}.csv"

    payload = fetch_vrm_stats(args.site_id, args.token, start_day, end_day)
    records = payload.get("records")
    if not payload.get("success") or not isinstance(records, dict):
        raise SystemExit(f"VRM API did not return day stats: {json.dumps(payload, ensure_ascii=True)}")

    rows = normalize_records(records, start_day, end_day)
    summary = summarize(rows)
    report = {
        "script": script_metadata(),
        "site_id": str(args.site_id),
        "start_day": start_day.isoformat(),
        "end_day": end_day.isoformat(),
        "output": {
            "json": str(json_path),
            "csv": str(csv_path),
        },
        "summary": summary,
        "rows": rows,
        "raw_totals": payload.get("totals", {}),
    }
    write_json(json_path, report)
    write_csv(csv_path, rows)

    print(f"VRM kWh cache written: {json_path}")
    print(f"CSV mirror written:   {csv_path}")
    print(json.dumps({"summary": summary, "site_id": str(args.site_id)}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())