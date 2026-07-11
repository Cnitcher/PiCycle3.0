#!/usr/bin/env python3
"""SQLite storage boundary for durable PiCycle appliance data."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable


SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path("data/picycle.sqlite3")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    archived_at REAL
);

CREATE TABLE IF NOT EXISTS program_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    target_kind TEXT NOT NULL DEFAULT '',
    target_value REAL,
    label TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (program_id) REFERENCES workout_programs(id) ON DELETE CASCADE,
    UNIQUE (program_id, position)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER,
    started_at REAL NOT NULL,
    ended_at REAL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (program_id) REFERENCES workout_programs(id)
);

CREATE TABLE IF NOT EXISTS session_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    captured_at REAL NOT NULL,
    elapsed_seconds REAL NOT NULL,
    speed_mph REAL,
    avg_speed_mph REAL,
    distance_miles REAL,
    rpm REAL,
    avg_rpm REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    occurred_at REAL NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_samples_session_time
    ON session_samples(session_id, captured_at);

CREATE INDEX IF NOT EXISTS idx_session_events_session_time
    ON session_events(session_id, occurred_at);
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        """
        INSERT INTO schema_meta(key, value)
        VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )
    connection.commit()


@contextmanager
def open_database(db_path: str | Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    connection = connect(db_path)
    try:
        initialize(connection)
        yield connection
    finally:
        connection.close()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> Any:
    return json.loads(value)


def set_setting(connection: sqlite3.Connection, key: str, value: Any) -> None:
    connection.execute(
        """
        INSERT INTO settings(key, value_json, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        """,
        (key, _json_dumps(value), time.time()),
    )
    connection.commit()


def get_setting(connection: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = connection.execute(
        "SELECT value_json FROM settings WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return default
    return _json_loads(row["value_json"])


def create_program(
    connection: sqlite3.Connection,
    name: str,
    steps: Iterable[dict[str, Any]],
    description: str = "",
) -> int:
    now = time.time()
    cursor = connection.execute(
        """
        INSERT INTO workout_programs(name, description, created_at, updated_at)
        VALUES(?, ?, ?, ?)
        """,
        (name, description, now, now),
    )
    program_id = int(cursor.lastrowid)
    for position, step in enumerate(steps, start=1):
        connection.execute(
            """
            INSERT INTO program_steps(
                program_id, position, step_type, duration_seconds,
                target_kind, target_value, label
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                program_id,
                position,
                step["step_type"],
                int(step["duration_seconds"]),
                step.get("target_kind", ""),
                step.get("target_value"),
                step.get("label", ""),
            ),
        )
    connection.commit()
    return program_id


def get_program(connection: sqlite3.Connection, program_id: int) -> dict[str, Any] | None:
    program = connection.execute(
        "SELECT * FROM workout_programs WHERE id = ?",
        (program_id,),
    ).fetchone()
    if program is None:
        return None
    steps = connection.execute(
        "SELECT * FROM program_steps WHERE program_id = ? ORDER BY position",
        (program_id,),
    ).fetchall()
    return {
        "id": program["id"],
        "name": program["name"],
        "description": program["description"],
        "created_at": program["created_at"],
        "updated_at": program["updated_at"],
        "archived_at": program["archived_at"],
        "steps": [dict(step) for step in steps],
    }


def create_session(
    connection: sqlite3.Connection,
    program_id: int | None = None,
    started_at: float | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO sessions(program_id, started_at, status)
        VALUES(?, ?, 'active')
        """,
        (program_id, started_at or time.time()),
    )
    connection.commit()
    return int(cursor.lastrowid)


def add_session_sample(
    connection: sqlite3.Connection,
    session_id: int,
    sample: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO session_samples(
            session_id, captured_at, elapsed_seconds, speed_mph,
            avg_speed_mph, distance_miles, rpm, avg_rpm
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            sample.get("captured_at", time.time()),
            sample["elapsed_seconds"],
            sample.get("speed_mph"),
            sample.get("avg_speed_mph"),
            sample.get("distance_miles"),
            sample.get("rpm"),
            sample.get("avg_rpm"),
        ),
    )
    connection.commit()


def add_session_event(
    connection: sqlite3.Connection,
    session_id: int,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO session_events(session_id, occurred_at, event_type, payload_json)
        VALUES(?, ?, ?, ?)
        """,
        (session_id, time.time(), event_type, _json_dumps(payload or {})),
    )
    connection.commit()


def complete_session(
    connection: sqlite3.Connection,
    session_id: int,
    summary: dict[str, Any],
    ended_at: float | None = None,
) -> None:
    connection.execute(
        """
        UPDATE sessions
        SET status = 'completed', ended_at = ?, summary_json = ?
        WHERE id = ?
        """,
        (ended_at or time.time(), _json_dumps(summary), session_id),
    )
    connection.commit()


def get_session(connection: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    session = connection.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if session is None:
        return None
    samples = connection.execute(
        "SELECT * FROM session_samples WHERE session_id = ? ORDER BY captured_at",
        (session_id,),
    ).fetchall()
    events = connection.execute(
        "SELECT * FROM session_events WHERE session_id = ? ORDER BY occurred_at",
        (session_id,),
    ).fetchall()
    result = dict(session)
    result["summary"] = _json_loads(result.pop("summary_json"))
    result["samples"] = [dict(sample) for sample in samples]
    result["events"] = [
        {
            **dict(event),
            "payload": _json_loads(event["payload_json"]),
        }
        for event in events
    ]
    return result
