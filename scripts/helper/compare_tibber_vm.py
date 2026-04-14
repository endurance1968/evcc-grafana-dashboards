#!/usr/bin/env python3
"""Compare Tibber grid import consumption and cost against EVCC VM rollups.

This script is a local validation helper for the EVCC migration workflow. It
reads daily Tibber consumption/cost data from the Tibber GraphQL API and compares
it with the VictoriaMetrics rollup metrics used by the long-range dashboards:

- evcc_grid_import_daily_wh
- evcc_grid_import_cost_daily_eur

EVCC rollup samples are timestamped at the local day they represent. The script
maps the VM sample timestamp to its local date before comparing it to Tibber's
daily `from` date. Use --vm-day-offset-days only for diagnosing shifted data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

SCRIPT_NAME = "compare_tibber_vm.py"
SCRIPT_VERSION = "2026.04.14.3"
SCRIPT_LAST_MODIFIED = "2026-04-14"
TIBBER_GQL_URL = "https://api.tibber.com/v1-beta/gql"
UTC = dt.timezone.utc


@dataclass(frozen=True)
class DayValues:
    kwh: Optional[float] = None
    eur: Optional[float] = None


@dataclass(frozen=True)
class Row:
    day: dt.date
    tibber_kwh: Optional[float]
    vm_kwh: Optional[float]
    delta_kwh: Optional[float]
    tibber_eur: Optional[float]
    vm_eur: Optional[float]
    delta_eur: Optional[float]


def load_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def local_timestamp() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def parse_day(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; expected YYYY-MM-DD") from exc


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_json(url: str, *, method: str = "GET", headers: Optional[Mapping[str, str]] = None, body: Optional[bytes] = None) -> object:
    request = urllib.request.Request(url, method=method, headers=dict(headers or {}), data=body)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc
    return json.loads(payload or "{}")


def http_text(url: str) -> str:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


def tibber_query(token: str, query: str, variables: Optional[Mapping[str, object]] = None) -> Mapping[str, object]:
    payload = json.dumps({"query": query, "variables": dict(variables or {})}).encode("utf-8")
    data = http_json(
        TIBBER_GQL_URL,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        body=payload,
    )
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected Tibber response shape")
    if data.get("errors"):
        raise RuntimeError(f"Tibber API returned errors: {json.dumps(data['errors'], ensure_ascii=False)}")
    return data


def discover_tibber_home_id(token: str, *, quiet: bool = False) -> str:
    query = """
    query Homes {
      viewer {
        homes {
          id
          appNickname
          address { address1 postalCode city }
        }
      }
    }
    """
    data = tibber_query(token, query)
    homes = (((data.get("data") or {}).get("viewer") or {}).get("homes") or [])
    if len(homes) == 1:
        home = homes[0]
        if not quiet:
            print(f"Tibber home:          {home.get('appNickname') or '-'} ({home.get('address', {}).get('city') or '-'})")
        return str(home["id"])
    if not homes:
        raise RuntimeError("Tibber token returned no homes; set TIBBER_HOME_ID if this is unexpected")
    print("Multiple Tibber homes found; set --tibber-home-id or TIBBER_HOME_ID:")
    for home in homes:
        address = home.get("address") or {}
        print(f"- {home.get('id')}  {home.get('appNickname') or '-'}  {address.get('city') or '-'}")
    raise SystemExit(2)


def fetch_tibber_daily(
    token: str,
    home_id: str,
    start_day: dt.date,
    end_day: dt.date,
    page_size: int,
) -> Dict[dt.date, DayValues]:
    query = """
    query Consumption($homeId: ID!, $last: Int!, $before: String) {
      viewer {
        home(id: $homeId) {
          consumption(resolution: DAILY, last: $last, before: $before) {
            pageInfo {
              startCursor
              hasPreviousPage
            }
            nodes {
              from
              to
              consumption
              consumptionUnit
              cost
            }
          }
        }
      }
    }
    """
    out: Dict[dt.date, DayValues] = {}
    before: Optional[str] = None
    seen_cursors: set[str] = set()

    while True:
        data = tibber_query(token, query, {"homeId": home_id, "last": page_size, "before": before})
        consumption = (((data.get("data") or {}).get("viewer") or {}).get("home") or {}).get("consumption") or {}
        nodes = consumption.get("nodes") or []
        page_info = consumption.get("pageInfo") or {}
        oldest_day: Optional[dt.date] = None

        for node in nodes:
            from_value = str(node.get("from") or "")
            if not from_value:
                continue
            day = dt.datetime.fromisoformat(from_value).date()
            oldest_day = day if oldest_day is None else min(oldest_day, day)
            if start_day <= day <= end_day:
                unit = str(node.get("consumptionUnit") or "kWh")
                if unit.lower() != "kwh":
                    raise RuntimeError(f"Unexpected Tibber consumption unit for {day}: {unit}")
                out[day] = DayValues(kwh=to_float(node.get("consumption")), eur=to_float(node.get("cost")))

        if oldest_day is not None and oldest_day <= start_day:
            break
        if not page_info.get("hasPreviousPage"):
            break
        cursor = page_info.get("startCursor")
        if not cursor or cursor in seen_cursors:
            break
        seen_cursors.add(str(cursor))
        before = str(cursor)

    return out


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    result = float(value)
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def vm_export_url(base_url: str, matcher: str, start: dt.datetime, end: dt.datetime) -> str:
    params = [("match[]", matcher), ("start", iso_z(start)), ("end", iso_z(end))]
    return f"{base_url.rstrip('/')}/api/v1/export?{urllib.parse.urlencode(params)}"


def fetch_vm_daily_metric(
    base_url: str,
    metric: str,
    start_day: dt.date,
    end_day: dt.date,
    timezone: ZoneInfo,
    scale: float,
    day_offset_days: int,
) -> Dict[dt.date, float]:
    # Export a padded window. Old imports may have small timestamp offsets, so
    # filter after mapping the sample timestamp to the local business date.
    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=timezone) - dt.timedelta(days=1)
    end = dt.datetime.combine(end_day, dt.time.min, tzinfo=timezone) + dt.timedelta(days=3)
    text = http_text(vm_export_url(base_url, metric, start, end))
    out: Dict[dt.date, float] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        values = item.get("values") or []
        timestamps = item.get("timestamps") or []
        for raw_ts, raw_value in zip(timestamps, values):
            timestamp_ms = int(raw_ts)
            local_dt = dt.datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).astimezone(timezone)
            day = local_dt.date() + dt.timedelta(days=day_offset_days)
            if start_day <= day <= end_day:
                value = to_float(raw_value)
                if value is None:
                    continue
                # VM should have one sample per metric/day. If duplicates exist,
                # keep the latest export value by overwriting deterministically.
                out[day] = value / scale
    return out


def build_rows(start_day: dt.date, end_day: dt.date, tibber: Mapping[dt.date, DayValues], vm: Mapping[dt.date, DayValues]) -> List[Row]:
    rows: List[Row] = []
    current = start_day
    while current <= end_day:
        tibber_values = tibber.get(current, DayValues())
        vm_values = vm.get(current, DayValues())
        rows.append(
            Row(
                day=current,
                tibber_kwh=tibber_values.kwh,
                vm_kwh=vm_values.kwh,
                delta_kwh=delta(vm_values.kwh, tibber_values.kwh),
                tibber_eur=tibber_values.eur,
                vm_eur=vm_values.eur,
                delta_eur=delta(vm_values.eur, tibber_values.eur),
            )
        )
        current += dt.timedelta(days=1)
    return rows


def delta(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return left - right


def fmt(value: Optional[float], width: int, decimals: int) -> str:
    if value is None:
        return "-".rjust(width)
    return f"{value:.{decimals}f}".rjust(width)


def print_table(rows: Iterable[Row], *, title: str, monthly: bool = False) -> None:
    print(title)
    print("-" * len(title))
    print(
        f"{'Period' if monthly else 'Date':<10} "
        f"{'Tibber kWh':>11} {'VM kWh':>11} {'Delta kWh':>11} "
        f"{'Tibber EUR':>11} {'VM EUR':>11} {'Delta EUR':>11}"
    )
    for row in rows:
        label = row.day.isoformat()[:7] if monthly else row.day.isoformat()
        print(
            f"{label:<10} "
            f"{fmt(row.tibber_kwh, 11, 3)} {fmt(row.vm_kwh, 11, 3)} {fmt(row.delta_kwh, 11, 3)} "
            f"{fmt(row.tibber_eur, 11, 3)} {fmt(row.vm_eur, 11, 3)} {fmt(row.delta_eur, 11, 3)}"
        )
    print()


def monthly_rows(rows: Iterable[Row]) -> List[Row]:
    buckets: Dict[Tuple[int, int], List[Row]] = {}
    for row in rows:
        buckets.setdefault((row.day.year, row.day.month), []).append(row)
    out: List[Row] = []
    for (year, month), items in sorted(buckets.items()):
        out.append(
            Row(
                day=dt.date(year, month, 1),
                tibber_kwh=sum_optional(item.tibber_kwh for item in items),
                vm_kwh=sum_optional(item.vm_kwh for item in items),
                delta_kwh=sum_optional(item.delta_kwh for item in items),
                tibber_eur=sum_optional(item.tibber_eur for item in items),
                vm_eur=sum_optional(item.vm_eur for item in items),
                delta_eur=sum_optional(item.delta_eur for item in items),
            )
        )
    return out


def sum_optional(values: Iterable[Optional[float]]) -> Optional[float]:
    found = False
    total = 0.0
    for value in values:
        if value is None:
            continue
        found = True
        total += value
    return total if found else None


def max_abs(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [abs(value) for value in values if value is not None]
    return max(present) if present else None


def print_summary(rows: List[Row], monthly: List[Row], kwh_tolerance: float, eur_tolerance: float) -> int:
    missing_tibber = sum(1 for row in rows if row.tibber_kwh is None and row.tibber_eur is None)
    missing_vm = sum(1 for row in rows if row.vm_kwh is None and row.vm_eur is None)
    max_kwh = max_abs(row.delta_kwh for row in rows)
    max_eur = max_abs(row.delta_eur for row in rows)
    month_max_kwh = max_abs(row.delta_kwh for row in monthly)
    month_max_eur = max_abs(row.delta_eur for row in monthly)

    print("Summary")
    print("-------")
    print(f"- Daily rows:          {len(rows)}")
    print(f"- Missing Tibber days: {missing_tibber}")
    print(f"- Missing VM days:     {missing_vm}")
    print(f"- Max daily kWh delta: {fmt(max_kwh, 0, 3).strip() if max_kwh is not None else '-'}")
    print(f"- Max daily EUR delta: {fmt(max_eur, 0, 3).strip() if max_eur is not None else '-'}")
    print(f"- Max month kWh delta: {fmt(month_max_kwh, 0, 3).strip() if month_max_kwh is not None else '-'}")
    print(f"- Max month EUR delta: {fmt(month_max_eur, 0, 3).strip() if month_max_eur is not None else '-'}")

    problems = missing_tibber + missing_vm
    if max_kwh is not None and max_kwh > kwh_tolerance:
        problems += 1
    if max_eur is not None and max_eur > eur_tolerance:
        problems += 1

    print()
    print("Result")
    print("------")
    if problems:
        print("CHECK: Tibber and VM differ beyond the configured tolerance or data is missing.")
        return 1
    print("OK: Tibber and VM match within the configured tolerance.")
    return 0


def default_range(timezone: ZoneInfo, include_today: bool) -> Tuple[dt.date, dt.date]:
    today = dt.datetime.now(timezone).date()
    end_day = today if include_today else today - dt.timedelta(days=1)
    return dt.date(end_day.year, end_day.month, 1), end_day


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Tibber daily consumption/cost with EVCC VictoriaMetrics rollups.")
    parser.add_argument("--env-file", default=".env.local", help="Environment file with TIBBER_API_TOKEN and optional TIBBER_HOME_ID")
    parser.add_argument("--tibber-token", default="", help="Tibber API token; defaults to TIBBER_API_TOKEN")
    parser.add_argument("--tibber-home-id", default="", help="Tibber home id; defaults to TIBBER_HOME_ID or auto-detects a single home")
    parser.add_argument("--tibber-page-size", type=int, default=100, help="Tibber DAILY consumption page size")
    parser.add_argument("--vm-base-url", default="", help="VictoriaMetrics base URL; defaults to VM_BASE_URL or http://127.0.0.1:8428")
    parser.add_argument("--start-day", type=parse_day, help="First local day to compare, YYYY-MM-DD")
    parser.add_argument("--end-day", type=parse_day, help="Last local day to compare, YYYY-MM-DD")
    parser.add_argument("--include-today", action="store_true", help="Default range includes today instead of ending yesterday")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Local timezone used for Tibber and VM day mapping")
    parser.add_argument("--kwh-tolerance", type=float, default=0.25, help="Allowed max absolute daily kWh delta")
    parser.add_argument("--eur-tolerance", type=float, default=0.25, help="Allowed max absolute daily EUR delta")
    parser.add_argument("--vm-day-offset-days", type=int, default=0, help="Offset applied to VM sample local dates before comparing; default 0")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text tables")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)
    timezone = ZoneInfo(args.timezone)
    start_day, end_day = default_range(timezone, args.include_today)
    if args.start_day:
        start_day = args.start_day
    if args.end_day:
        end_day = args.end_day
    if end_day < start_day:
        raise SystemExit("--end-day must be on or after --start-day")

    token = args.tibber_token or os.environ.get("TIBBER_API_TOKEN", "")
    if not token:
        raise SystemExit("Missing Tibber token. Set TIBBER_API_TOKEN in .env.local or pass --tibber-token.")
    home_id = args.tibber_home_id or os.environ.get("TIBBER_HOME_ID", "") or discover_tibber_home_id(token, quiet=args.json)
    vm_base_url = args.vm_base_url or os.environ.get("VM_BASE_URL", "") or "http://127.0.0.1:8428"

    if not args.json:
        print("EVCC Tibber vs VM comparison")
        print("============================")
        print(f"Script:              {SCRIPT_NAME}")
        print(f"Version:             {SCRIPT_VERSION}")
        print(f"Last modified:       {SCRIPT_LAST_MODIFIED}")
        print(f"Run at:              {local_timestamp()}")
        print(f"Range:               {start_day} -> {end_day}")
        print(f"Timezone:            {args.timezone}")
        print(f"VM base URL:         {vm_base_url}")
        print(f"VM day mapping:      sample local date {args.vm_day_offset_days:+d} day(s)")
        print()

    tibber = fetch_tibber_daily(token, home_id, start_day, end_day, args.tibber_page_size)
    vm_kwh = fetch_vm_daily_metric(vm_base_url, "evcc_grid_import_daily_wh", start_day, end_day, timezone, 1000.0, args.vm_day_offset_days)
    vm_eur = fetch_vm_daily_metric(vm_base_url, "evcc_grid_import_cost_daily_eur", start_day, end_day, timezone, 1.0, args.vm_day_offset_days)
    vm = {day: DayValues(kwh=vm_kwh.get(day), eur=vm_eur.get(day)) for day in sorted(set(vm_kwh) | set(vm_eur))}
    rows = build_rows(start_day, end_day, tibber, vm)
    months = monthly_rows(rows)

    if args.json:
        print(json.dumps({
            "script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION, "last_modified": SCRIPT_LAST_MODIFIED},
            "range": {"start_day": start_day.isoformat(), "end_day": end_day.isoformat(), "timezone": args.timezone},
            "daily": [row.__dict__ | {"day": row.day.isoformat()} for row in rows],
            "monthly": [row.__dict__ | {"day": row.day.isoformat(), "period": row.day.isoformat()[:7]} for row in months],
        }, ensure_ascii=False, indent=2))
        return 0

    print_table(rows, title="Daily comparison")
    print_table(months, title="Monthly comparison", monthly=True)
    return print_summary(rows, months, args.kwh_tolerance, args.eur_tolerance)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

