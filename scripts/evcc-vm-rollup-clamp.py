#!/usr/bin/env python3
"""Wrapper for the clamp-based EVCC VictoriaMetrics rollup variant."""

from __future__ import annotations

import pathlib
import runpy
import sys

THIS_DIR = pathlib.Path(__file__).resolve().parent
MAIN = THIS_DIR / "evcc-vm-rollup.py"
DEFAULT_CONFIG = THIS_DIR / "evcc-vm-rollup-clamp.conf.example"

if "--config" not in sys.argv[1:]:
    sys.argv = [sys.argv[0], "--config", str(DEFAULT_CONFIG), *sys.argv[1:]]

runpy.run_path(str(MAIN), run_name="__main__")
