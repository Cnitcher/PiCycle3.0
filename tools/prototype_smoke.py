#!/usr/bin/env python3
"""Prototype/headless runtime smoke check.

This exercises the prototype speed module and headless display without importing Redis,
RPi.GPIO, luma.lcd, OpenCV, or pynput.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_modes import display_module_name, load_settings, speed_module_name  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a prototype/headless PiCycle smoke check.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    settings.setdefault("globals", {})["real_hw"] = False

    speed_module = speed_module_name(settings)
    display_module = display_module_name(settings)

    speed = importlib.import_module(speed_module).BikeSpeed(
        pulse_gpio=settings["gpio_assignments"]["wheel"]["pulses"],
        radius=float(settings["globals"]["wheel_rad_inches"]),
    )
    display = importlib.import_module(display_module).Display(
        dev_pins=settings["gpio_assignments"],
    )

    current = {}
    for _ in range(args.iterations):
        current = {
            "curr_speed": speed.curr_speed(),
            "avg_speed": speed.avg_speed(),
            "distance": speed.distance(),
            "rpm": speed.rpm(),
            "avg_rpm": speed.average_rpm(),
            "timer": str(speed.timer()),
        }
        display.display_status(current)
        display.display_test()
        time.sleep(args.sleep)

    print(f"speed_module={speed_module}")
    print(f"display_module={display_module}")
    print(f"current={current}")
    print("Prototype smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
