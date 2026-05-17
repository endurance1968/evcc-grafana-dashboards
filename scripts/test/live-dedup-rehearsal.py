#!/usr/bin/env python3
"""Replay selected live VM series into Docker and rehearse deduplication there."""

from __future__ import annotations

import argparse
import importlib.util
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
from collections import Counter
from pathlib import Path


SCRIPT_NAME = "live-dedup-rehearsal.py"
SCRIPT_VERSION = "2026.05.16.3"
SCRIPT_LAST_MODIFIED = "2026-05-16"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEDUP_SCRIPT = REPO_ROOT / "scripts" / "helper" / "vm-dedup-series.py"
DEDUP_SPEC = importlib.util.spec_from_file_location("vm_dedup_series_for_rehearsal", DEDUP_SCRIPT)
DEDUP = importlib.util.module_from_spec(DEDUP_SPEC)
sys.modules[DEDUP_SPEC.name] = DEDUP
assert DEDUP_SPEC.loader is not None
DEDUP_SPEC.loader.exec_module(DEDUP)

DEFAULT_DOCKER_IMAGE = "victoriametrics/victoria-metrics:v1.110.0"
DEFAULT_MATCHERS = [
    'pvPower_value{title="Balkon Sued"}',
    'pvEnergy_value{title="Balkon Sued"}',
    'pvPower_value{title="Carport West"}',
    'pvEnergy_value{title="Carport West"}',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read selected series from a live VM, copy them into a disposable Docker VM, and run "
            "vm-dedup-series.py only against the Docker copy."
        )
    )
    parser.add_argument("--source-base-url", required=True, help="Read-only source VictoriaMetrics base URL.")
    parser.add_argument("--matcher", action="append", default=[], help="Matcher to rehearse. Can be passed multiple times.")
    parser.add_argument("--start", default="1", help="Export start as Unix seconds or RFC3339.")
    parser.add_argument("--end", default="", help="Export end as Unix seconds or RFC3339. Defaults to tomorrow UTC.")
    parser.add_argument("--docker", action="store_true", help="Start a temporary VictoriaMetrics Docker container.")
    parser.add_argument("--docker-image", default=DEFAULT_DOCKER_IMAGE, help="VictoriaMetrics Docker image.")
    parser.add_argument("--docker-port", type=int, default=0, help="Host port for Docker mode; 0 lets Docker choose.")
    parser.add_argument("--keep-docker", action="store_true", help="Do not stop the Docker container after the test.")
    parser.add_argument("--import-batch-size", type=int, default=1)
    parser.add_argument("--max-import-line-bytes", type=int, default=8_000_000)
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
    name = f"evcc-live-dedup-rehearsal-{os.getpid()}-{uuid.uuid4().hex[:8]}"
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
        port_mapping = f"{default_docker_bind_address()}:{args.docker_port}:8428" if args.docker_port > 0 else f"{default_docker_bind_address()}::8428"
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
            base_url = f"http://{default_docker_published_host()}:{port}"
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


def export_rows(base_url: str, matcher: str, start: str, end: str):
    url = base_url.rstrip("/") + "/api/v1/export?" + urllib.parse.urlencode({"match[]": matcher, "start": start, "end": end})
    with urllib.request.urlopen(url, timeout=600) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if line:
                yield json.loads(line)


def analyze_rows(rows: list[dict]) -> dict[str, int]:
    points = 0
    unique_points = 0
    duplicate_extra_samples = 0
    conflict_samples = 0
    for row in rows:
        values_by_timestamp: dict[int, float] = {}
        for ts_raw, value_raw in zip(row.get("timestamps", []), row.get("values", []), strict=False):
            points += 1
            ts = int(ts_raw)
            value = float(value_raw)
            if ts in values_by_timestamp:
                duplicate_extra_samples += 1
                if values_by_timestamp[ts] != value:
                    conflict_samples += 1
            else:
                values_by_timestamp[ts] = value
        unique_points += len(values_by_timestamp)
    return {
        "series": len(rows),
        "points": points,
        "unique_points": unique_points,
        "duplicate_extra_samples": duplicate_extra_samples,
        "conflict_samples": conflict_samples,
    }


def import_rows(base_url: str, rows: list[dict], batch_size: int, max_line_bytes: int) -> tuple[int, int]:
    return DEDUP.import_rows(base_url, rows, batch_size, max_line_bytes)


def wait_for_reproduced_import(base_url: str, matcher: str, expected: dict[str, int], start: str, end: str, timeout_seconds: int = 120) -> dict[str, int]:
    deadline = time.time() + timeout_seconds
    last = {"series": 0, "points": 0, "unique_points": 0, "duplicate_extra_samples": 0, "conflict_samples": 0}
    while time.time() < deadline:
        last = analyze_rows(list(export_rows(base_url, matcher, start, end)))
        if last == expected:
            return last
        time.sleep(1)
    return last


