# PiCycle Storage Boundary

PiCycle uses SQLite for durable appliance data and keeps realtime ride state in memory.

## Durable Data

SQLite owns:

- settings values that need history-safe updates,
- workout programs and ordered program steps,
- workout sessions,
- sampled session metrics,
- session events such as pause, resume, interval change, and completion.

## Realtime Data

Do not write every Hall sensor pulse to SQLite. Realtime sensor-derived values belong in
memory while the ride is active. Durable writes should happen at boundaries or controlled
sample intervals.

Initial write-frequency assumption:

- session start/end: write immediately,
- session events: write when the event occurs,
- session samples: write no more than once per second by default,
- raw Hall pulses: never write directly to durable storage.

## Database Location

The default database path is `data/picycle.sqlite3`. The `data/` directory is ignored by
Git because it is local runtime state.

Tests use temporary or in-memory SQLite databases.

