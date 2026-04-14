#!/usr/bin/env python3
"""Run an optional end-to-end rollup test against a disposable VictoriaMetrics."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_NAME = "rollup-e2e.py"
SCRIPT_VERSION = "2026.04.14.2"
SCRIPT_LAST_MODIFIED = "2026-04-14"

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLUP_SCRIPT = REPO_ROOT / "scripts" / "rollup" / "evcc-vm-rollup.py"
FIXTURE_LABEL = "evcc_rollup_e2e"
ROLLUP_PREFIX = "e2e_evcc"
DEFAULT_DOCKER_IMAGE = "victoriametrics/victoria-metrics:v1.110.0"
DEFAULT_DOCKER_PORT = 18428


@dataclass(frozen=True)
class Series:
    metric: dict[str, str]
    values: list[float]
    timestamps: list[int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a real EVCC rollup read/write/replace test against a disposable VictoriaMetrics. "
            "Use --docker for an isolated local container, or --base-url with --confirm-disposable."
        )
    )
    parser.add_argument("--docker", action="store_true", help="Start a temporary VictoriaMetrics Docker container.")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE, help="VictoriaMetrics Docker image to run.")
    parser.add_argument("--docker-port", type=int, default=DEFAULT_DOCKER_PORT, help="Host port for --docker mode.")
    parser.add_argument("--keep-docker", action="store_true", help="Do not stop the Docker container after the test.")
    parser.add_argument("--base-url", default=os.environ.get("ROLLUP_E2E_VM_URL", ""), help="Disposable VM base URL.")
    parser.add_argument(
        "--confirm-disposable",
        action="store_true",
        help="Required when --base-url is used; confirms the target may be modified and cleaned.",
    )
    parser.add_argument("--start-day", default="2026-02-01", help="Fixture month start day; must be first day of month.")
    parser.add_argument("--end-day", default="2026-02-28", help="Fixture month end day; must be full historical month.")
    parser.add_argument("--timezone", default="Europe/Berlin", help="Local timezone used by rollup.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON summary.")
    return parser.parse_args()


def log(message: str, *, json_mode: bool) -> None:
    if not json_mode:
        print(message, flush=True)


def is_local_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname or ""
    return host in {"127.0.0.1", "localhost", "::1"}


def wait_for_vm(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=2) as response:
                if 200 <= response.status < 300:
                    return
        except Exception as exc:  # noqa: BLE001 - report the last connection problem.
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"VictoriaMetrics did not become healthy at {base_url}: {last_error}")


def wait_for_port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} is already in use; pass --docker-port with a free port.")


def start_docker_vm(args: argparse.Namespace, json_mode: bool) -> tuple[str, str]:
    wait_for_port_free(args.docker_port)
    name = f"evcc-rollup-e2e-{os.getpid()}"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "-p",
        f"127.0.0.1:{args.docker_port}:8428",
        args.docker_image,
    ]
    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    base_url = f"http://127.0.0.1:{args.docker_port}"
    wait_for_vm(base_url)
    return name, base_url


def stop_docker_vm(container_name: str, json_mode: bool) -> None:
    if not container_name:
        return
    cmd = ["docker", "stop", container_name]
    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def http_post_bytes(base_url: str, path: str, body: bytes) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"POST {path} failed with HTTP {response.status}")


def http_post_form(base_url: str, path: str, pairs: list[tuple[str, str]]) -> None:
    body = urllib.parse.urlencode(pairs).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"POST {path} failed with HTTP {response.status}")


def http_get_json(base_url: str, path: str, params: dict[str, str | list[str]]) -> dict:
    query = urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}?{query}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def export_series(base_url: str, matcher: str, start: str, end: str) -> list[dict]:
    query = urllib.parse.urlencode({"match[]": matcher, "start": start, "end": end})
    url = f"{base_url.rstrip('/')}/api/v1/export?{query}"
    out: list[dict] = []
    with urllib.request.urlopen(url, timeout=30) as response:
        for raw_line in response.read().decode("utf-8").splitlines():
            line = raw_line.strip()
            if line:
                out.append(json.loads(line))
    return out


def delete_matcher(base_url: str, matcher: str) -> None:
    http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", matcher)])


def reset_cache(base_url: str) -> None:
    try:
        http_post_form(base_url, "/internal/resetRollupResultCache", [])
    except urllib.error.HTTPError:
        pass


def fixture_timestamps(start_day: str, days: int, tz_name: str) -> list[int]:
    tz = ZoneInfo(tz_name)
    current = datetime.fromisoformat(start_day).replace(tzinfo=tz)
    end = current + timedelta(days=days)
    timestamps: list[int] = []
    while current < end:
        timestamps.append(int(current.astimezone(timezone.utc).timestamp() * 1000))
        current += timedelta(hours=1)
    return timestamps


def build_fixture_series(args: argparse.Namespace) -> list[Series]:
    timestamps = fixture_timestamps(args.start_day, 2, args.timezone)
    common = {"e2e_fixture": FIXTURE_LABEL}
    return [
        Series({"__name__": "pvPower_value", **common}, [1000.0] * len(timestamps), timestamps),
        Series({"__name__": "homePower_value", **common}, [500.0] * len(timestamps), timestamps),
        Series({"__name__": "gridPower_value", **common}, [250.0] * len(timestamps), timestamps),
        Series({"__name__": "chargePower_value", "loadpoint": "LP1", **common}, [100.0] * len(timestamps), timestamps),
        Series({"__name__": "extPower_value", "title": "Lab", **common}, [50.0] * len(timestamps), timestamps),
        Series({"__name__": "tariffGrid_value", **common}, [0.30] * len(timestamps), timestamps),
        Series({"__name__": "tariffFeedIn_value", **common}, [0.08] * len(timestamps), timestamps),
    ]


def serialize_series(series: list[Series]) -> bytes:
    lines = [
        json.dumps(
            {"metric": item.metric, "values": item.values, "timestamps": item.timestamps},
            separators=(",", ":"),
            ensure_ascii=True,
        )
        for item in series
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_config(base_url: str, args: argparse.Namespace, directory: Path) -> Path:
    config = configparser.ConfigParser()
    config["victoriametrics"] = {
        "base_url": base_url,
        "host_label": "",
        "timezone": args.timezone,
        "metric_prefix": ROLLUP_PREFIX,
        "raw_sample_step": "1h",
        "energy_rollup_step": "1h",
        "price_bucket_minutes": "60",
        "max_fetch_points_per_series": "50000",
    }
    config["benchmark"] = {
        "start": f"{args.start_day}T00:00:00Z",
        "end": f"{args.end_day}T23:59:59Z",
        "step": "1d",
    }
    path = directory / "evcc-rollup-e2e.conf"
    with path.open("w", encoding="utf-8") as handle:
        config.write(handle)
    return path


def run_rollup(config_path: Path, args: argparse.Namespace, json_mode: bool) -> dict:
    cmd = [
        sys.executable,
        str(ROLLUP_SCRIPT),
        "--config",
        str(config_path),
        "backfill",
        "--start-day",
        args.start_day,
        "--end-day",
        args.end_day,
        "--replace-range",
        "--write",
        "--json",
    ]
    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "rollup command failed "
            f"({result.returncode}): stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def assert_close(name: str, actual: float, expected: float, tolerance: float = 0.001) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")


def flatten_export_values(rows: list[dict]) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for row in rows:
        for timestamp, value in zip(row.get("timestamps", []), row.get("values", []), strict=False):
            values.append((int(timestamp), float(value)))
    return sorted(values)


def month_export_range(args: argparse.Namespace) -> tuple[str, str, str, str]:
    local_start = datetime.fromisoformat(args.start_day).replace(tzinfo=ZoneInfo(args.timezone))
    if local_start.month == 12:
        next_month = local_start.replace(year=local_start.year + 1, month=1, day=1)
    else:
        next_month = local_start.replace(month=local_start.month + 1, day=1)
    start_iso = (local_start.astimezone(timezone.utc) - timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    end_iso = (next_month.astimezone(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"{local_start.year:04d}", f"{local_start.month:02d}", start_iso, end_iso


def validate_rollup_values(base_url: str, args: argparse.Namespace) -> dict[str, object]:
    local_year, local_month, export_start, export_end = month_export_range(args)
    matcher = f'{{__name__=~"{ROLLUP_PREFIX}_.*",local_year="{local_year}",local_month="{local_month}"}}'
    rows = export_series(base_url, matcher, export_start, export_end)
    metric_values: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        name = row.get("metric", {}).get("__name__", "")
        metric_values.setdefault(name, []).extend(flatten_export_values([row]))

    required = {
        f"{ROLLUP_PREFIX}_pv_energy_daily_wh": 24000.0,
        f"{ROLLUP_PREFIX}_home_energy_daily_wh": 12000.0,
        f"{ROLLUP_PREFIX}_grid_import_daily_wh": 6000.0,
        f"{ROLLUP_PREFIX}_loadpoint_energy_daily_wh": 2400.0,
    }
    for metric, expected in required.items():
        samples = sorted(metric_values.get(metric, []))
        if len(samples) != 2:
            raise AssertionError(f"{metric}: expected 2 daily samples, got {len(samples)}")
        timestamps = [timestamp for timestamp, _value in samples]
        if len(set(timestamps)) != len(timestamps):
            raise AssertionError(f"{metric}: duplicate timestamps detected: {timestamps}")
        for _timestamp, value in samples:
            assert_close(metric, value, expected)

    return {
        "exported_series": len(rows),
        "required_metrics": sorted(required),
        "required_sample_counts": {metric: len(metric_values.get(metric, [])) for metric in required},
    }


def cleanup_fixture(base_url: str) -> None:
    delete_matcher(base_url, f'{{e2e_fixture="{FIXTURE_LABEL}"}}')
    delete_matcher(base_url, f'{{__name__=~"{ROLLUP_PREFIX}_.*"}}')
    reset_cache(base_url)


def run_e2e(base_url: str, args: argparse.Namespace, json_mode: bool) -> dict[str, object]:
    wait_for_vm(base_url)
    cleanup_fixture(base_url)
    http_post_bytes(base_url, "/api/v1/import", serialize_series(build_fixture_series(args)))
    reset_cache(base_url)

    with tempfile.TemporaryDirectory(prefix="evcc-rollup-e2e-") as tmp:
        config_path = write_config(base_url, args, Path(tmp))
        first = run_rollup(config_path, args, json_mode)
        first_values = validate_rollup_values(base_url, args)
        second = run_rollup(config_path, args, json_mode)
        second_values = validate_rollup_values(base_url, args)

    cleanup_fixture(base_url)
    return {
        "base_url": base_url,
        "first_run": {
            "samples": first.get("samples"),
            "series": first.get("series"),
            "replace_delete_results": first.get("replace_delete_results", []),
            **first_values,
        },
        "second_run": {
            "samples": second.get("samples"),
            "series": second.get("series"),
            "replace_delete_results": second.get("replace_delete_results", []),
            **second_values,
        },
    }


def main() -> int:
    args = parse_args()
    json_mode = bool(args.json)
    container_name = ""

    if args.docker:
        container_name, base_url = start_docker_vm(args, json_mode)
    else:
        base_url = args.base_url.strip()
        if not base_url:
            raise SystemExit("Pass --docker, or pass --base-url/ROLLUP_E2E_VM_URL with --confirm-disposable.")
        if not args.confirm_disposable:
            raise SystemExit("--confirm-disposable is required with --base-url because this test writes and deletes data.")
        if not is_local_url(base_url):
            raise SystemExit("Refusing non-local --base-url. Use --docker or tunnel the disposable VM to localhost.")

    try:
        summary = run_e2e(base_url, args, json_mode)
    finally:
        if container_name and not args.keep_docker:
            stop_docker_vm(container_name, json_mode)

    if json_mode:
        print(json.dumps({"script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION}, "result": "OK", **summary}, indent=2))
    else:
        print("EVCC rollup E2E")
        print("================")
        print(f"Script:       {SCRIPT_NAME}")
        print(f"Version:      {SCRIPT_VERSION}")
        print(f"Last modified:{SCRIPT_LAST_MODIFIED:>12}")
        print(f"Base URL:     {summary['base_url']}")
        print("\nResult")
        print("------")
        print("OK: repeated --replace-range rollups produced expected values without duplicate daily samples.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
