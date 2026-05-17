#!/usr/bin/env python3
"""Run a disposable VictoriaMetrics E2E test for exact-series deduplication."""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


SCRIPT_NAME = "dedup-series-e2e.py"
SCRIPT_VERSION = "2026.05.16.1"
SCRIPT_LAST_MODIFIED = "2026-05-16"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEDUP_SCRIPT = REPO_ROOT / "scripts" / "helper" / "vm-dedup-series.py"
DEFAULT_DOCKER_IMAGE = "victoriametrics/victoria-metrics:v1.110.0"
START = "1"
END = "1710001000"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate vm-dedup-series.py against a disposable VictoriaMetrics. "
            "Use --docker for an isolated container, or --base-url with --confirm-disposable."
        )
    )
    parser.add_argument("--docker", action="store_true", help="Start a temporary VictoriaMetrics Docker container.")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE, help="VictoriaMetrics Docker image.")
    parser.add_argument("--docker-port", type=int, default=0, help="Host port for Docker mode; 0 lets Docker choose.")
    parser.add_argument(
        "--docker-bind-address",
        default=os.environ.get("DEDUP_E2E_DOCKER_BIND_ADDRESS", ""),
        help="Host address used for Docker port publishing; defaults to 0.0.0.0 inside containers, otherwise 127.0.0.1.",
    )
    parser.add_argument(
        "--docker-published-host",
        default=os.environ.get("DEDUP_E2E_DOCKER_PUBLISHED_HOST", ""),
        help="Host name used by the test to reach the published Docker port.",
    )
    parser.add_argument("--keep-docker", action="store_true", help="Do not stop the Docker container after the test.")
    parser.add_argument("--base-url", default=os.environ.get("DEDUP_E2E_VM_URL", ""), help="Disposable VM base URL.")
    parser.add_argument(
        "--confirm-disposable",
        action="store_true",
        help="Required with --base-url because this test writes and deletes data.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    return parser.parse_args()


def runs_inside_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def default_docker_bind_address() -> str:
    return "0.0.0.0" if runs_inside_container() else "127.0.0.1"


def docker_host_published_address() -> str:
    try:
        infos = socket.getaddrinfo("host.docker.internal", None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return str(infos[0][4][0])
    except socket.gaierror:
        pass
    try:
        with Path("/proc/net/route").open("r", encoding="utf-8") as handle:
            for line in handle.readlines()[1:]:
                fields = line.split()
                if len(fields) >= 3 and fields[1] == "00000000":
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except OSError:
        pass
    return "host.docker.internal"


def default_docker_published_host() -> str:
    return docker_host_published_address() if runs_inside_container() else "127.0.0.1"


def log(message: str, *, json_mode: bool) -> None:
    if not json_mode:
        print(message, flush=True)


def wait_for_vm(base_url: str, timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=2) as response:
                if 200 <= response.status < 300:
                    return
        except Exception as exc:  # noqa: BLE001 - report last startup error.
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"VictoriaMetrics did not become healthy at {base_url}: {last_error}")


def docker_published_port(container_name: str) -> int:
    result = subprocess.run(
        ["docker", "port", container_name, "8428/tcp"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker port failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    line = next((item.strip() for item in result.stdout.splitlines() if item.strip()), "")
    if not line:
        raise RuntimeError(f"Docker did not report a published port for {container_name}:8428/tcp")
    return int(line.rsplit(":", 1)[-1])


def start_docker_vm(args: argparse.Namespace, json_mode: bool) -> tuple[str, str]:
    name = f"evcc-dedup-e2e-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    if runs_inside_container():
        cmd = [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "--network",
            f"container:{socket.gethostname()}",
            args.docker_image,
            "-retentionPeriod=100y",
        ]
        base_url = "http://127.0.0.1:8428"
    else:
        bind_address = args.docker_bind_address or default_docker_bind_address()
        published_host = args.docker_published_host or default_docker_published_host()
        port_mapping = f"{bind_address}:{args.docker_port}:8428" if args.docker_port > 0 else f"{bind_address}::8428"
        cmd = [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-p",
            port_mapping,
            args.docker_image,
            "-retentionPeriod=100y",
        ]
        base_url = ""

    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    try:
        if not runs_inside_container():
            port = args.docker_port if args.docker_port > 0 else docker_published_port(name)
            published_host = args.docker_published_host or default_docker_published_host()
            base_url = f"http://{published_host}:{port}"
        wait_for_vm(base_url)
        return name, base_url
    except Exception:
        subprocess.run(["docker", "stop", name], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        raise


def stop_docker_vm(container_name: str, json_mode: bool) -> None:
    if not container_name:
        return
    log(f"$ docker stop {container_name}", json_mode=json_mode)
    subprocess.run(["docker", "stop", container_name], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


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
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=urllib.parse.urlencode(pairs).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"POST {path} failed with HTTP {response.status}")


def reset_cache(base_url: str) -> None:
    try:
        http_post_form(base_url, "/internal/resetRollupResultCache", [])
    except Exception:  # noqa: BLE001 - old VM builds may not expose this endpoint.
        pass


def serialize_jsonl(rows: list[dict]) -> bytes:
    return ("\n".join(json.dumps(row, separators=(",", ":"), ensure_ascii=True) for row in rows) + "\n").encode("utf-8")


def delete_fixture(base_url: str, fixture_label: str) -> None:
    http_post_form(base_url, "/api/v1/admin/tsdb/delete_series", [("match[]", f'{{e2e_fixture="{fixture_label}"}}')])
    reset_cache(base_url)


def fixture_rows(fixture_label: str) -> list[dict]:
    return [
        {
            "metric": {"__name__": "pvPower_value", "title": "Dedup Clean", "e2e_fixture": fixture_label},
            "timestamps": [1710000000000, 1710000000000, 1710000060000, 1710000060000, 1710000120000],
            "values": [100.0, 100.0, 120.0, 120.0, 130.0],
        },
        {
            "metric": {"__name__": "pvEnergy_value", "title": "Dedup Clean", "e2e_fixture": fixture_label},
            "timestamps": [1710000000000, 1710000000000, 1710000060000],
            "values": [10.0, 10.0, 11.0],
        },
        {
            "metric": {"__name__": "pvPower_value", "title": "Dedup Conflict", "e2e_fixture": fixture_label},
            "timestamps": [1710000000000, 1710000000000],
            "values": [1.0, 2.0],
        },
        {
            "metric": {"__name__": "pvPower_value", "title": "Dedup Superset", "e2e_fixture": fixture_label},
            "timestamps": [1710000000000, 1710000000000],
            "values": [1.0, 1.0],
        },
        {
            "metric": {"__name__": "pvPower_value", "title": "Dedup Superset", "host": "vm", "e2e_fixture": fixture_label},
            "timestamps": [1710000000000, 1710000000000],
            "values": [2.0, 2.0],
        },
    ]


def export_points(base_url: str, matcher: str) -> list[tuple[int, float]]:
    query = urllib.parse.urlencode({"match[]": matcher, "start": START, "end": END})
    points: list[tuple[int, float]] = []
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/v1/export?{query}", timeout=30) as response:
        for raw_line in response.read().decode("utf-8").splitlines():
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            for timestamp, value in zip(row.get("timestamps", []), row.get("values", []), strict=False):
                points.append((int(timestamp), float(value)))
    return sorted(points)


def wait_for_export_points(base_url: str, matcher: str, expected_count: int, timeout_seconds: int = 30) -> list[tuple[int, float]]:
    deadline = time.time() + timeout_seconds
    last: list[tuple[int, float]] = []
    while time.time() < deadline:
        last = export_points(base_url, matcher)
        if len(last) == expected_count:
            return last
        time.sleep(0.5)
    raise AssertionError(f"{matcher}: expected {expected_count} exported points, got {len(last)}: {last}")


def run_dedup(args: list[str], json_mode: bool) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(DEDUP_SCRIPT), *args]
    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def assert_success(result: subprocess.CompletedProcess[str], context: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{context} failed with exit code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def assert_failure(result: subprocess.CompletedProcess[str], context: str) -> None:
    if result.returncode == 0:
        raise AssertionError(f"{context} unexpectedly succeeded\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")


def run_e2e(base_url: str, json_mode: bool) -> dict[str, object]:
    wait_for_vm(base_url)
    fixture_label = f"dedup-series-{uuid.uuid4().hex[:8]}"
    http_post_bytes(base_url, "/api/v1/import", serialize_jsonl(fixture_rows(fixture_label)))
    reset_cache(base_url)
    wait_for_export_points(base_url, f'pvPower_value{{title="Dedup Clean",e2e_fixture="{fixture_label}"}}', 5)

    with tempfile.TemporaryDirectory(prefix="evcc-dedup-series-e2e-") as tmp:
        tmp_path = Path(tmp)
        clean_common = [
            "--base-url",
            base_url,
            "--matcher",
            f'{{title="Dedup Clean",e2e_fixture="{fixture_label}"}}',
            "--start",
            START,
            "--end",
            END,
            "--backup-jsonl",
            str(tmp_path / "clean.jsonl"),
            "--deduped-jsonl",
            str(tmp_path / "clean-deduped.jsonl"),
        ]
        dry_run = run_dedup(clean_common, json_mode)
        assert_success(dry_run, "clean dry-run")
        if "GO FOR IT" not in dry_run.stdout:
            raise AssertionError(f"clean dry-run did not report GO FOR IT:\n{dry_run.stdout}\n{dry_run.stderr}")

        write = run_dedup([*clean_common, "--reset-cache", "--write"], json_mode)
        assert_success(write, "clean write")
        power_points = wait_for_export_points(
            base_url,
            f'pvPower_value{{title="Dedup Clean",e2e_fixture="{fixture_label}"}}',
            3,
        )
        energy_points = wait_for_export_points(
            base_url,
            f'pvEnergy_value{{title="Dedup Clean",e2e_fixture="{fixture_label}"}}',
            2,
        )
        if power_points != [(1710000000000, 100.0), (1710000060000, 120.0), (1710000120000, 130.0)]:
            raise AssertionError(f"deduped pvPower points differ: {power_points}")
        if energy_points != [(1710000000000, 10.0), (1710000060000, 11.0)]:
            raise AssertionError(f"deduped pvEnergy points differ: {energy_points}")

        second_dry_run = run_dedup(clean_common, json_mode)
        assert_success(second_dry_run, "second clean dry-run")
        if "No duplicate timestamps were found" not in second_dry_run.stdout:
            raise AssertionError(f"second dry-run was not idempotent:\n{second_dry_run.stdout}\n{second_dry_run.stderr}")

        conflict_common = [
            "--base-url",
            base_url,
            "--matcher",
            f'{{title="Dedup Conflict",e2e_fixture="{fixture_label}"}}',
            "--start",
            START,
            "--end",
            END,
            "--backup-jsonl",
            str(tmp_path / "conflict.jsonl"),
        ]
        conflict_dry_run = run_dedup(conflict_common, json_mode)
        assert_success(conflict_dry_run, "conflict dry-run")
        if "STOP" not in conflict_dry_run.stdout:
            raise AssertionError(f"conflict dry-run did not stop:\n{conflict_dry_run.stdout}\n{conflict_dry_run.stderr}")
        conflict_write = run_dedup([*conflict_common, "--write"], json_mode)
        assert_failure(conflict_write, "conflict write")

        superset_common = [
            "--base-url",
            base_url,
            "--matcher",
            f'pvPower_value{{title="Dedup Superset",e2e_fixture="{fixture_label}"}}',
            "--start",
            START,
            "--end",
            END,
            "--backup-jsonl",
            str(tmp_path / "superset.jsonl"),
        ]
        superset_write = run_dedup([*superset_common, "--write"], json_mode)
        assert_failure(superset_write, "superset write")
        if "superset" not in (superset_write.stdout + superset_write.stderr).lower():
            raise AssertionError(f"superset write did not explain superset risk:\n{superset_write.stdout}\n{superset_write.stderr}")

    delete_fixture(base_url, fixture_label)
    return {
        "base_url": base_url,
        "fixture_label": fixture_label,
        "clean_power_points": power_points,
        "clean_energy_points": energy_points,
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
            raise SystemExit("Pass --docker, or pass --base-url with --confirm-disposable.")
        if not args.confirm_disposable:
            raise SystemExit("--confirm-disposable is required with --base-url because this test writes and deletes data.")

    try:
        summary = run_e2e(base_url, json_mode)
    finally:
        if container_name and not args.keep_docker:
            stop_docker_vm(container_name, json_mode)

    if json_mode:
        print(json.dumps({"script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION}, "result": "OK", **summary}, indent=2))
    else:
        print("EVCC dedup series E2E")
        print("=====================")
        print(f"Script:       {SCRIPT_NAME}")
        print(f"Version:      {SCRIPT_VERSION}")
        print(f"Last modified:{SCRIPT_LAST_MODIFIED:>12}")
        print(f"Base URL:     {summary['base_url']}")
        print("\nResult")
        print("------")
        print("OK: dedup write removed identical duplicates, stayed idempotent, and blocked unsafe writes.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
