#!/usr/bin/env python3
"""Single-process prototype runtime spike for PiCycle."""

from __future__ import annotations

import importlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ride_session import RideSession
from runtime_modes import display_module_name, load_settings, speed_module_name


class RuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current: dict[str, Any] = {}
        self.running = False

    def update(self, current: dict[str, Any]) -> None:
        with self._lock:
            self.current = dict(current)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.current)


class ApplianceRuntime:
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self.settings = settings or load_settings()
        self.state = RuntimeState()
        self.session = RideSession()
        self.speed = self._create_speed()
        self.display = self._create_display()

    def _create_speed(self):
        module = importlib.import_module(speed_module_name(self.settings))
        return module.BikeSpeed(
            pulse_gpio=self.settings["gpio_assignments"]["wheel"]["pulses"],
            radius=float(self.settings["globals"]["wheel_rad_inches"]),
        )

    def _create_display(self):
        module = importlib.import_module(display_module_name(self.settings))
        return module.Display(dev_pins=self.settings["gpio_assignments"])

    def tick(self) -> dict[str, Any]:
        now = time.time()
        current = {
            "captured_at": now,
            "curr_speed": self.speed.curr_speed(),
            "avg_speed": self.speed.avg_speed(),
            "distance": self.speed.distance(),
            "rpm": self.speed.rpm(),
            "avg_rpm": self.speed.average_rpm(),
            "timer": str(self.speed.timer()),
            "session": self.session.snapshot(now),
        }
        self.state.update(current)
        self.display.display_status(current)
        return current

    def run(self, iterations: int | None = None, tick_seconds: float = 1.0) -> None:
        self.state.running = True
        count = 0
        try:
            while iterations is None or count < iterations:
                self.tick()
                count += 1
                time.sleep(tick_seconds)
        finally:
            self.state.running = False


class StatusServer:
    def __init__(self, runtime: ApplianceRuntime, host: str = "127.0.0.1", port: int = 0) -> None:
        self.runtime = runtime
        handler = self._make_handler(runtime)
        self.server = ThreadingHTTPServer((host, port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @staticmethod
    def _make_handler(runtime: ApplianceRuntime):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path != "/status":
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = json.dumps(runtime.state.snapshot(), sort_keys=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):  # noqa: A002
                return

        return Handler

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/status"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
