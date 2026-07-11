import unittest

from ride_session import (
    COMPLETED,
    DISCARDED,
    IDLE,
    PAUSED,
    RIDING,
    SAVED,
    InvalidTransition,
    RideSession,
)


class RideSessionTests(unittest.TestCase):
    def test_start_pause_resume_complete_save_flow(self):
        session = RideSession()
        session.start(10.0)
        self.assertEqual(session.state, RIDING)

        session.pause(20.0)
        self.assertEqual(session.state, PAUSED)

        session.resume(25.0)
        self.assertEqual(session.state, RIDING)

        session.complete(40.0)
        self.assertEqual(session.state, COMPLETED)
        self.assertEqual(session.active_seconds(40.0), 25.0)

        session.save(41.0)
        self.assertEqual(session.state, SAVED)
        self.assertEqual([event["type"] for event in session.events], ["start", "pause", "resume", "complete", "save"])

    def test_pause_time_is_excluded_while_still_paused(self):
        session = RideSession()
        session.start(0.0)
        session.pause(10.0)
        self.assertEqual(session.active_seconds(25.0), 10.0)
        self.assertEqual(session.snapshot(25.0)["state"], PAUSED)

    def test_invalid_transitions_are_rejected(self):
        session = RideSession()
        with self.assertRaises(InvalidTransition):
            session.pause(1.0)
        session.start(2.0)
        with self.assertRaises(InvalidTransition):
            session.save(3.0)

    def test_completed_session_can_be_discarded(self):
        session = RideSession()
        session.start(1.0)
        session.complete(2.0)
        session.discard(3.0)
        self.assertEqual(session.state, DISCARDED)

    def test_idle_session_can_be_discarded(self):
        session = RideSession()
        self.assertEqual(session.state, IDLE)
        session.discard(1.0)
        self.assertEqual(session.state, DISCARDED)


if __name__ == "__main__":
    unittest.main()

