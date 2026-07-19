#!/usr/bin/env python3
"""SQLite storage boundary for durable PiCycle appliance data."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable


SCHEMA_VERSION = 2
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

CREATE TABLE IF NOT EXISTS rider_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    archived_at REAL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER,
    rider_profile_id INTEGER,
    started_at REAL NOT NULL,
    ended_at REAL,
    status TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (program_id) REFERENCES workout_programs(id),
    FOREIGN KEY (rider_profile_id) REFERENCES rider_profiles(id)
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_rider_profiles_active_name
    ON rider_profiles(display_name COLLATE NOCASE)
    WHERE archived_at IS NULL;
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
    _migrate_sessions_schema(connection)
    connection.execute(
        """
        INSERT INTO schema_meta(key, value)
        VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )
    connection.commit()


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _session_has_rider_profile_fk(connection: sqlite3.Connection) -> bool:
    rows = connection.execute("PRAGMA foreign_key_list(sessions)").fetchall()
    return any(row["from"] == "rider_profile_id" and row["table"] == "rider_profiles" for row in rows)


def _migrate_sessions_schema(connection: sqlite3.Connection) -> None:
    columns = _table_columns(connection, "sessions")
    if "rider_profile_id" in columns and _session_has_rider_profile_fk(connection):
        return

    rider_profile_select = "rider_profile_id" if "rider_profile_id" in columns else "NULL"
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("DROP TABLE IF EXISTS sessions_new")
        connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS sessions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                rider_profile_id INTEGER,
                started_at REAL NOT NULL,
                ended_at REAL,
                status TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{{}}',
                FOREIGN KEY (program_id) REFERENCES workout_programs(id),
                FOREIGN KEY (rider_profile_id) REFERENCES rider_profiles(id)
            );

            INSERT INTO sessions_new(
                id, program_id, rider_profile_id, started_at, ended_at, status, summary_json
            )
            SELECT id, program_id, {rider_profile_select}, started_at, ended_at, status, summary_json
            FROM sessions;

            DROP TABLE sessions;
            ALTER TABLE sessions_new RENAME TO sessions;
            """
        )
        connection.commit()
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


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


def _clean_display_name(display_name: str) -> str:
    cleaned = " ".join(str(display_name).split())
    if not cleaned:
        raise ValueError("Rider profile display name cannot be blank.")
    return cleaned


def create_rider_profile(
    connection: sqlite3.Connection,
    display_name: str,
    created_at: float | None = None,
) -> int:
    now = created_at or time.time()
    cursor = connection.execute(
        """
        INSERT INTO rider_profiles(display_name, created_at, updated_at)
        VALUES(?, ?, ?)
        """,
        (_clean_display_name(display_name), now, now),
    )
    connection.commit()
    return int(cursor.lastrowid)


def get_rider_profile(connection: sqlite3.Connection, rider_profile_id: int) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM rider_profiles WHERE id = ?",
        (rider_profile_id,),
    ).fetchone()
    return dict(row) if row else None


def list_rider_profiles(
    connection: sqlite3.Connection,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    where = "" if include_archived else "WHERE archived_at IS NULL"
    rows = connection.execute(
        f"""
        SELECT *
        FROM rider_profiles
        {where}
        ORDER BY display_name COLLATE NOCASE, id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def archive_rider_profile(
    connection: sqlite3.Connection,
    rider_profile_id: int,
    archived_at: float | None = None,
) -> bool:
    now = archived_at or time.time()
    cursor = connection.execute(
        """
        UPDATE rider_profiles
        SET archived_at = ?, updated_at = ?
        WHERE id = ? AND archived_at IS NULL
        """,
        (now, now, rider_profile_id),
    )
    connection.commit()
    return cursor.rowcount > 0


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
    rider_profile_id: int | None = None,
    started_at: float | None = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO sessions(program_id, rider_profile_id, started_at, status)
        VALUES(?, ?, ?, 'active')
        """,
        (program_id, rider_profile_id, started_at or time.time()),
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


def save_completed_ride_summary(
    connection: sqlite3.Connection,
    ride: dict[str, Any],
    program_id: int | None = None,
    rider_profile_id: int | None = None,
) -> int:
    selected_rider_profile_id = rider_profile_id or ride.get("rider_profile_id")
    if selected_rider_profile_id is not None:
        ride = {**ride, "rider_profile_id": int(selected_rider_profile_id)}
    session_id = create_session(
        connection,
        program_id=program_id,
        rider_profile_id=selected_rider_profile_id,
        started_at=ride.get("started_at"),
    )
    complete_session(connection, session_id, ride, ended_at=ride.get("ended_at"))
    return session_id


def list_completed_ride_summaries(
    connection: sqlite3.Connection,
    limit: int = 20,
    rider_profile_id: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    rider_filter = ""
    if rider_profile_id is not None:
        rider_filter = "AND s.rider_profile_id = ?"
        params.append(rider_profile_id)
    params.append(limit)
    rows = connection.execute(
        f"""
        SELECT
            s.id,
            s.started_at,
            s.ended_at,
            s.summary_json,
            s.rider_profile_id,
            rp.display_name AS rider_display_name
        FROM sessions s
        LEFT JOIN rider_profiles rp ON rp.id = s.rider_profile_id
        WHERE s.status = 'completed'
        {rider_filter}
        ORDER BY s.ended_at DESC, s.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    rides = []
    for row in rows:
        summary = _json_loads(row["summary_json"])
        summary.setdefault("id", f"session-{row['id']}")
        summary.setdefault("started_at", row["started_at"])
        summary.setdefault("ended_at", row["ended_at"])
        summary.setdefault("rider_profile_id", row["rider_profile_id"])
        if row["rider_display_name"]:
            summary.setdefault("rider_display_name", row["rider_display_name"])
            summary.setdefault(
                "rider",
                {
                    "kind": "profile",
                    "id": row["rider_profile_id"],
                    "display_name": row["rider_display_name"],
                    "durable": True,
                },
            )
        rides.append(summary)
    return rides


def delete_completed_ride_summary(connection: sqlite3.Connection, ride_id: str) -> bool:
    rows = connection.execute(
        """
        SELECT id, summary_json
        FROM sessions
        WHERE status = 'completed'
        """
    ).fetchall()
    session_id = None
    if ride_id.startswith("session-"):
        try:
            session_id = int(ride_id.removeprefix("session-"))
        except ValueError:
            session_id = None
    for row in rows:
        summary = _json_loads(row["summary_json"])
        if row["id"] == session_id or summary.get("id") == ride_id:
            connection.execute("DELETE FROM sessions WHERE id = ?", (row["id"],))
            connection.commit()
            return True
    return False


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
