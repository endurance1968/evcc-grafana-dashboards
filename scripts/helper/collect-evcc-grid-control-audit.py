#!/usr/bin/env python3
"""Collect EVCC grid-control audit metrics and write them to VictoriaMetrics.

This helper is intentionally standalone and uses only the Python standard library.
It polls EVCC read-only API endpoints and writes Prometheus text exposition data
into VictoriaMetrics /api/v1/import/prometheus.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_VERSION = "2026.06.20.3"
SCRIPT_LAST_MODIFIED = "2026-06-20"
DEFAULT_USER_AGENT = f"evcc-vm-grid-control-audit/{SCRIPT_VERSION}"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bool_to_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return 1
        if lowered in {"false", "0", "no", "off"}:
            return 0
    return None


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def non_empty_string(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def first_non_empty_string(*values: Any) -> str:
    for value in values:
        parsed = non_empty_string(value)
        if parsed:
            return parsed
    return ""


def nested_string(data: dict[str, Any], *parts: str) -> str:
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return non_empty_string(current)


def get_path(data: dict[str, Any], *parts: str) -> Any:
    current: Any = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def metric(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        label_text = ",".join(f'{key}="{label_value(str(val))}"' for key, val in sorted(labels.items()))
        return f"{name}{{{label_text}}} {value}"
    return f"{name} {value}"


def parse_iso_timestamp_seconds(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def format_event_minute(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return value.strip().replace("T", " ")[:16]
    return parsed.strftime("%Y-%m-%d %H:%M")


@dataclass(frozen=True)
class ControlGroup:
    group_id: str
    name: str
    kind: str
    loadpoints: tuple[int, ...] = ()


LOADPOINT_CONTROL_GROUP_KINDS = {"loadpoint", "loadpoints", "heat_pump", "heat_pumps"}


def normalize_control_group_kind(kind: str) -> str:
    normalized = kind.strip().lower().replace("-", "_")
    aliases = {
        "heatpump": "heat_pump",
        "heatpumps": "heat_pump",
    }
    return aliases.get(normalized, normalized)


def parse_control_groups(value: str) -> tuple[ControlGroup, ...]:
    """Parse env syntax: id|name|kind|members;id2|name2|kind2|members2."""
    groups: list[ControlGroup] = []
    for raw_group in value.split(";"):
        raw_group = raw_group.strip()
        if not raw_group:
            continue
        parts = [part.strip() for part in raw_group.split("|", 3)]
        if len(parts) != 4:
            raise ValueError(f"Invalid control group syntax: {raw_group!r}")
        group_id, name, kind, members = parts
        normalized_kind = normalize_control_group_kind(kind)
        if normalized_kind in LOADPOINT_CONTROL_GROUP_KINDS:
            loadpoints = tuple(int(part.strip()) for part in members.replace(",", "+").split("+") if part.strip())
            if not loadpoints:
                raise ValueError(f"Control group {group_id!r} with kind {kind!r} needs at least one loadpoint member")
        elif normalized_kind == "battery_grid_charge":
            loadpoints = ()
        else:
            raise ValueError(f"Unsupported control group kind: {kind!r}")
        groups.append(ControlGroup(group_id=group_id, name=name, kind=normalized_kind, loadpoints=loadpoints))
    return tuple(groups)


def minimum_allowed_power_w(unit_count: int, base_w: float = 4200.0, additional_factor: float = 0.4) -> float:
    if unit_count <= 0:
        return 0.0
    return base_w + max(unit_count - 1, 0) * additional_factor * base_w


def http_get_json(url: str, timeout: float, user_agent: str) -> Any:
    req = Request(url, headers={"User-Agent": user_agent})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_prometheus_metrics(write_url: str, lines: list[str], timeout: float, dry_run: bool = False) -> None:
    if not lines:
        return
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    if dry_run:
        sys.stdout.write(payload.decode("utf-8"))
        return
    req = Request(write_url, data=payload, method="POST")
    req.add_header("Content-Type", "text/plain; version=0.0.4")
    req.add_header("User-Agent", DEFAULT_USER_AGENT)
    with urlopen(req, timeout=timeout) as response:
        response.read()


CSV_EVENT_FIELDS = [
    "event_id",
    "site_id",
    "start_time_utc",
    "end_time_utc",
    "type",
    "status",
    "limit_w",
    "grid_power_start_w",
    "intervention_source",
    "source_ski",
    "source",
    "first_seen_utc",
    "last_seen_utc",
]


def event_id(session: dict[str, Any]) -> str:
    raw = "|".join(
        str(
            first_present(
                session.get(key),
                session.get(key.lower()),
                session.get(key.replace("_", "")),
            )
            or ""
        )
        for key in ["created", "type", "limit", "source", "ski"]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def detect_intervention_source(session: dict[str, Any]) -> str:
    candidate = first_non_empty_string(
        session.get("source"),
        session.get("origin"),
        session.get("provider"),
        session.get("trigger"),
        session.get("actor"),
        session.get("controlSource"),
        session.get("control_source"),
        nested_string(session, "source", "type"),
        nested_string(session, "origin", "type"),
        session.get("type"),
    )
    lowered = candidate.lower()
    if "eebus" in lowered:
        return "EEBUS"
    if "relay" in lowered or "relais" in lowered:
        return "Relay"
    if candidate:
        return candidate
    return "EVCC"


def detect_source_ski(session: dict[str, Any]) -> str:
    return first_non_empty_string(
        session.get("ski"),
        session.get("sourceSki"),
        session.get("source_ski"),
        session.get("remoteSki"),
        session.get("remote_ski"),
        session.get("deviceSki"),
        session.get("device_ski"),
        session.get("entitySki"),
        session.get("entity_ski"),
        nested_string(session, "eebus", "ski"),
        nested_string(session, "source", "ski"),
        nested_string(session, "origin", "ski"),
    )


def normalize_sessions(sessions: Any, site_id: str, seen_at_utc: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(sessions, list):
        return []
    seen_at = seen_at_utc or iso_now()
    normalized: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        start = session.get("created")
        if not start:
            continue
        end = session.get("finished") or ""
        normalized.append(
            {
                "event_id": event_id(session),
                "site_id": site_id,
                "start_time_utc": start,
                "end_time_utc": end,
                "type": session.get("type", ""),
                "limit_w": session.get("limit", ""),
                "grid_power_start_w": session.get("grid", ""),
                "intervention_source": detect_intervention_source(session),
                "source_ski": detect_source_ski(session),
                "source": "evcc_gridsessions",
                "first_seen_utc": seen_at,
                "last_seen_utc": seen_at,
                "status": "finished" if end else "active",
            }
        )
    return normalized


def build_event_metrics(events: list[dict[str, Any]], site_id: str) -> list[str]:
    lines: list[str] = []
    for event in events:
        start_timestamp = parse_iso_timestamp_seconds(event.get("start_time_utc"))
        if start_timestamp is None:
            continue
        event_labels = {
            "site": site_id,
            "source": "evcc_gridsessions",
            "event_id": str(event.get("event_id", "")),
            "start": format_event_minute(event.get("start_time_utc")),
            "end": format_event_minute(event.get("end_time_utc")),
            "type": str(event.get("type", "")),
            "status": str(event.get("status", "")),
            "limit_w": str(event.get("limit_w", "")),
            "grid_power_start_w": str(event.get("grid_power_start_w", "")),
            "intervention_source": str(event.get("intervention_source", "")),
            "source_ski": str(event.get("source_ski", "")),
        }
        lines.append(metric("evcc_audit_gridsession_event_start_timestamp_seconds", start_timestamp, event_labels))
    return lines


def build_state_metrics(
    state: dict[str, Any],
    site_id: str,
    control_groups: tuple[ControlGroup, ...] = (),
    control_unit_count: int | None = None,
    minimum_base_w: float = 4200.0,
    additional_unit_factor: float = 0.4,
) -> list[str]:
    labels = {"site": site_id}
    lines: list[str] = [metric("evcc_audit_collector_up", 1, labels)]

    site = state.get("site") if isinstance(state.get("site"), dict) else {}
    grid_power = first_present(
        get_path(site, "grid", "power"),
        site.get("gridPower"),
        get_path(state, "grid", "power"),
        state.get("gridPower"),
    )
    home_power = first_present(site.get("homePower"), state.get("homePower"))
    grid_import_power: float | None = None
    grid_export_power: float | None = None

    grid_power_parsed = number(grid_power)
    if grid_power_parsed is not None:
        grid_import_power = max(grid_power_parsed, 0.0)
        grid_export_power = max(-grid_power_parsed, 0.0)
        lines.append(metric("evcc_audit_site_grid_power_w", grid_power_parsed, labels))
        lines.append(metric("evcc_audit_site_grid_import_power_w", grid_import_power, labels))
        lines.append(metric("evcc_audit_site_grid_export_power_w", grid_export_power, labels))

    home_power_parsed = number(home_power)
    if home_power_parsed is not None:
        lines.append(metric("evcc_audit_site_home_power_w", home_power_parsed, labels))

    battery_grid_charge = first_present(site.get("batteryGridChargeActive"), state.get("batteryGridChargeActive"))
    battery_grid_charge_active = bool_to_number(battery_grid_charge)
    battery_power_value: float | None = None
    if battery_grid_charge_active is not None:
        lines.append(metric("evcc_audit_battery_grid_charge_active", battery_grid_charge_active, labels))

    battery = state.get("battery") if isinstance(state.get("battery"), dict) else {}
    battery_power_value = number(first_present(battery.get("power"), state.get("batteryPower")))
    if battery_power_value is not None:
        lines.append(metric("evcc_audit_battery_power_w", battery_power_value, labels))
    battery_soc_value = number(first_present(battery.get("soc"), state.get("batterySoc")))
    if battery_soc_value is not None:
        lines.append(metric("evcc_audit_battery_soc_percent", battery_soc_value, labels))

    hems_status = get_path(state, "hems", "status") or {}
    hems_dimmed = bool_to_number(hems_status.get("dimmed"))
    hems_curtailed = bool_to_number(hems_status.get("curtailed"))
    if hems_dimmed is not None:
        lines.append(metric("evcc_audit_hems_dimmed", hems_dimmed, labels))
    if hems_curtailed is not None:
        lines.append(metric("evcc_audit_hems_curtailed", hems_curtailed, labels))

    max_consumption_power = number(hems_status.get("maxConsumptionPower"))
    max_production_power = number(hems_status.get("maxProductionPower"))
    if max_consumption_power is not None:
        lines.append(metric("evcc_audit_hems_max_consumption_power_w", max_consumption_power, labels))
    if max_production_power is not None:
        lines.append(metric("evcc_audit_hems_max_production_power_w", max_production_power, labels))

    has_explicit_hems_state = hems_dimmed is not None or hems_curtailed is not None
    consumption_limit_active = hems_dimmed == 1 or (
        not has_explicit_hems_state and max_consumption_power is not None and max_consumption_power > 0
    )
    hems_signal_active = hems_dimmed == 1 or hems_curtailed == 1
    production_limit_active = max_production_power is not None and max_production_power != 0 and (
        hems_signal_active or not has_explicit_hems_state
    )
    effective_max_consumption_power = max_consumption_power if consumption_limit_active and max_consumption_power is not None else 0.0
    effective_max_production_power = abs(max_production_power) if production_limit_active and max_production_power is not None else 0.0
    lines.append(metric("evcc_audit_vnb_signal_active", 1 if consumption_limit_active or production_limit_active else 0, labels))
    lines.append(metric("evcc_audit_hems_effective_max_consumption_power_w", effective_max_consumption_power, labels))
    lines.append(metric("evcc_audit_hems_effective_max_production_power_w", effective_max_production_power, labels))
    if grid_import_power is not None:
        lines.append(metric("evcc_audit_vnb_consumption_margin_w", effective_max_consumption_power - grid_import_power, labels))
    if grid_export_power is not None:
        lines.append(metric("evcc_audit_vnb_production_margin_w", effective_max_production_power - grid_export_power, labels))

    loadpoint_powers: dict[int, float] = {}
    loadpoints = state.get("loadpoints") if isinstance(state.get("loadpoints"), list) else []
    for index, loadpoint in enumerate(loadpoints, start=1):
        if not isinstance(loadpoint, dict):
            continue
        lp_name = str(loadpoint.get("title") or loadpoint.get("name") or index)
        charge_power = number(loadpoint.get("chargePower"))
        if charge_power is not None:
            loadpoint_powers[index] = charge_power
        lp_labels = {"site": site_id, "loadpoint": str(index), "name": lp_name}
        for field, name in [
            ("chargePower", "evcc_audit_loadpoint_charge_power_w"),
            ("offeredCurrent", "evcc_audit_loadpoint_offered_current_a"),
            ("effectiveMaxCurrent", "evcc_audit_loadpoint_effective_max_current_a"),
            ("phasesActive", "evcc_audit_loadpoint_phases_active"),
        ]:
            parsed = number(loadpoint.get(field))
            if parsed is not None:
                lines.append(metric(name, parsed, lp_labels))
        for field, name in [
            ("enabled", "evcc_audit_loadpoint_enabled"),
            ("charging", "evcc_audit_loadpoint_charging"),
            ("connected", "evcc_audit_loadpoint_connected"),
        ]:
            parsed = bool_to_number(loadpoint.get(field))
            if parsed is not None:
                lines.append(metric(name, parsed, lp_labels))

    for group in control_groups:
        group_labels = {"site": site_id, "group": group.group_id, "name": group.name, "kind": group.kind}
        if group.kind in LOADPOINT_CONTROL_GROUP_KINDS:
            values = [loadpoint_powers[index] for index in group.loadpoints if index in loadpoint_powers]
            if values:
                lines.append(metric("evcc_audit_control_group_power_w", sum(values), group_labels))
        elif group.kind == "battery_grid_charge":
            if battery_grid_charge_active == 1 and battery_power_value is not None:
                lines.append(metric("evcc_audit_control_group_power_w", abs(battery_power_value), group_labels))
            else:
                lines.append(metric("evcc_audit_control_group_power_w", 0, group_labels))

    effective_unit_count = control_unit_count if control_unit_count is not None else len(control_groups)
    if effective_unit_count > 0:
        minimum_power = minimum_allowed_power_w(effective_unit_count, minimum_base_w, additional_unit_factor)
        lines.append(metric("evcc_audit_control_units", effective_unit_count, labels))
        lines.append(metric("evcc_audit_minimum_allowed_power_w", minimum_power, labels))
        if grid_import_power is not None:
            lines.append(metric("evcc_audit_calculated_minimum_margin_w", minimum_power - grid_import_power, labels))

    return lines


def read_existing_events(csv_path: Path) -> dict[str, dict[str, str]]:
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        events: dict[str, dict[str, str]] = {}
        for row in reader:
            event_key = row.get("event_id", "").strip()
            if event_key:
                events[event_key] = {field: row.get(field, "") for field in CSV_EVENT_FIELDS}
        return events


def write_events_csv(audit_dir: str, events: list[dict[str, Any]]) -> Path | None:
    if not events:
        return None
    csv_path = Path(audit_dir) / "events" / "evcc-grid-control-events.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_existing_events(csv_path)
    for event in events:
        event_key = str(event.get("event_id", "")).strip()
        if not event_key:
            continue
        current = existing.get(event_key, {field: "" for field in CSV_EVENT_FIELDS})
        first_seen = current.get("first_seen_utc") or str(event.get("first_seen_utc", ""))
        for field in CSV_EVENT_FIELDS:
            value = event.get(field, "")
            if value != "":
                current[field] = str(value)
        current["first_seen_utc"] = first_seen
        current["last_seen_utc"] = str(event.get("last_seen_utc") or current.get("last_seen_utc") or iso_now())
        existing[event_key] = current

    tmp_path = csv_path.with_suffix(".csv.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_EVENT_FIELDS)
        writer.writeheader()
        for event in sorted(existing.values(), key=lambda row: (row.get("start_time_utc", ""), row.get("event_id", ""))):
            writer.writerow(event)
    os.replace(tmp_path, csv_path)
    return csv_path


def collect_once(args: argparse.Namespace) -> list[str]:
    state_url = f"{args.evcc_url.rstrip('/')}/api/state"
    sessions_url = f"{args.evcc_url.rstrip('/')}/api/gridsessions"
    control_groups = parse_control_groups(args.control_groups)
    state = http_get_json(state_url, args.timeout, args.user_agent)
    if not isinstance(state, dict):
        raise RuntimeError("EVCC /api/state did not return an object")
    lines = build_state_metrics(
        state,
        args.site,
        control_groups=control_groups,
        control_unit_count=args.control_units,
        minimum_base_w=args.minimum_base_w,
        additional_unit_factor=args.additional_unit_factor,
    )
    lines.append(metric("evcc_audit_collector_last_success_timestamp_seconds", int(time.time()), {"site": args.site, "source": "evcc_state"}))

    sessions = http_get_json(sessions_url, args.timeout, args.user_agent)
    events = normalize_sessions(sessions, args.site)
    if args.local_csv and not args.dry_run:
        write_events_csv(args.audit_dir, events)
    lines.extend(build_event_metrics(events, args.site))
    return lines


def write_failure_metric(args: argparse.Namespace, message: str) -> None:
    labels = {"site": args.site, "error": message[:120]}
    try:
        post_prometheus_metrics(args.vm_write_url, [metric("evcc_audit_collector_up", 0, labels)], args.timeout, args.dry_run)
    except Exception:
        pass


def parse_optional_int(value: str) -> int | None:
    if not value:
        return None
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect EVCC grid-control audit metrics for VictoriaMetrics.")
    parser.add_argument("--evcc-url", default=env("EVCC_BASE_URL"), help="EVCC base URL, for example http://evcc:7070")
    parser.add_argument("--vm-write-url", default=env("VM_WRITE_URL", "http://127.0.0.1:8428/api/v1/import/prometheus"), help="VictoriaMetrics Prometheus import URL")
    parser.add_argument("--site", default=env("SITE_ID", "home"), help="site label for generated metrics")
    parser.add_argument("--poll-seconds", type=int, default=int(env("EVCC_API_POLL_SECONDS", "10")), help="poll interval in service mode")
    parser.add_argument("--timeout", type=float, default=float(env("HTTP_TIMEOUT_SECONDS", "10")), help="HTTP timeout in seconds")
    parser.add_argument("--control-groups", default=env("EVCC_14A_CONTROL_GROUPS"), help="optional control groups: id|name|kind|members;...")
    parser.add_argument("--control-units", type=parse_optional_int, default=parse_optional_int(env("EVCC_14A_CONTROL_UNITS")), help="override number of controllable units for minimum power calculation")
    parser.add_argument("--minimum-base-w", type=float, default=float(env("EVCC_14A_MIN_POWER_BASE_W", "4200")), help="minimum allowed power for one unit")
    parser.add_argument("--additional-unit-factor", type=float, default=float(env("EVCC_14A_ADDITIONAL_UNIT_FACTOR", "0.4")), help="additional unit factor for minimum allowed power")
    parser.add_argument("--user-agent", default=env("HTTP_USER_AGENT", DEFAULT_USER_AGENT), help="HTTP User-Agent")
    parser.add_argument("--audit-dir", default=env("AUDIT_DATA_DIR", "/var/lib/evcc-grid-control-audit"), help="local directory for the cumulative intervention CSV")
    parser.add_argument("--no-local-csv", dest="local_csv", action="store_false", default=env("LOCAL_EVENT_CSV", "true").lower() not in {"0", "false", "no", "off"}, help="disable the local cumulative intervention CSV")
    parser.add_argument("--once", action="store_true", default=env("RUN_ONCE", "false").lower() in {"1", "true", "yes", "on"}, help="run one collector cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="print Prometheus metrics instead of writing to VictoriaMetrics or local CSV")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"collect-evcc-grid-control-audit.py v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED})")
        return 0
    if not args.evcc_url:
        parser.error("--evcc-url or EVCC_BASE_URL is required")
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")

    print(f"collect-evcc-grid-control-audit.py v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED})", flush=True)
    while True:
        try:
            lines = collect_once(args)
            post_prometheus_metrics(args.vm_write_url, lines, args.timeout, args.dry_run)
            print(f"{iso_now()} collector cycle completed: {len(lines)} metric lines", flush=True)
        except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError, OSError) as exc:
            message = str(exc)
            print(f"{iso_now()} collector cycle failed: {message}", file=sys.stderr, flush=True)
            write_failure_metric(args, message)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