def run_dedup(args: list[str], json_mode: bool) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(DEDUP_SCRIPT), *args]
    log(f"$ {' '.join(cmd)}", json_mode=json_mode)
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def assert_success(result: subprocess.CompletedProcess[str], context: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{context} failed with exit code {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def rehearse_matcher(source_base_url: str, target_base_url: str, matcher: str, start: str, end: str, args: argparse.Namespace, work_dir: Path, json_mode: bool) -> dict[str, object]:
    source_rows = list(export_rows(source_base_url, matcher, start, end))
    before = analyze_rows(source_rows)
    imported_batches, imported_chunks = import_rows(target_base_url, source_rows, args.import_batch_size, args.max_import_line_bytes)
    docker_before = wait_for_reproduced_import(target_base_url, matcher, before, start, end)
    if docker_before != before:
        raise AssertionError(f"Docker import did not reproduce source for {matcher}: source={before}, docker={docker_before}")

    safe_name = "".join(ch if ch.isalnum() else "_" for ch in matcher)[:80]
    common = [
        "--base-url",
        target_base_url,
        "--matcher",
        matcher,
        "--start",
        start,
        "--end",
        end,
        "--backup-jsonl",
        str(work_dir / f"{safe_name}.jsonl"),
        "--deduped-jsonl",
        str(work_dir / f"{safe_name}.deduped.jsonl"),
    ]
    dry_run = run_dedup(common, json_mode)
    assert_success(dry_run, f"dry-run {matcher}")
    if before["duplicate_extra_samples"] and before["conflict_samples"] == 0 and "GO FOR IT" not in dry_run.stdout:
        raise AssertionError(f"Dry-run did not recommend write for {matcher}:\n{dry_run.stdout}\n{dry_run.stderr}")

    write = run_dedup([*common, "--reset-cache", "--write"], json_mode)
    assert_success(write, f"write {matcher}")
    docker_after_rows = list(export_rows(target_base_url, matcher, start, end))
    docker_after = analyze_rows(docker_after_rows)
    expected_points = before["unique_points"]
    if docker_after["points"] != expected_points or docker_after["duplicate_extra_samples"] != 0 or docker_after["conflict_samples"] != 0:
        raise AssertionError(f"Docker dedup result invalid for {matcher}: before={before}, after={docker_after}")

    second_dry_run = run_dedup(common, json_mode)
    assert_success(second_dry_run, f"second dry-run {matcher}")
    if "No duplicate timestamps were found" not in second_dry_run.stdout:
        raise AssertionError(f"Second dry-run was not idempotent for {matcher}:\n{second_dry_run.stdout}\n{second_dry_run.stderr}")

    return {
        "matcher": matcher,
        "source": before,
        "docker_before": docker_before,
        "docker_after": docker_after,
        "import_batches": imported_batches,
        "imported_chunks": imported_chunks,
    }


def main() -> int:
    args = parse_args()
    if not args.docker:
        raise SystemExit("--docker is required; this rehearsal must write only to a disposable Docker VM.")
    start = DEDUP.api_time(args.start)
    end = DEDUP.api_time(args.end or DEDUP.default_end_timestamp())
    matchers = args.matcher or DEFAULT_MATCHERS
    json_mode = bool(args.json)
    container_name = ""
    try:
        container_name, target_base_url = start_docker_vm(args, json_mode)
        with tempfile.TemporaryDirectory(prefix="evcc-live-dedup-rehearsal-") as tmp:
            work_dir = Path(tmp)
            results = [
                rehearse_matcher(args.source_base_url, target_base_url, matcher, start, end, args, work_dir, json_mode)
                for matcher in matchers
            ]
    finally:
        if container_name and not args.keep_docker:
            stop_docker_vm(container_name, json_mode)

    summary = {
        "script": {"name": SCRIPT_NAME, "version": SCRIPT_VERSION, "last_modified": SCRIPT_LAST_MODIFIED},
        "source_base_url": args.source_base_url,
        "target_base_url": target_base_url,
        "start": start,
        "end": end,
        "result": "OK",
        "matchers": results,
    }
    if json_mode:
        print(json.dumps(summary, indent=2))
    else:
        print("EVCC live dedup rehearsal")
        print("========================")
        print(f"Script:       {SCRIPT_NAME}")
        print(f"Version:      {SCRIPT_VERSION}")
        print(f"Last modified:{SCRIPT_LAST_MODIFIED:>12}")
        print(f"Source:       {args.source_base_url}")
        print(f"Docker VM:    {target_base_url}")
        print("\nResult")
        print("------")
        print("OK: live-exported series were reproduced in Docker, deduplicated, verified, and rechecked idempotently.")
        for item in results:
            print(
                f"- {item['matcher']}: points {item['source']['points']} -> {item['docker_after']['points']}, "
                f"duplicates {item['source']['duplicate_extra_samples']} -> {item['docker_after']['duplicate_extra_samples']}"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
