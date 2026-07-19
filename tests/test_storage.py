import tempfile
import unittest
from pathlib import Path

import storage


class StorageTests(unittest.TestCase):
    def test_initialize_records_schema_version(self):
        with storage.open_database(":memory:") as connection:
            value = connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()["value"]
        self.assertEqual(value, str(storage.SCHEMA_VERSION))

    def test_settings_round_trip_json_values(self):
        with storage.open_database(":memory:") as connection:
            storage.set_setting(connection, "display", {"brightness": 80, "sleep": True})
            value = storage.get_setting(connection, "display")
        self.assertEqual(value, {"brightness": 80, "sleep": True})

    def test_program_round_trip_with_steps(self):
        with storage.open_database(":memory:") as connection:
            program_id = storage.create_program(
                connection,
                "30/30",
                [
                    {"step_type": "warmup", "duration_seconds": 120, "label": "Warmup"},
                    {
                        "step_type": "work",
                        "duration_seconds": 30,
                        "target_kind": "rpm",
                        "target_value": 85,
                        "label": "Push",
                    },
                ],
                description="Starter interval",
            )
            program = storage.get_program(connection, program_id)
        self.assertIsNotNone(program)
        self.assertEqual(program["name"], "30/30")
        self.assertEqual(len(program["steps"]), 2)
        self.assertEqual(program["steps"][1]["target_kind"], "rpm")

    def test_session_samples_events_and_completion(self):
        with storage.open_database(":memory:") as connection:
            session_id = storage.create_session(connection, started_at=100.0)
            storage.add_session_sample(
                connection,
                session_id,
                {
                    "captured_at": 101.0,
                    "elapsed_seconds": 1.0,
                    "speed_mph": 12.5,
                    "avg_speed_mph": 12.5,
                    "distance_miles": 0.003,
                    "rpm": 84.0,
                    "avg_rpm": 84.0,
                },
            )
            storage.add_session_event(connection, session_id, "pause", {"reason": "test"})
            storage.complete_session(
                connection,
                session_id,
                {"duration_seconds": 1.0, "distance_miles": 0.003},
                ended_at=102.0,
            )
            session = storage.get_session(connection, session_id)
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["summary"]["distance_miles"], 0.003)
        self.assertEqual(len(session["samples"]), 1)
        self.assertEqual(session["events"][0]["payload"], {"reason": "test"})

    def test_completed_ride_summary_helpers_round_trip(self):
        ride = {
            "id": "ride-1",
            "label": "Tabata",
            "program": "tabata",
            "started_at": 100.0,
            "ended_at": 200.0,
            "durationSec": 100,
            "calories": 12.3,
        }
        with storage.open_database(":memory:") as connection:
            storage.save_completed_ride_summary(connection, ride)
            rides = storage.list_completed_ride_summaries(connection)
        self.assertEqual(len(rides), 1)
        self.assertEqual(rides[0]["label"], "Tabata")
        self.assertEqual(rides[0]["calories"], 12.3)

    def test_delete_completed_ride_summary_by_summary_id(self):
        ride = {
            "id": "ride-1",
            "label": "Ride",
            "started_at": 100.0,
            "ended_at": 200.0,
            "durationSec": 100,
        }
        with storage.open_database(":memory:") as connection:
            storage.save_completed_ride_summary(connection, ride)
            deleted = storage.delete_completed_ride_summary(connection, "ride-1")
            rides = storage.list_completed_ride_summaries(connection)
        self.assertTrue(deleted)
        self.assertEqual(rides, [])

    def test_delete_completed_ride_summary_by_generated_session_id(self):
        ride = {
            "label": "Ride",
            "started_at": 100.0,
            "ended_at": 200.0,
            "durationSec": 100,
        }
        with storage.open_database(":memory:") as connection:
            session_id = storage.save_completed_ride_summary(connection, ride)
            deleted = storage.delete_completed_ride_summary(connection, f"session-{session_id}")
            rides = storage.list_completed_ride_summaries(connection)
        self.assertTrue(deleted)
        self.assertEqual(rides, [])

    def test_file_database_parent_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nested" / "picycle.sqlite3"
            with storage.open_database(db_path) as connection:
                storage.set_setting(connection, "unit", "imperial")
            self.assertTrue(db_path.exists())


if __name__ == "__main__":
    unittest.main()
