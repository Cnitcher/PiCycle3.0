#!/usr/bin/env python3
"""Runtime mode selection helpers for PiCycle.

These helpers intentionally use only the Python standard library so tools can check
prototype/headless behavior without importing Redis, GPIO, or display libraries.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS_FILE = Path("settings.json")


def load_settings(filename: str | Path = DEFAULT_SETTINGS_FILE) -> dict[str, Any]:
    with Path(filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "real", "hardware"}


def is_real_hardware(settings: dict[str, Any]) -> bool:
    env_mode = os.getenv("PICYCLE_HARDWARE")
    if env_mode:
        return _truthy(env_mode)

    env_real_hw = os.getenv("PICYCLE_REAL_HW")
    if env_real_hw:
        return _truthy(env_real_hw)

    return bool(settings.get("globals", {}).get("real_hw", False))


def speed_module_name(settings: dict[str, Any]) -> str:
    return "speed_input.hall_sensor" if is_real_hardware(settings) else "speed_input.prototype"


def display_module_name(settings: dict[str, Any]) -> str:
    display_mode = os.getenv("PICYCLE_DISPLAY", "auto").strip().lower()
    if display_mode == "headless":
        return "display.headless"
    if display_mode in {"prototype", "desktop"}:
        return "display.prototype"
    if display_mode in {"ili9341", "real", "hardware"}:
        return "display.ili9341"
    return "display.ili9341" if is_real_hardware(settings) else "display.prototype"

