#!/usr/bin/env python3
"""
Script: import-pv-generation-costs.py
Purpose: Calculate PV generation cost rollups from existing VictoriaMetrics PV data.
Version: 2026.06.07.5
Last modified: 2026-06-07
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_VERSION = "2026.06.07.5"
SCRIPT_LAST_MODIFIED = "2026-06-07"
DEFAULT_DAILY_PV_METRIC = "evcc_pv_energy_by_title_daily_wh"


def log(message: str) -> None:
    print(message, flush=True)


def script_path(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def add_optional(cmd: list[str], option: str, value: str | None) -> None:
    if value:
        cmd.extend([option, value])


def add_flag(cmd: list[str], option: str, enabled: bool) -> None:
    if enabled:
        cmd.append(option)


def run_step(label: str, cmd: list[str]) -> None:
    printable = " ".join(cmd)
    log(f"\n[{label}] {printable}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {result.returncode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate PV generation cost rollups from metrics that already exist in VictoriaMetrics. "
            "SMA imports are intentionally handled by import-sma-energy-balance.py and import-sma-pv-energy.py. "
            "Dry-run by default."
        )
    )
    parser.add_argument("--vm-base-url", default="http://127.0.0.1:8428")
    parser.add_argument("--investment-file", default="data/private/investments.xlsx")
    parser.add_argument("--start", help="first local day, YYYY-MM-DD")
    parser.add_argument("--end", help="exclusive local end day, YYYY-MM-DD")
    parser.add_argument("--timezone", default="Europe/Berlin")
    parser.add_argument(
        "--energy-source",
        choices=["pv-power", "daily-metric", "combined"],
        default="pv-power",
        help="pv-power integrates EVCC pvPower_value; daily-metric reads a preimported daily Wh metric; combined merges both",
    )
    parser.add_argument(
        "--pv-energy-metric",
        default=DEFAULT_DAILY_PV_METRIC,
        help="per-title daily Wh metric to use with --energy-source=daily-metric or --energy-source=combined",
    )
    parser.add_argument(
        "--combined-energy-conflict",
        choices=["prefer-evcc", "prefer-daily-metric", "sum", "error"],
        default="prefer-evcc",
        help="how --energy-source=combined handles days where EVCC pvPower and the daily metric both have energy",
    )
    parser.add_argument("--peak-power-limit", type=float, default=30000.0)
    parser.add_argument("--sample-interval", default="30s")
    parser.add_argument("--skip-titles-without-energy", action="store_true")
    parser.add_argument("--write-pv-energy-rollup", action="store_true")
    parser.add_argument("--replace-costs", action="store_true", help="delete generated cost metrics before writing")
    parser.add_argument("--write", action="store_true", help="write to VictoriaMetrics; omitted means dry-run only")
    return parser.parse_args()


def build_cost_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(script_path("import-investment-costs.py")),
        "--vm-base-url",
        args.vm_base_url,
        "--investment-file",
        args.investment_file,
        "--timezone",
        args.timezone,
        "--energy-source",
        args.energy_source,
        "--pv-energy-metric",
        args.pv_energy_metric,
        "--combined-energy-conflict",
        args.combined_energy_conflict,
        "--peak-power-limit",
        str(args.peak_power_limit),
        "--sample-interval",
        args.sample_interval,
    ]
    add_optional(cmd, "--start", args.start)
    add_optional(cmd, "--end", args.end)
    add_flag(cmd, "--skip-titles-without-energy", args.skip_titles_without_energy)
    add_flag(cmd, "--write-pv-energy-rollup", args.write_pv_energy_rollup)
    add_flag(cmd, "--replace", args.replace_costs)
    add_flag(cmd, "--write", args.write)
    return cmd


def main() -> int:
    started = time.perf_counter()
    args = parse_args()
    log(f"import-pv-generation-costs.py v{SCRIPT_VERSION} (last modified {SCRIPT_LAST_MODIFIED})")
    log(f"Mode: {'write' if args.write else 'dry-run'}")
    log("SMA import: not handled here. Run import-sma-energy-balance.py and/or import-sma-pv-energy.py first if needed.")
    log(f"Investment energy source: {args.energy_source}")
    run_step("PV generation cost rollup", build_cost_cmd(args))
    log(f"\nWorkflow finished in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

