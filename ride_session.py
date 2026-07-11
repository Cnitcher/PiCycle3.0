#!/usr/bin/env python3
"""Ride session state machine for the PiCycle appliance runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


IDLE = "idle"
RIDING = "riding"
PAUSED = "paused"
COMPLETED = "completed"
SAVED = "saved"
DISCARDED = "discarded"


TERMINAL_STATES = {SAVED, DISCARDED}


class InvalidTransition(ValueError):
    pass


@dataclass
class RideSession:
    state: str = IDLE
    started_at: float | None = None
    paused_at: float | None = None
    ended_at: float | None = None
    accumulated_pause_seconds: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)

    def _ensure(self, *states: str) -> None:
        if self.state not in states:
            allowed = ", ".join(states)
            raise InvalidTransition(f"Cannot transition from {self.state}; expected {allowed}.")

    def _event(self, event_type: str, now: float) -> None:
        self.events.append({"type": event_type, "at": now})

    def start(self, now: float) -> None:
        self._ensure(IDLE)
        self.state = RIDING
        self.started_at = now
        self.paused_at = None
        self.ended_at = None
        self.accumulated_pause_seconds = 0.0
        self.events.clear()
        self._event("start", now)

    def pause(self, now: float) -> None:
        self._ensure(RIDING)
        self.state = PAUSED
        self.paused_at = now
        self._event("pause", now)

    def resume(self, now: float) -> None:
        self._ensure(PAUSED)
        if self.paused_at is not None:
            self.accumulated_pause_seconds += max(0.0, now - self.paused_at)
        self.state = RIDING
        self.paused_at = None
        self._event("resume", now)

    def complete(self, now: float) -> None:
        self._ensure(RIDING, PAUSED)
        if self.state == PAUSED and self.paused_at is not None:
            self.accumulated_pause_seconds += max(0.0, now - self.paused_at)
            self.paused_at = None
        self.state = COMPLETED
        self.ended_at = now
        self._event("complete", now)

    def save(self, now: float) -> None:
        self._ensure(COMPLETED)
        self.state = SAVED
        self._event("save", now)

    def discard(self, now: float) -> None:
        self._ensure(IDLE, COMPLETED)
        self.state = DISCARDED
        self._event("discard", now)

    def active_seconds(self, now: float) -> float:
        if self.started_at is None:
            return 0.0
        end = self.ended_at if self.ended_at is not None else now
        paused = self.accumulated_pause_seconds
        if self.state == PAUSED and self.paused_at is not None:
            paused += max(0.0, now - self.paused_at)
        return max(0.0, end - self.started_at - paused)

    def snapshot(self, now: float) -> dict[str, Any]:
        return {
            "state": self.state,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "ended_at": self.ended_at,
            "active_seconds": self.active_seconds(now),
            "event_count": len(self.events),
        }

