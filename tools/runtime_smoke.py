#!/usr/bin/env python3
"""Smoke test for the single-process prototype runtime spike."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from appliance_runtime import ApplianceRuntime, StatusServer  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PiCycle appliance runtime smoke.")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--tick-seconds", type=float, default=0.01)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("PICYCLE_HARDWARE", "prototype")
    os.environ.setdefault("PICYCLE_DISPLAY", "headless")

    runtime = ApplianceRuntime()
    server = StatusServer(runtime)
    server.start()
    try:
        runtime.run(iterations=args.iterations, tick_seconds=args.tick_seconds)
        with urllib.request.urlopen(server.url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    required = {"curr_speed", "avg_speed", "distance", "rpm", "avg_rpm", "timer", "session"}
    missing = sorted(required - set(payload))
    if missing:
        print(f"Runtime smoke failed. Missing status keys: {', '.join(missing)}")
        return 1

    print(f"status_url={server.url}")
    print(f"status={payload}")
    print("Runtime smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
