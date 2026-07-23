"""Knob-first PiCycle appliance state for the 320x240 cockpit."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from effort import echo_machine_calories_per_minute


MENU = ["Ride", "Programs", "History", "Settings"]
PROGRAMS = ["Tabata", "Swedish 4x4"]
PAUSE_MENU = ["Resume", "Save and End", "Discard"]
REVIEW_ACTIONS = ["Back", "Delete"]
DELETE_CONFIRM_ACTIONS = ["No", "Yes"]
GUEST_LABEL = "Guest"
NEW_RIDER_LABEL = "New Rider"
SETUP_INSTRUCTION = "Scan for setup"
DEFAULT_PROFILE_SETUP_PATH = "/profiles/new"
DOUBLE_PRESS_SECONDS = 0.28
TIME_STEP_SECONDS = 10


@dataclass
class Phase:
    name: str
    remaining: float
    round: int
    rounds: int
    phase_start: float = 0.0


def format_mmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    return format_mmss(seconds)


def _program_label(label: str) -> str:
    if label == "Quick Start":
        return "Ride"
    return " ".join(word if word.isupper() else word.capitalize() for word in label.split())


class PiCycleAppliance:
    """Small, deterministic appliance brain shared by display and tests."""

    def __init__(
        self,
        rides: list[dict[str, Any]] | None = None,
        rider_profiles: list[dict[str, Any]] | None = None,
        profile_setup_url: str = DEFAULT_PROFILE_SETUP_PATH,
    ) -> None:
        self.view = "rider_select"
        self.selected = 0
        self.status = "idle"
        self.active_label = "Ride"
        self.active_mode = "ride"
        self.active_review_id: str | None = None
        self.tabata_config = {"warmupSec": 120, "hotSec": 20, "recoverSec": 40, "rounds": 8}
        self.swedish_config = {"warmupSec": 120, "hardSec": 240, "recoverSec": 180, "rounds": 4}
        self.elapsed = 0.0
        self.distance = 0.0
        self.speed = 0.0
        self.avg_speed = 0.0
        self.calories = 0.0
        self.pace = 0.0
        self.pace_history = [0.0]
        self.speed_history = [0.0]
        self.started_at: float | None = None
        self.ended_at: float | None = None
        self._last_update_at: float | None = None
        self._pending_press_at: float | None = None
        self._last_saved_ride: dict[str, Any] | None = None
        self._last_deleted_ride_id: str | None = None
        self.rides = rides or []
        self.rider_profiles = self._clean_profiles(rider_profiles or [])
        self.selected_rider: dict[str, Any] | None = None
        self.profile_setup_url = profile_setup_url

    def update_metrics(self, current: dict[str, Any] | None = None, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._flush_pending_press(now)
        current = current or {}

        if self.status != "riding":
            self._last_update_at = now
            return

        if self._last_update_at is None:
            self._last_update_at = now
            return

        dt = max(0.0, now - self._last_update_at)
        self._last_update_at = now
        self.speed = max(0.0, float(current.get("curr_speed") or 0.0))
        rpm = max(0.0, float(current.get("rpm") or 0.0))
        self.pace = echo_machine_calories_per_minute(rpm)
        self.elapsed += dt
        self.distance += self.speed * dt / 3600.0
        self.calories += self.pace * dt / 60.0
        self.avg_speed = self.distance / (self.elapsed / 3600.0) if self.elapsed > 0 else 0.0
        self.pace_history.append(self.pace)
        self.speed_history.append(self.speed)

        if self.active_mode == "tabata" and self.elapsed >= self.tabata_total_seconds():
            self._complete_program()
        if self.active_mode == "swedish" and self.elapsed >= self.swedish_total_seconds():
            self._complete_program()

    def handle_input(self, command: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._flush_pending_press(now)
        if command == "UP":
            self.rotate(1)
        elif command == "DOWN":
            self.rotate(-1)
        elif command == "ENTER":
            self.press(now)

    def rotate(self, delta: int) -> None:
        if self.view == "tabata_setup":
            self._rotate_tabata(delta)
            return
        if self.view == "swedish_setup":
            if self.selected == 0:
                self.swedish_config["warmupSec"] = max(0, self.swedish_config["warmupSec"] + delta * TIME_STEP_SECONDS)
            return
        if self.view in {"ride", "tabata_ride", "swedish_ride"}:
            return
        items = self.current_items()
        if items:
            self.selected = (self.selected + delta + len(items)) % len(items)

    def press(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if self.view == "review":
            self._select_review_action()
            return
        if self.view == "delete_confirm":
            self._select_delete_confirm_action()
            return
        if self._pending_press_at is not None and now - self._pending_press_at <= DOUBLE_PRESS_SECONDS:
            self._pending_press_at = None
            self.go_back()
            return
        self._pending_press_at = now

    def go_back(self) -> bool:
        self._pending_press_at = None
        if self.view == "rider_setup":
            self.view = "rider_select"
            self.selected = 0
            return True
        if self.view == "menu":
            self.view = "rider_select"
            self.selected = 0
            self.selected_rider = None
            return True
        if self.view in {"programs", "settings", "history"}:
            self.view = "menu"
            self.selected = 0
            return True
        if self.view == "tabata_setup":
            self.view = "programs"
            self.selected = 0
            return True
        if self.view == "swedish_setup":
            self.view = "programs"
            self.selected = 1
            return True
        if self.view == "review":
            self.view = "history"
            self.selected = 0
            return True
        if self.view == "delete_confirm":
            self.view = "review"
            self.selected = 1
            return True
        if self.view == "pause":
            self.status = "riding"
            self.view = self._ride_view()
            self.selected = 0
            self._last_update_at = time.time()
            return True
        return False

    def pop_saved_ride(self) -> dict[str, Any] | None:
        ride = self._last_saved_ride
        self._last_saved_ride = None
        return ride

    def pop_deleted_ride_id(self) -> str | None:
        ride_id = self._last_deleted_ride_id
        self._last_deleted_ride_id = None
        return ride_id

    def set_rider_profiles(self, rider_profiles: list[dict[str, Any]]) -> None:
        self.rider_profiles = self._clean_profiles(rider_profiles)

    def set_rides(self, rides: list[dict[str, Any]]) -> None:
        self.rides = list(rides)
        self.selected = min(self.selected, max(0, len(self.current_items()) - 1))

    def current_items(self) -> list[str]:
        if self.view == "rider_select":
            return self._rider_labels()
        if self.view == "menu":
            return MENU
        if self.view == "programs":
            return PROGRAMS
        if self.view == "tabata_setup":
            return ["Warmup", "All Out", "Recover", "Rounds", "Start"]
        if self.view == "swedish_setup":
            return ["Warmup", "Start"]
        if self.view == "history":
            return [format_mmss(ride.get("durationSec", 0)) for ride in self.rides]
        if self.view == "review":
            return REVIEW_ACTIONS
        if self.view == "delete_confirm":
            return DELETE_CONFIRM_ACTIONS
        if self.view == "pause":
            return PAUSE_MENU
        return []

    def selected_label(self) -> str:
        items = self.current_items()
        return items[self.selected] if 0 <= self.selected < len(items) else self.active_label

    def snapshot(self) -> dict[str, Any]:
        phase = None
        feedback = None
        if self.view == "tabata_ride":
            phase = self.tabata_phase().__dict__
        elif self.view == "swedish_ride":
            swedish_phase = self.swedish_phase()
            phase = swedish_phase.__dict__
            feedback = self.swedish_feedback(swedish_phase)
        review = self.active_review()
        return {
            "view": self.view,
            "status": self.status,
            "selected": self.selected,
            "items": self.current_items(),
            "selected_label": self.selected_label(),
            "active_label": self.active_label,
            "elapsed": self.elapsed,
            "elapsed_text": format_mmss(self.elapsed),
            "speed": self.speed,
            "avg_speed": self.avg_speed,
            "calories": self.calories,
            "pace": self.pace,
            "pace_history": list(self.pace_history),
            "phase": phase,
            "feedback": feedback,
            "tabata_config": dict(self.tabata_config),
            "swedish_config": dict(self.swedish_config),
            "rides": list(self.rides),
            "review": review,
            "rider_profiles": list(self.rider_profiles),
            "selected_rider": self._selected_rider_snapshot(),
            "setup": self._setup_snapshot() if self.view == "rider_setup" else None,
        }

    def active_review(self) -> dict[str, Any] | None:
        if self.view not in {"review", "delete_confirm"}:
            return None
        if self.active_review_id is None:
            return self.rides[0] if self.rides else None
        return next((ride for ride in self.rides if ride.get("id") == self.active_review_id), None)

    def tabata_summary(self, config: dict[str, Any] | None = None) -> str:
        config = config or self.tabata_config
        return f"{config['rounds']} x {config['hotSec']}s all out / {config['recoverSec']}s recover"

    def swedish_summary(self, config: dict[str, Any] | None = None) -> str:
        config = config or self.swedish_config
        return f"{config['rounds']} x {format_duration(config['hardSec'])} hard / {format_duration(config['recoverSec'])} recover"

    def tabata_total_seconds(self, config: dict[str, Any] | None = None) -> int:
        config = config or self.tabata_config
        return int(config["warmupSec"] + config["rounds"] * (config["hotSec"] + config["recoverSec"]))

    def swedish_total_seconds(self, config: dict[str, Any] | None = None) -> int:
        config = config or self.swedish_config
        return int(config["warmupSec"] + config["rounds"] * config["hardSec"] + (config["rounds"] - 1) * config["recoverSec"])

    def tabata_phase(self) -> Phase:
        config = self.tabata_config
        if self.elapsed >= self.tabata_total_seconds(config):
            return Phase("Done", 0, config["rounds"], config["rounds"])
        if self.elapsed < config["warmupSec"]:
            return Phase("Warmup", config["warmupSec"] - self.elapsed, 0, config["rounds"])
        interval_time = self.elapsed - config["warmupSec"]
        cycle = config["hotSec"] + config["recoverSec"]
        round_number = min(config["rounds"], int(interval_time // cycle) + 1)
        within = interval_time % cycle
        if within < config["hotSec"]:
            return Phase("All Out", config["hotSec"] - within, round_number, config["rounds"], self.elapsed - within)
        return Phase("Recover", cycle - within, round_number, config["rounds"], self.elapsed - within)

    def swedish_phase(self) -> Phase:
        config = self.swedish_config
        total = self.swedish_total_seconds(config)
        if self.elapsed >= total:
            return Phase("Done", 0, config["rounds"], config["rounds"], total)
        if self.elapsed < config["warmupSec"]:
            return Phase("Warmup", config["warmupSec"] - self.elapsed, 0, config["rounds"], 0)
        workout_time = self.elapsed - config["warmupSec"]
        for round_number in range(1, config["rounds"] + 1):
            hard_start = config["warmupSec"] + (round_number - 1) * (config["hardSec"] + config["recoverSec"])
            if workout_time < config["hardSec"]:
                return Phase("Hard", config["hardSec"] - workout_time, round_number, config["rounds"], hard_start)
            workout_time -= config["hardSec"]
            if round_number < config["rounds"]:
                if workout_time < config["recoverSec"]:
                    return Phase("Recover", config["recoverSec"] - workout_time, round_number, config["rounds"], hard_start + config["hardSec"])
                workout_time -= config["recoverSec"]
        return Phase("Done", 0, config["rounds"], config["rounds"], total)

    def swedish_feedback(self, phase: Phase) -> dict[str, str]:
        if phase.name == "Warmup":
            return {"status": "Warm up", "detail": "Save it for round 1"}
        if phase.name == "Recover":
            return {"status": "Recover", "detail": "Next hard round is coming"}
        if phase.name != "Hard":
            return {"status": "Done", "detail": "Save and end when ready"}
        round_average = self._average_pace_range(phase.phase_start, self.elapsed)
        if phase.round == 1:
            detail = f"{round_average:.1f} Cal/min this round" if round_average else "Build a steady hard pace"
            return {"status": "Set pace", "detail": detail}
        config = self.swedish_config
        previous_start = config["warmupSec"] + (phase.round - 2) * (config["hardSec"] + config["recoverSec"])
        target = self._average_pace_range(previous_start, previous_start + config["hardSec"])
        delta = self.pace - target
        status = "Above pace" if delta > 0.5 else "Under pace" if delta < -0.5 else "On pace"
        sign = "+" if delta >= 0 else ""
        return {"status": status, "detail": f"{sign}{delta:.1f} vs round {phase.round - 1}"}

    def _flush_pending_press(self, now: float) -> None:
        if self._pending_press_at is not None and now - self._pending_press_at > DOUBLE_PRESS_SECONDS:
            self._pending_press_at = None
            self._single_press()

    def _single_press(self) -> None:
        if self.view == "rider_select":
            self._select_rider_item()
            return
        if self.view == "rider_setup":
            return
        if self.view == "menu":
            item = MENU[self.selected]
            if item == "Ride":
                self._start_ride("Ride", "ride")
            elif item == "Programs":
                self.view = "programs"
                self.selected = 0
            elif item == "History":
                self.view = "history"
                self.selected = 0
            elif item == "Settings":
                self.view = "settings"
                self.selected = 0
            return
        if self.view == "programs":
            item = PROGRAMS[self.selected]
            if item == "Tabata":
                self.view = "tabata_setup"
            elif item == "Swedish 4x4":
                self.view = "swedish_setup"
            self.selected = 0
            return
        if self.view == "tabata_setup":
            if self.selected == 4:
                self._start_ride("Tabata", "tabata")
            else:
                self.selected = min(4, self.selected + 1)
            return
        if self.view == "swedish_setup":
            if self.selected == 1:
                self._start_ride("Swedish 4x4", "swedish")
            else:
                self.selected = 1
            return
        if self.view == "history":
            if self.rides:
                self.active_review_id = self.rides[self.selected].get("id")
                self.view = "review"
                self.selected = 0
            return
        if self.view in {"ride", "tabata_ride", "swedish_ride"}:
            self.status = "paused"
            self.view = "pause"
            self.selected = 0
            return
        if self.view == "pause":
            item = PAUSE_MENU[self.selected]
            if item == "Resume":
                self.status = "riding"
                self.view = self._ride_view()
                self._last_update_at = time.time()
            elif item == "Save and End":
                self._save_and_reset()
            elif item == "Discard":
                self._reset("idle")

    def _select_review_action(self) -> None:
        item = REVIEW_ACTIONS[self.selected]
        if item == "Back":
            self.go_back()
        elif item == "Delete" and self.active_review():
            self.view = "delete_confirm"
            self.selected = 0

    def _select_delete_confirm_action(self) -> None:
        item = DELETE_CONFIRM_ACTIONS[self.selected]
        if item == "No":
            self.view = "review"
            self.selected = 1
            return
        self._delete_active_review()

    def _delete_active_review(self) -> None:
        ride = self.active_review()
        if not ride:
            self.view = "history"
            self.selected = 0
            return
        ride_id = ride.get("id")
        deleted_index = next(
            (index for index, existing in enumerate(self.rides) if existing.get("id") == ride_id),
            0,
        )
        self.rides = [existing for existing in self.rides if existing.get("id") != ride_id]
        if ride_id:
            self._last_deleted_ride_id = str(ride_id)
        self.active_review_id = None
        self.view = "history"
        self.selected = min(deleted_index, max(0, len(self.rides) - 1))

    def _rotate_tabata(self, delta: int) -> None:
        if self.selected == 0:
            self.tabata_config["warmupSec"] = max(0, self.tabata_config["warmupSec"] + delta * TIME_STEP_SECONDS)
        elif self.selected == 1:
            self.tabata_config["hotSec"] = max(TIME_STEP_SECONDS, self.tabata_config["hotSec"] + delta * TIME_STEP_SECONDS)
        elif self.selected == 2:
            self.tabata_config["recoverSec"] = max(TIME_STEP_SECONDS, self.tabata_config["recoverSec"] + delta * TIME_STEP_SECONDS)
        elif self.selected == 3:
            rounds = [4, 6, 8, 10, 12, 16, 20]
            index = rounds.index(self.tabata_config["rounds"])
            self.tabata_config["rounds"] = rounds[(index + delta + len(rounds)) % len(rounds)]

    def _start_ride(self, label: str, mode: str) -> None:
        now = time.time()
        if self.selected_rider is None:
            self.selected_rider = self._guest_rider()
        self.status = "riding"
        self.active_label = label
        self.active_mode = mode
        self.view = self._ride_view()
        self.selected = 0
        self.started_at = now
        self.ended_at = None
        self._last_update_at = now
        self.elapsed = 0.0
        self.distance = 0.0
        self.speed = 0.0
        self.avg_speed = 0.0
        self.calories = 0.0
        self.pace = 0.0
        self.pace_history = [0.0]
        self.speed_history = [0.0]

    def _complete_program(self) -> None:
        self.status = "paused"
        self.view = "pause"
        self.selected = 1
        self.ended_at = time.time()

    def _save_and_reset(self) -> None:
        ended_at = time.time()
        rider = self._selected_rider_snapshot() or self._guest_rider()
        ride = {
            "id": f"{int(ended_at)}-{int(self.calories * 10)}",
            "label": self.active_label,
            "program": self.active_mode,
            "rider": rider,
            "rider_profile_id": rider.get("id") if rider.get("kind") == "profile" else None,
            "rider_display_name": rider["display_name"],
            "durable": rider["durable"],
            "started_at": self.started_at or ended_at - self.elapsed,
            "ended_at": ended_at,
            "durationSec": int(round(self.elapsed)),
            "calories": round(self.calories, 1),
            "distance": round(self.distance, 2),
            "avgSpeed": round(self.avg_speed, 1),
            "avgPace": round(self.calories / (self.elapsed / 60.0), 1) if self.elapsed > 0 else 0.0,
            "maxSpeed": round(max(self.speed_history or [0.0]), 1),
            "maxPace": round(max(self.pace_history or [0.0]), 1),
            "structure": self._active_structure(),
            "samples": [round(value, 1) for value in self._sample_series(self.pace_history, 60)],
            "type": _program_label(self.active_label),
        }
        self.rides = [ride, *self.rides[:19]]
        self._last_saved_ride = ride
        self._reset("idle")

    def _reset(self, status: str) -> None:
        self.view = "menu" if self.selected_rider else "rider_select"
        self.status = status
        self.selected = 0
        self.active_label = "Ride"
        self.active_mode = "ride"
        self.active_review_id = None
        self.elapsed = 0.0
        self.distance = 0.0
        self.speed = 0.0
        self.avg_speed = 0.0
        self.calories = 0.0
        self.pace = 0.0
        self.pace_history = [0.0]
        self.speed_history = [0.0]
        self.started_at = None
        self.ended_at = None
        self._last_update_at = None
        self._pending_press_at = None

    def _ride_view(self) -> str:
        if self.active_mode == "tabata":
            return "tabata_ride"
        if self.active_mode == "swedish":
            return "swedish_ride"
        return "ride"

    def _active_structure(self) -> dict[str, Any] | None:
        if self.active_mode == "tabata":
            return dict(self.tabata_config)
        if self.active_mode == "swedish":
            return dict(self.swedish_config)
        return None

    def _select_rider_item(self) -> None:
        labels = self._rider_labels()
        if not labels:
            return
        item = labels[self.selected]
        if item == NEW_RIDER_LABEL:
            self.view = "rider_setup"
            self.selected = 0
            return
        if item == GUEST_LABEL:
            self.selected_rider = self._guest_rider()
        else:
            profile = self._profile_for_label(item)
            if profile is None:
                return
            self.selected_rider = {
                "kind": "profile",
                "id": profile["id"],
                "display_name": profile["display_name"],
                "durable": True,
            }
        self.view = "menu"
        self.selected = 0

    def _rider_labels(self) -> list[str]:
        labels = [profile["display_name"] for profile in self.rider_profiles]
        labels.extend([GUEST_LABEL, NEW_RIDER_LABEL])
        return labels

    def _profile_for_label(self, label: str) -> dict[str, Any] | None:
        return next((profile for profile in self.rider_profiles if profile["display_name"] == label), None)

    def _selected_rider_snapshot(self) -> dict[str, Any] | None:
        return dict(self.selected_rider) if self.selected_rider else None

    def _setup_snapshot(self) -> dict[str, str]:
        return {
            "instruction": SETUP_INSTRUCTION,
            "url": self.profile_setup_url,
        }

    @staticmethod
    def _guest_rider() -> dict[str, Any]:
        return {
            "kind": "guest",
            "id": None,
            "display_name": GUEST_LABEL,
            "durable": False,
        }

    @staticmethod
    def _clean_profiles(rider_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        profiles = []
        for profile in rider_profiles:
            display_name = str(profile.get("display_name", "")).strip()
            if not display_name:
                continue
            profiles.append(
                {
                    **profile,
                    "id": int(profile["id"]),
                    "display_name": display_name,
                }
            )
        return profiles

    def _average_pace_range(self, start_sec: float, end_sec: float) -> float:
        start = max(1, int(start_sec) + 1)
        end = min(len(self.pace_history), max(start, int(end_sec) + 1))
        values = [value for value in self.pace_history[start:end] if isinstance(value, (int, float))]
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _sample_series(values: list[float], max_points: int) -> list[float]:
        if len(values) <= max_points:
            return values
        stride = (len(values) - 1) / (max_points - 1)
        return [values[min(len(values) - 1, round(index * stride))] for index in range(max_points)]
